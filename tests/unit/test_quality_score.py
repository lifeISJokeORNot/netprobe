"""
Unit tests for tester._quality_score — the function that translates raw
latency and packet-loss numbers into a 0-100 score and a letter grade.

Includes a property-based test using Hypothesis: rather than picking a
handful of example inputs, Hypothesis generates hundreds of random inputs
and checks that an invariant always holds. This catches edge cases that
example-based tests miss.
"""

import pytest
from hypothesis import given, strategies as st
from tester import _quality_score


# ── Example-based tests ───────────────────────────────────────────────────────

def test_no_signal_returns_grade_f():
    """latency=None means no response at all — must be the worst grade."""
    result = _quality_score(None, 100)
    assert result["grade"] == "F"
    assert result["score"] == 0
    assert result["label"] == "No signal"


def test_perfect_conditions_grade_a():
    """1ms latency, 0% loss → top of the scale."""
    result = _quality_score(1.0, 0.0)
    assert result["grade"] == "A"
    assert result["score"] >= 90


def test_terrible_conditions_grade_f():
    """Very high latency and high loss → F."""
    result = _quality_score(800.0, 80.0)
    assert result["grade"] == "F"


@pytest.mark.parametrize("avg_ms,loss_pct,expected_grade", [
    (10.0,  0.0,  "A"),    # excellent
    (50.0,  0.0,  "A"),    # still excellent
    (60.0,  0.0,  "B"),    # good
    (90.0,  5.0,  "C"),    # fair
    (150.0, 10.0, "D"),    # poor
])
def test_grade_thresholds(avg_ms, loss_pct, expected_grade):
    """Each grade band should be reachable with reasonable inputs."""
    result = _quality_score(avg_ms, loss_pct)
    assert result["grade"] == expected_grade, (
        f"latency={avg_ms}, loss={loss_pct} produced grade {result['grade']} "
        f"(score {result['score']}), expected {expected_grade}"
    )


# ── Property-based test ───────────────────────────────────────────────────────

@given(
    avg_ms=st.floats(min_value=0.0, max_value=10_000.0, allow_nan=False, allow_infinity=False),
    loss_pct=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
)
def test_score_always_in_valid_range(avg_ms, loss_pct):
    """
    PROPERTY: For any valid latency/loss input, the score must be in [0, 100]
    and the grade must be one of the five defined letters.

    Hypothesis will generate ~100 random examples and try to find one that
    breaks this invariant. If something passes a max() guard wrong or a
    rounding edge case sneaks in, this test will fail.
    """
    result = _quality_score(avg_ms, loss_pct)
    assert 0 <= result["score"] <= 100, f"score {result['score']} out of range"
    assert result["grade"] in {"A", "B", "C", "D", "F"}
    assert isinstance(result["label"], str) and result["label"]


@given(loss_pct=st.floats(min_value=0.0, max_value=100.0, allow_nan=False))
def test_no_signal_always_grade_f(loss_pct):
    """No matter what loss_pct is, latency=None should always give grade F."""
    result = _quality_score(None, loss_pct)
    assert result["grade"] == "F"
    assert result["score"] == 0

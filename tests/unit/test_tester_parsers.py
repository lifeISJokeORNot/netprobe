"""
Unit tests for tester.py — focuses on the _system_ping_fallback parser and
the run_ping_test wrapper.

These tests use mocking to avoid any real network or subprocess calls, so
they run identically on every machine (and on CI without network access).
"""

from pathlib import Path
from unittest.mock import patch
import subprocess
import pytest

import tester
from tester import _system_ping_fallback, run_ping_test


FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


# ── DEF-003 REGRESSION TEST ───────────────────────────────────────────────────
# The original parser split on '/' and grabbed the first numeric token,
# which on Linux returned the *minimum* (12.345) instead of the average
# (15.678). The fix uses anchored regex.

def test_linux_parser_returns_avg_not_min():
    """
    REGRESSION (DEF-003): Linux ping output 'rtt min/avg/max/mdev = 12.3/15.6/19.0/2.3'
    must yield avg=15.6, NOT min=12.3.
    """
    output = _read_fixture("ping_linux.txt")
    with patch("subprocess.check_output", return_value=output.encode()):
        result = _system_ping_fallback("8.8.8.8", 4)
    assert result["latency_avg_ms"] == 15.678, (
        f"Parser returned {result['latency_avg_ms']} — expected the avg (15.678), "
        "not the minimum. DEF-003 has regressed."
    )


def test_windows_parser_extracts_average():
    """Windows: 'Minimum = 14ms, Maximum = 18ms, Average = 16ms' → avg=16."""
    output = _read_fixture("ping_windows.txt")
    with patch("subprocess.check_output", return_value=output.encode()):
        result = _system_ping_fallback("8.8.8.8", 4)
    assert result["latency_avg_ms"] == 16.0


def test_garbage_output_yields_none_avg():
    """Unparseable output must not crash — returns success but with avg=None."""
    output = _read_fixture("ping_garbage.txt")
    with patch("subprocess.check_output", return_value=output.encode()):
        result = _system_ping_fallback("8.8.8.8", 4)
    assert result["latency_avg_ms"] is None
    assert result["status"].startswith("success")


def test_empty_output_yields_none_avg():
    with patch("subprocess.check_output", return_value=b""):
        result = _system_ping_fallback("8.8.8.8", 4)
    assert result["latency_avg_ms"] is None


def test_decimal_avg_preserved():
    """Decimal averages must not be truncated to int."""
    fake = b"rtt min/avg/max/mdev = 1.0/2.5/4.0/1.0 ms\n"
    with patch("subprocess.check_output", return_value=fake):
        result = _system_ping_fallback("host", 4)
    assert result["latency_avg_ms"] == 2.5


# ── Subprocess error handling ─────────────────────────────────────────────────

def test_called_process_error_returns_unreachable():
    err = subprocess.CalledProcessError(1, "ping")
    with patch("subprocess.check_output", side_effect=err):
        result = _system_ping_fallback("8.8.8.8", 4)
    assert result["status"] == "unreachable"
    assert result["packet_loss_percent"] == 100.0


def test_unexpected_exception_returns_error_status():
    with patch("subprocess.check_output", side_effect=OSError("boom")):
        result = _system_ping_fallback("8.8.8.8", 4)
    assert result["status"] == "error"
    assert "boom" in result["error"]


# ── run_ping_test integration with ping3 ──────────────────────────────────────

def test_ping_test_aggregates_latencies_correctly():
    """All packets succeed → loss=0, avg = mean(latencies)."""
    with patch("tester.ping3_ping", side_effect=[10.0, 20.0, 30.0, 40.0]):
        result = run_ping_test("8.8.8.8", count=4)
    assert result["packet_loss_percent"] == 0.0
    assert result["latency_avg_ms"] == 25.0
    assert result["latency_min_ms"] == 10.0
    assert result["latency_max_ms"] == 40.0
    assert result["status"] == "success"


def test_ping_test_partial_loss():
    """Half the packets fail → 50% loss and avg over the survivors."""
    with patch("tester.ping3_ping", side_effect=[10.0, None, 20.0, False]):
        result = run_ping_test("8.8.8.8", count=4)
    assert result["packet_loss_percent"] == 50.0
    assert result["latency_avg_ms"] == 15.0
    assert result["packets_received"] == 2


def test_ping_test_total_loss_marks_unreachable():
    """All packets fail → status='unreachable' and metrics are None."""
    with patch("tester.ping3_ping", return_value=None):
        result = run_ping_test("8.8.8.8", count=4)
    assert result["status"] == "unreachable"
    assert result["latency_avg_ms"] is None
    assert result["packet_loss_percent"] == 100.0


def test_ping_test_falls_back_on_ping3_exception():
    """If ping3 raises, the system ping fallback is invoked."""
    fake_linux_output = b"rtt min/avg/max/mdev = 1.0/2.0/3.0/0.5 ms\n"
    with patch("tester.ping3_ping", side_effect=PermissionError("raw socket")), \
         patch("subprocess.check_output", return_value=fake_linux_output):
        result = run_ping_test("8.8.8.8", count=4)
    assert "fallback" in result["status"]
    assert result["latency_avg_ms"] == 2.0

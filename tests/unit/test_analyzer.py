"""
Unit tests for analyzer.py — anomaly detection logic.

These tests cover:
  - Boundary conditions (insufficient history, exactly-at-threshold values)
  - Each severity branch (None / warning / critical) for both ping and speed
  - The DEF-002 regression: severity must escalate, never downgrade
  - Unknown test types and malformed inputs
"""

import pytest
from analyzer import analyze_result, MIN_HISTORY


# ── Insufficient-history guards ───────────────────────────────────────────────

def test_returns_none_with_empty_history():
    """No baseline at all → no anomaly can be detected."""
    result = {"latency_avg_ms": 500.0, "packet_loss_percent": 0.0}
    assert analyze_result("ping", result, []) is None


def test_returns_none_with_history_below_minimum(healthy_ping_history):
    """Fewer than MIN_HISTORY records → cannot establish baseline → no anomaly."""
    short_history = healthy_ping_history[: MIN_HISTORY - 1]
    result = {"latency_avg_ms": 500.0, "packet_loss_percent": 0.0}
    assert analyze_result("ping", result, short_history) is None


def test_returns_none_when_history_records_lack_latency():
    """Records without latency_avg_ms must be skipped, not crash."""
    history = [{"host": "8.8.8.8"} for _ in range(10)]   # no latency fields
    result = {"latency_avg_ms": 500.0, "packet_loss_percent": 0.0}
    assert analyze_result("ping", result, history) is None


# ── Ping: healthy / no anomaly ────────────────────────────────────────────────

def test_no_anomaly_at_baseline(healthy_ping_history):
    """Current latency matches baseline → nothing to flag."""
    result = {"host": "8.8.8.8", "latency_avg_ms": 20.0, "packet_loss_percent": 0.0}
    assert analyze_result("ping", result, healthy_ping_history) is None


def test_no_anomaly_just_below_spike_threshold(healthy_ping_history):
    """Boundary case: 79% above baseline is below the 80% (1.8x) threshold."""
    result = {"host": "8.8.8.8", "latency_avg_ms": 20.0 * 1.79, "packet_loss_percent": 0.0}
    assert analyze_result("ping", result, healthy_ping_history) is None


# ── Ping: latency anomalies ───────────────────────────────────────────────────

def test_warning_for_moderate_latency_spike(healthy_ping_history):
    """100% above baseline (2x) → warning (under 150%)."""
    result = {"host": "8.8.8.8", "latency_avg_ms": 40.0, "packet_loss_percent": 0.0}
    anomaly = analyze_result("ping", result, healthy_ping_history)
    assert anomaly is not None
    assert anomaly["severity"] == "warning"
    assert anomaly["test_type"] == "ping"
    assert any("Latency" in r for r in anomaly["reasons"])


def test_critical_for_severe_latency_spike(healthy_ping_history):
    """200% above baseline → critical (over 150%)."""
    result = {"host": "8.8.8.8", "latency_avg_ms": 60.0, "packet_loss_percent": 0.0}
    anomaly = analyze_result("ping", result, healthy_ping_history)
    assert anomaly["severity"] == "critical"


def test_critical_when_host_unreachable(healthy_ping_history):
    """latency_avg_ms = None means the host did not respond at all."""
    result = {"host": "8.8.8.8", "latency_avg_ms": None, "packet_loss_percent": 100.0}
    anomaly = analyze_result("ping", result, healthy_ping_history)
    assert anomaly["severity"] == "critical"
    assert "Host unreachable" in " ".join(anomaly["reasons"])


# ── Ping: packet-loss anomalies ───────────────────────────────────────────────

def test_warning_for_moderate_packet_loss(healthy_ping_history):
    """Loss above 10% but below 50% → warning."""
    result = {"host": "8.8.8.8", "latency_avg_ms": 20.0, "packet_loss_percent": 25.0}
    anomaly = analyze_result("ping", result, healthy_ping_history)
    assert anomaly["severity"] == "warning"
    assert any("Packet loss" in r for r in anomaly["reasons"])


def test_critical_for_severe_packet_loss(healthy_ping_history):
    """Loss at or above 50% → critical."""
    result = {"host": "8.8.8.8", "latency_avg_ms": 20.0, "packet_loss_percent": 60.0}
    anomaly = analyze_result("ping", result, healthy_ping_history)
    assert anomaly["severity"] == "critical"


# ── DEF-002 REGRESSION TEST ───────────────────────────────────────────────────
# This is the bug we found: critical-latency events were being downgraded
# to warning if packet loss was also present (but only minor). The fix was
# to make severity monotonically escalate. Don't delete this test.

def test_critical_latency_is_not_downgraded_by_minor_loss(healthy_ping_history):
    """
    REGRESSION (DEF-002): Critical latency + minor (15%) packet loss must stay critical.

    Pre-fix behaviour: severity ended as 'warning' because the loss-handling
    block reassigned `severity` unconditionally. Post-fix: severity escalates only.
    """
    result = {"host": "8.8.8.8", "latency_avg_ms": 60.0, "packet_loss_percent": 15.0}
    anomaly = analyze_result("ping", result, healthy_ping_history)
    assert anomaly["severity"] == "critical", (
        "Severity downgraded from critical to warning — DEF-002 has regressed."
    )
    # Both reasons should be reported, so the user sees the full picture.
    assert len(anomaly["reasons"]) == 2


# ── Speed test anomalies ──────────────────────────────────────────────────────

def test_speed_no_anomaly_at_baseline(healthy_speed_history):
    result = {"download_mbps": 100.0, "upload_mbps": 50.0}
    assert analyze_result("speed", result, healthy_speed_history) is None


def test_speed_warning_on_moderate_download_drop(healthy_speed_history):
    """60% drop from baseline → warning (not >70%)."""
    result = {"download_mbps": 40.0, "upload_mbps": 50.0}
    anomaly = analyze_result("speed", result, healthy_speed_history)
    assert anomaly["severity"] == "warning"


def test_speed_critical_on_severe_download_drop(healthy_speed_history):
    """80% drop from baseline → critical."""
    result = {"download_mbps": 20.0, "upload_mbps": 50.0}
    anomaly = analyze_result("speed", result, healthy_speed_history)
    assert anomaly["severity"] == "critical"


def test_speed_upload_drop_alone_triggers_warning(healthy_speed_history):
    """Upload-only severe drop should flag, not silently pass."""
    result = {"download_mbps": 100.0, "upload_mbps": 10.0}
    anomaly = analyze_result("speed", result, healthy_speed_history)
    assert anomaly is not None
    assert anomaly["severity"] in ("warning", "critical")


# ── Unknown / malformed input ─────────────────────────────────────────────────

def test_unknown_test_type_returns_none(healthy_ping_history):
    """Defensive: an unsupported test_type should not raise, just return None."""
    result = {"latency_avg_ms": 500.0}
    assert analyze_result("traceroute", result, healthy_ping_history) is None

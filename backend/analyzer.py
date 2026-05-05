"""
analyzer.py — Anomaly Detection Engine
Compares current test result against historical baseline.
Detects: latency spikes, speed drops, packet loss surges.
"""

from datetime import datetime

LATENCY_SPIKE_FACTOR  = 1.8   # 80% above baseline = anomaly
SPEED_DROP_FACTOR     = 0.5   # 50% below baseline = anomaly
LOSS_THRESHOLD        = 10.0  # any loss above 10% = anomaly
MIN_HISTORY           = 5     # need at least 5 past results to analyze


def analyze_result(test_type: str, result: dict, history: list[dict]) -> dict | None:
    """
    Compare result against historical baseline.
    Returns an anomaly dict if detected, None otherwise.
    """
    if len(history) < MIN_HISTORY:
        return None  # not enough data yet

    if test_type == "ping":
        return _analyze_ping(result, history)
    if test_type == "speed":
        return _analyze_speed(result, history)
    return None


def _analyze_ping(result: dict, history: list[dict]) -> dict | None:
    past = [r for r in history if r.get("latency_avg_ms") is not None]
    if len(past) < MIN_HISTORY:
        return None

    baseline_lat  = sum(r["latency_avg_ms"]       for r in past) / len(past)
    baseline_loss = sum(r.get("packet_loss_percent", 0) for r in past) / len(past)

    current_lat  = result.get("latency_avg_ms")
    current_loss = result.get("packet_loss_percent", 0)

    severity = None
    reasons  = []

    if current_lat is None:
        severity = "critical"
        reasons.append("Host unreachable")
    else:
        if baseline_lat > 0 and current_lat > baseline_lat * LATENCY_SPIKE_FACTOR:
            pct = round((current_lat / baseline_lat - 1) * 100)
            reasons.append(f"Latency {pct}% above baseline ({round(baseline_lat,1)} ms → {current_lat} ms)")
            severity = "warning" if pct < 150 else "critical"

    if current_loss > LOSS_THRESHOLD:
        reasons.append(f"Packet loss {current_loss}% (threshold: {LOSS_THRESHOLD}%)")
        severity = "critical" if current_loss >= 50 else "warning"

    if not reasons:
        return None

    return {
        "timestamp":   datetime.now().isoformat(),
        "test_type":   "ping",
        "host":        result.get("host"),
        "severity":    severity,
        "reasons":     reasons,
        "baseline_latency_ms": round(baseline_lat, 1),
        "current_latency_ms":  current_lat,
        "baseline_loss_pct":   round(baseline_loss, 1),
        "current_loss_pct":    current_loss,
    }


def _analyze_speed(result: dict, history: list[dict]) -> dict | None:
    past = [r for r in history if r.get("download_mbps") is not None]
    if len(past) < MIN_HISTORY:
        return None

    baseline_dl = sum(r["download_mbps"] for r in past) / len(past)
    baseline_ul = sum(r.get("upload_mbps", 0) for r in past) / len(past)

    current_dl = result.get("download_mbps")
    current_ul = result.get("upload_mbps")

    reasons  = []
    severity = None

    if current_dl is not None and baseline_dl > 0:
        if current_dl < baseline_dl * SPEED_DROP_FACTOR:
            pct = round((1 - current_dl / baseline_dl) * 100)
            reasons.append(f"Download {pct}% below baseline ({round(baseline_dl,1)} → {current_dl} Mbps)")
            severity = "critical" if pct > 70 else "warning"

    if current_ul is not None and baseline_ul > 0:
        if current_ul < baseline_ul * SPEED_DROP_FACTOR:
            pct = round((1 - current_ul / baseline_ul) * 100)
            reasons.append(f"Upload {pct}% below baseline ({round(baseline_ul,1)} → {current_ul} Mbps)")
            if severity != "critical":
                severity = "warning"

    if not reasons:
        return None

    return {
        "timestamp":           datetime.now().isoformat(),
        "test_type":           "speed",
        "severity":            severity,
        "reasons":             reasons,
        "baseline_download":   round(baseline_dl, 1),
        "current_download":    current_dl,
        "baseline_upload":     round(baseline_ul, 1),
        "current_upload":      current_ul,
    }

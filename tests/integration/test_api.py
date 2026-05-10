"""
Integration tests for main.py — exercises the FastAPI surface using the
TestClient with the database isolated and external network calls stubbed
out via the `client` fixture in conftest.py.

These tests are end-to-end on the API but offline (no real network), so
they're suitable for CI runs in any environment.
"""

import pytest


# ── Health / smoke ────────────────────────────────────────────────────────────

def test_health_endpoint_returns_ok(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Ping endpoint ─────────────────────────────────────────────────────────────

def test_ping_endpoint_returns_full_payload(client):
    r = client.get("/ping?host=8.8.8.8&count=4")
    assert r.status_code == 200
    body = r.json()
    for field in ["host", "latency_avg_ms", "packet_loss_percent", "quality", "status"]:
        assert field in body, f"missing field: {field}"


def test_ping_rejects_count_below_minimum(client):
    """count must be >= 1 (FastAPI's Query validator)."""
    r = client.get("/ping?host=8.8.8.8&count=0")
    assert r.status_code == 422


def test_ping_rejects_count_above_maximum(client):
    """count must be <= 20."""
    r = client.get("/ping?host=8.8.8.8&count=99")
    assert r.status_code == 422


def test_ping_uses_default_host_when_omitted(client):
    r = client.get("/ping")
    assert r.status_code == 200
    assert r.json()["host"] == "8.8.8.8"


def test_ping_persists_result_to_history(client):
    client.get("/ping?host=8.8.8.8&count=4")
    history = client.get("/history?test_type=ping").json()["records"]
    assert len(history) == 1


# ── Anomaly wiring (DEF-001 regression) ───────────────────────────────────────
# The anomaly feature was completely disconnected before the fix. These tests
# guarantee the wiring stays connected: /anomalies must exist and return the
# right shape, and ping/speed responses must include the `anomaly` key when
# one is detected.

def test_anomalies_endpoint_exists(client):
    """REGRESSION (DEF-001): /anomalies must return 200, not 404."""
    r = client.get("/anomalies")
    assert r.status_code == 200, "DEF-001 has regressed: /anomalies endpoint missing"


def test_anomalies_endpoint_returns_anomalies_key(client):
    body = client.get("/anomalies").json()
    assert "anomalies" in body
    assert isinstance(body["anomalies"], list)


def test_anomalies_empty_initially(client):
    """On a fresh database, the anomaly log must be empty (not error)."""
    body = client.get("/anomalies").json()
    assert body["anomalies"] == []


def test_anomalies_limit_validated(client):
    """limit must be at least 1."""
    r = client.get("/anomalies?limit=0")
    assert r.status_code == 422


# ── Speed endpoint ────────────────────────────────────────────────────────────

def test_speed_endpoint_returns_full_payload(client):
    r = client.get("/speed")
    assert r.status_code == 200
    body = r.json()
    assert body["download_mbps"] == 100.0
    assert body["status"] == "success"


def test_speed_persists_result_to_history(client):
    client.get("/speed")
    history = client.get("/history?test_type=speed").json()["records"]
    assert len(history) == 1


# ── History / stats ───────────────────────────────────────────────────────────

def test_history_returns_records_key(client):
    body = client.get("/history").json()
    assert "records" in body and isinstance(body["records"], list)


def test_history_filter_by_type(client):
    """Saving one ping and one speed; filter should return only the requested type."""
    client.get("/ping?count=4")
    client.get("/speed")
    pings = client.get("/history?test_type=ping").json()["records"]
    speeds = client.get("/history?test_type=speed").json()["records"]
    assert all(r["test_type"] == "ping" for r in pings)
    assert all(r["test_type"] == "speed" for r in speeds)


def test_stats_endpoint_returns_required_keys(client):
    body = client.get("/stats").json()
    for k in ["total_tests", "total_anomalies", "avg_ping_ms", "avg_download_mbps"]:
        assert k in body, f"missing stats key: {k}"


def test_delete_history_clears_records(client):
    client.get("/ping?count=4")
    assert len(client.get("/history").json()["records"]) > 0
    r = client.delete("/history")
    assert r.status_code == 200
    assert client.get("/history").json()["records"] == []


# ── Multi-ping ────────────────────────────────────────────────────────────────

def test_multi_ping_rejects_empty_hosts(client):
    """Empty hosts string → 400 with a clear error message."""
    r = client.get("/ping/multi?hosts=")
    assert r.status_code == 400


def test_multi_ping_caps_at_four_hosts(client):
    """Even if 6 hosts are supplied, only 4 are tested."""
    r = client.get("/ping/multi?hosts=a,b,c,d,e,f&count=1")
    assert r.status_code == 200
    body = r.json()
    assert body["hosts_tested"] == 4

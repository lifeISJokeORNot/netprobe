"""
Unit tests for database.py — the SQLite persistence layer.

All tests use the `tmp_db` fixture from conftest.py, which monkeypatches
DB_PATH to a per-test temporary file. Tests are therefore fully isolated
and never touch the real results.db.
"""

import sqlite3
import database


def test_init_creates_results_table(tmp_db):
    with sqlite3.connect(tmp_db) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    table_names = {r[0] for r in rows}
    assert "results" in table_names


def test_init_creates_anomalies_table(tmp_db):
    with sqlite3.connect(tmp_db) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    assert "anomalies" in {r[0] for r in rows}


def test_init_is_idempotent(tmp_db):
    """Calling init_db twice should not raise — important for app reloads."""
    database.init_db()      # already called once by the fixture
    database.init_db()      # should be a no-op


def test_save_and_retrieve_ping_result(tmp_db):
    payload = {"host": "8.8.8.8", "latency_avg_ms": 22.5, "timestamp": "2025-01-01T10:00:00"}
    database.save_result("ping", payload)
    history = database.get_history(test_type="ping")
    assert len(history) == 1
    assert history[0]["host"] == "8.8.8.8"
    assert history[0]["latency_avg_ms"] == 22.5
    assert history[0]["test_type"] == "ping"


def test_save_and_retrieve_speed_result(tmp_db):
    payload = {"download_mbps": 100.0, "upload_mbps": 50.0, "timestamp": "2025-01-01T10:00:00"}
    database.save_result("speed", payload)
    history = database.get_history(test_type="speed")
    assert len(history) == 1
    assert history[0]["download_mbps"] == 100.0


def test_get_history_filters_by_test_type(tmp_db):
    database.save_result("ping", {"latency_avg_ms": 20.0})
    database.save_result("ping", {"latency_avg_ms": 30.0})
    database.save_result("speed", {"download_mbps": 100.0})

    pings = database.get_history(test_type="ping")
    speeds = database.get_history(test_type="speed")
    everything = database.get_history()

    assert len(pings) == 2
    assert len(speeds) == 1
    assert len(everything) == 3


def test_get_history_respects_limit(tmp_db):
    for i in range(20):
        database.save_result("ping", {"latency_avg_ms": float(i)})
    history = database.get_history(test_type="ping", limit=5)
    assert len(history) == 5


def test_get_history_returns_newest_first(tmp_db):
    """Newest record (id=N) should appear before older ones (id<N)."""
    database.save_result("ping", {"latency_avg_ms": 10.0, "timestamp": "2025-01-01"})
    database.save_result("ping", {"latency_avg_ms": 99.0, "timestamp": "2025-01-02"})
    history = database.get_history(test_type="ping")
    assert history[0]["latency_avg_ms"] == 99.0
    assert history[1]["latency_avg_ms"] == 10.0


def test_save_anomaly_persists(tmp_db):
    anomaly = {
        "timestamp": "2025-01-01T12:00:00",
        "test_type": "ping",
        "severity": "critical",
        "reasons": ["Latency 200% above baseline"],
    }
    database.save_anomaly(anomaly)
    log = database.get_anomaly_log()
    assert len(log) == 1
    assert log[0]["severity"] == "critical"
    assert log[0]["test_type"] == "ping"


def test_delete_history_specific_type(tmp_db):
    database.save_result("ping", {"latency_avg_ms": 20.0})
    database.save_result("speed", {"download_mbps": 100.0})
    database.delete_history(test_type="ping")

    assert database.get_history(test_type="ping") == []
    assert len(database.get_history(test_type="speed")) == 1


def test_delete_history_all(tmp_db):
    database.save_result("ping", {"latency_avg_ms": 20.0})
    database.save_result("speed", {"download_mbps": 100.0})
    database.delete_history()
    assert database.get_history() == []


def test_stats_summary_with_empty_db(tmp_db):
    """Empty DB must not crash — averages should be None, counts zero."""
    stats = database.get_stats_summary()
    assert stats["total_tests"] == 0
    assert stats["total_anomalies"] == 0
    assert stats["avg_ping_ms"] is None
    assert stats["avg_download_mbps"] is None


def test_stats_summary_aggregates_correctly(tmp_db):
    database.save_result("ping", {"latency_avg_ms": 10.0, "packet_loss_percent": 0.0})
    database.save_result("ping", {"latency_avg_ms": 20.0, "packet_loss_percent": 0.0})
    database.save_result("ping", {"latency_avg_ms": 30.0, "packet_loss_percent": 0.0})
    stats = database.get_stats_summary()
    assert stats["total_tests"] == 3
    assert stats["avg_ping_ms"] == 20.0      # (10+20+30)/3
    assert stats["best_ping_ms"] == 10.0     # smallest is best for ping

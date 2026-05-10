"""
Shared pytest fixtures for the NetProbe test suite.

Why this file exists:
- Adds backend/ to sys.path so tests can `import analyzer`, `import database`, etc.
  without needing to modify the application code.
- Provides reusable fixtures (tmp DB, sample baselines, FastAPI client) to keep
  individual test files focused on assertions rather than setup.
"""

import sys
from pathlib import Path

# Make backend/ importable from anywhere in the test suite.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import pytest


# ── Database fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """
    Replace the production DB_PATH with a per-test temporary file and initialise it.

    Tests that touch the database get an isolated, empty SQLite file every time —
    no test pollution, no cleanup needed.
    """
    import database
    db_file = tmp_path / "test_results.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    database.init_db()
    return db_file


# ── Sample baselines for the analyzer ─────────────────────────────────────────

@pytest.fixture
def healthy_ping_history():
    """Five clean ping results: 20 ms latency, 0% loss. Used as a stable baseline."""
    return [
        {"latency_avg_ms": 20.0, "packet_loss_percent": 0.0, "host": "8.8.8.8"}
        for _ in range(5)
    ]


@pytest.fixture
def healthy_speed_history():
    """Five clean speed results: 100 Mbps down, 50 Mbps up. Used as a stable baseline."""
    return [
        {"download_mbps": 100.0, "upload_mbps": 50.0}
        for _ in range(5)
    ]


# ── FastAPI test client ───────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_db, monkeypatch):
    """
    A TestClient with the database isolated and external network calls stubbed.

    Tests using this fixture can hit the real FastAPI app without making any
    real network requests — ping/speed are replaced with fast deterministic
    fakes so the suite stays fast and offline-runnable (important for CI).
    """
    import tester

    def fake_ping(host="8.8.8.8", count=4):
        return {
            "timestamp": "2025-01-01T00:00:00",
            "host": host,
            "packets_sent": count,
            "packets_received": count,
            "packet_loss_percent": 0.0,
            "latency_min_ms": 19.0,
            "latency_avg_ms": 20.0,
            "latency_max_ms": 22.0,
            "latency_jitter_ms": 3.0,
            "quality": {"score": 95, "grade": "A", "label": "Excellent"},
            "status": "success",
        }

    def fake_speed():
        return {
            "timestamp": "2025-01-01T00:00:00",
            "download_mbps": 100.0,
            "upload_mbps": 50.0,
            "ping_ms": 12.0,
            "server_name": "Test Server",
            "server_country": "TR",
            "server_sponsor": "Test ISP",
            "status": "success",
        }

    monkeypatch.setattr(tester, "run_ping_test", fake_ping)
    monkeypatch.setattr(tester, "run_speed_test", fake_speed)

    # Patch the names imported into main as well — `from tester import ...` binds
    # the name into main's module namespace, so monkeypatching `tester.run_ping_test`
    # alone wouldn't affect what main actually calls.
    import main
    monkeypatch.setattr(main, "run_ping_test", fake_ping)
    monkeypatch.setattr(main, "run_speed_test", fake_speed)

    from fastapi.testclient import TestClient
    return TestClient(main.app)

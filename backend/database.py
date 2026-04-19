"""
database.py — SQLite storage for test results.
Called by main.py to save and retrieve ping/speed history.

No extra dependencies needed — sqlite3 is part of Python's standard library.
"""

import sqlite3
import json
from datetime import datetime

DB_PATH = "results.db"  # created in the same folder as main.py


# ── Setup ─────────────────────────────────────────────────────────────────────

def init_db():
    """
    Create the results table if it doesn't exist yet.
    Called once on server startup from main.py.
    """
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                test_type   TEXT    NOT NULL,          -- 'ping' or 'speed'
                timestamp   TEXT    NOT NULL,          -- ISO datetime string
                data        TEXT    NOT NULL           -- full result as JSON
            )
        """)
        conn.commit()


# ── Write ─────────────────────────────────────────────────────────────────────

def save_result(test_type: str, result: dict):
    """
    Save a test result to the database.

    - test_type : 'ping' or 'speed'
    - result    : the dict returned by tester.py functions
    """
    timestamp = result.get("timestamp", datetime.now().isoformat())
    data_json = json.dumps(result)

    with _connect() as conn:
        conn.execute(
            "INSERT INTO results (test_type, timestamp, data) VALUES (?, ?, ?)",
            (test_type, timestamp, data_json),
        )
        conn.commit()


# ── Read ──────────────────────────────────────────────────────────────────────

def get_history(test_type: str = None, limit: int = 50) -> list[dict]:
    """
    Retrieve past results from the database.

    - test_type : optional filter ('ping' or 'speed'). None = return all.
    - limit     : max number of rows (most recent first).

    Returns a list of dicts, each containing:
        id, test_type, timestamp, and all fields from the original result.
    """
    with _connect() as conn:
        if test_type:
            cursor = conn.execute(
                """
                SELECT id, test_type, timestamp, data
                FROM results
                WHERE test_type = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (test_type, limit),
            )
        else:
            cursor = conn.execute(
                """
                SELECT id, test_type, timestamp, data
                FROM results
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )

        rows = cursor.fetchall()

    records = []
    for row in rows:
        record = {
            "id": row[0],
            "test_type": row[1],
            "timestamp": row[2],
        }
        # Merge the stored JSON fields directly into the record
        try:
            record.update(json.loads(row[3]))
        except json.JSONDecodeError:
            record["raw"] = row[3]   # fallback: expose raw string

        records.append(record)

    return records


def delete_history(test_type: str = None):
    """
    Delete stored results.
    Useful for a 'Clear history' button in the dashboard later.

    - test_type : if provided, deletes only that type. None = delete everything.
    """
    with _connect() as conn:
        if test_type:
            conn.execute("DELETE FROM results WHERE test_type = ?", (test_type,))
        else:
            conn.execute("DELETE FROM results")
        conn.commit()


def get_stats_summary() -> dict:
    """
    Return quick aggregate stats for the dashboard header/summary cards.
    e.g. average ping latency and average download speed across all saved tests.
    """
    with _connect() as conn:
        # Average ping latency
        ping_cursor = conn.execute(
            "SELECT data FROM results WHERE test_type = 'ping' ORDER BY id DESC LIMIT 20"
        )
        ping_rows = ping_cursor.fetchall()

        # Average speed
        speed_cursor = conn.execute(
            "SELECT data FROM results WHERE test_type = 'speed' ORDER BY id DESC LIMIT 10"
        )
        speed_rows = speed_cursor.fetchall()

    # Compute averages from stored JSON
    ping_avgs = []
    for row in ping_rows:
        try:
            data = json.loads(row[0])
            val = data.get("latency_avg_ms")
            if val is not None:
                ping_avgs.append(val)
        except json.JSONDecodeError:
            continue

    download_avgs = []
    upload_avgs = []
    for row in speed_rows:
        try:
            data = json.loads(row[0])
            dl = data.get("download_mbps")
            ul = data.get("upload_mbps")
            if dl is not None:
                download_avgs.append(dl)
            if ul is not None:
                upload_avgs.append(ul)
        except json.JSONDecodeError:
            continue

    def avg(lst):
        return round(sum(lst) / len(lst), 2) if lst else None

    return {
        "avg_ping_ms": avg(ping_avgs),
        "avg_download_mbps": avg(download_avgs),
        "avg_upload_mbps": avg(upload_avgs),
        "total_ping_tests": len(ping_avgs),
        "total_speed_tests": len(download_avgs),
    }


# ── Internal ──────────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    """Open a connection to the SQLite database file."""
    return sqlite3.connect(DB_PATH)

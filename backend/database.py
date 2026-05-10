"""
database.py — SQLite storage (v2)
BUG FIX: check_same_thread=False added for multi-threaded FastAPI use.
New: anomaly log table.
"""

import sqlite3, json
from datetime import datetime

DB_PATH = "results.db"

def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                data TEXT NOT NULL
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                test_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                data TEXT NOT NULL
            )""")
        conn.commit()

def save_result(test_type, result):
    ts = result.get("timestamp", datetime.now().isoformat())
    with _connect() as conn:
        conn.execute("INSERT INTO results (test_type, timestamp, data) VALUES (?,?,?)",
                     (test_type, ts, json.dumps(result)))
        conn.commit()

def save_anomaly(anomaly):
    with _connect() as conn:
        conn.execute("INSERT INTO anomalies (timestamp, test_type, severity, data) VALUES (?,?,?,?)",
                     (anomaly["timestamp"], anomaly["test_type"], anomaly["severity"], json.dumps(anomaly)))
        conn.commit()

def get_history(test_type=None, limit=50):
    with _connect() as conn:
        if test_type:
            rows = conn.execute("SELECT id,test_type,timestamp,data FROM results WHERE test_type=? ORDER BY id DESC LIMIT ?", (test_type, limit)).fetchall()
        else:
            rows = conn.execute("SELECT id,test_type,timestamp,data FROM results ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    records = []
    for row in rows:
        r = {"id": row[0], "test_type": row[1], "timestamp": row[2]}
        try: r.update(json.loads(row[3]))
        except: r["raw"] = row[3]
        records.append(r)
    return records

def get_anomaly_log(limit=20):
    with _connect() as conn:
        rows = conn.execute("SELECT id,timestamp,test_type,severity,data FROM anomalies ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    records = []
    for row in rows:
        r = {"id": row[0], "timestamp": row[1], "test_type": row[2], "severity": row[3]}
        try: r.update(json.loads(row[4]))
        except: pass
        records.append(r)
    return records

def get_stats_summary():
    with _connect() as conn:
        ping_rows  = conn.execute("SELECT data FROM results WHERE test_type='ping'  ORDER BY id DESC LIMIT 50").fetchall()
        speed_rows = conn.execute("SELECT data FROM results WHERE test_type='speed' ORDER BY id DESC LIMIT 20").fetchall()
        total      = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
        anomaly_ct = conn.execute("SELECT COUNT(*) FROM anomalies").fetchone()[0]

    def _parse(rows):
        out = []
        for row in rows:
            try: out.append(json.loads(row[0]))
            except: pass
        return out

    pings, speeds = _parse(ping_rows), _parse(speed_rows)

    def avg(lst):
        lst = [x for x in lst if x is not None]
        return round(sum(lst)/len(lst), 2) if lst else None

    return {
        "total_tests":       total,
        "total_anomalies":   anomaly_ct,
        "avg_ping_ms":       avg([p.get("latency_avg_ms") for p in pings]),
        "avg_packet_loss":   avg([p.get("packet_loss_percent") for p in pings]),
        "avg_quality_score": avg([p.get("quality", {}).get("score") for p in pings]),
        "avg_download_mbps": avg([s.get("download_mbps") for s in speeds]),
        "avg_upload_mbps":   avg([s.get("upload_mbps")   for s in speeds]),
        "best_download_mbps": max((s.get("download_mbps") for s in speeds if s.get("download_mbps")), default=None),
        "best_ping_ms":       min((p.get("latency_avg_ms") for p in pings  if p.get("latency_avg_ms")), default=None),
    }

def delete_history(test_type=None):
    with _connect() as conn:
        if test_type: conn.execute("DELETE FROM results WHERE test_type=?", (test_type,))
        else:         conn.execute("DELETE FROM results")
        conn.commit()

def _connect():
    # BUG FIX: check_same_thread=False required for FastAPI's multi-threaded env
    return sqlite3.connect(DB_PATH, check_same_thread=False)

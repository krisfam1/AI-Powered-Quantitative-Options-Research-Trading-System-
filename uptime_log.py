from dotenv import load_dotenv
load_dotenv()

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = "uptime_log.db"


def init_uptime_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS heartbeats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)


def log_heartbeat(service: str) -> None:
    """Record a single heartbeat -- call this once per loop iteration."""
    init_uptime_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO heartbeats (service, timestamp) VALUES (?, ?)",
            (service, datetime.now(timezone.utc).isoformat()),
        )


def get_downtime_gaps(service: str, gap_threshold_minutes: int = 10) -> list[dict]:
    """
    Analyze heartbeat history to find real gaps (likely downtime) larger
    than the threshold.
    """
    init_uptime_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT timestamp FROM heartbeats WHERE service = ? ORDER BY timestamp ASC",
            (service,),
        ).fetchall()

    if len(rows) < 2:
        return []

    gaps = []
    for i in range(1, len(rows)):
        prev = datetime.fromisoformat(rows[i - 1][0])
        curr = datetime.fromisoformat(rows[i][0])
        gap_minutes = (curr - prev).total_seconds() / 60
        if gap_minutes >= gap_threshold_minutes:
            gaps.append({
                "gap_start": rows[i - 1][0],
                "gap_end": rows[i][0],
                "gap_minutes": round(gap_minutes, 1),
            })

    return gaps


if __name__ == "__main__":
    log_heartbeat("test_service")
    print("Heartbeat logged.")
    gaps = get_downtime_gaps("test_service")
    print("Downtime gaps found: " + str(len(gaps)))
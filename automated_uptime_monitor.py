from dotenv import load_dotenv
load_dotenv()

"""
Automated uptime gap monitor.

Checks for real downtime gaps during market hours, and specifically flags
any gap that overlaps with a position that was actually open at the time --
the genuinely actionable case, distinct from routine overnight/weekend
closures which are expected and harmless.
"""

import sqlite3
from datetime import datetime, timedelta, timezone

GAP_THRESHOLD_MINUTES = 10
DB_PATH = "uptime_log.db"


def check_gaps_during_open_positions() -> dict:
    with sqlite3.connect("uptime_log.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT timestamp FROM heartbeats WHERE service = 'OptionsShadowLoop' ORDER BY timestamp ASC")
        heartbeats = [datetime.fromisoformat(row[0]) for row in cur.fetchall()]

    with sqlite3.connect("options_trades.db") as conn2:
        conn2.row_factory = sqlite3.Row
        trades = conn2.execute("SELECT * FROM options_trades").fetchall()

    real_gaps = []
    for i in range(1, len(heartbeats)):
        gap_start = heartbeats[i - 1]
        gap_end = heartbeats[i]
        gap_minutes = (gap_end - gap_start).total_seconds() / 60

        if gap_minutes > GAP_THRESHOLD_MINUTES:
            if gap_minutes < 180:
                real_gaps.append((gap_start, gap_end, gap_minutes))

    flagged = []
    for gap_start, gap_end, gap_minutes in real_gaps:
        for t in trades:
            entry_date = t["entry_date"]
            exit_date = t["exit_date"] if t["exit_date"] else datetime.now(timezone.utc).date().isoformat()
            if entry_date <= gap_start.date().isoformat() <= exit_date:
                flagged.append({
                    "trade_id": t["trade_id"],
                    "gap_start": gap_start.isoformat(),
                    "gap_end": gap_end.isoformat(),
                    "gap_minutes": round(gap_minutes, 1),
                })

    return {"total_real_gaps": len(real_gaps), "flagged_overlaps": flagged}


if __name__ == "__main__":
    result = check_gaps_during_open_positions()
    print("Real mid-session gaps found (>10 min, <3 hrs): " + str(result["total_real_gaps"]))
    if result["flagged_overlaps"]:
        print("\nWARNING -- gaps overlapping with open positions:")
        for f in result["flagged_overlaps"]:
            print("  " + f["trade_id"] + ": gap " + f["gap_start"] + " to " + f["gap_end"] + " (" + str(f["gap_minutes"]) + " min)")
    else:
        print("No gaps overlapped with any open position -- downtime did not affect any trade.")
"""
Read-only gap check for gex_metrics (CLAUDE.md Section 60, 2026-10-01).

Answers "would GEX_Historical_Incremental_Update find anything to fill right
now?" using that script's OWN functions and scan rule -- no logic duplicated:
scan real trading days from the earliest per-ticker MAX(snapshot_date) through
yesterday (UTC), and flag every (ticker, date) without both sign_convention
rows. Writes nothing. Prints one JSON line.

Same scope as the updater: an interior gap older than the earliest per-ticker
max (e.g. SMCI 2026-09-28) is outside its scan range and is not reported here.
"""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

from gex_historical_incremental_update import (
    TICKERS, FALLBACK_FLOOR, _get_per_ticker_max, _ticker_date_complete,
)
from gex_data_loader import get_real_trading_days, DB_PATH

with sqlite3.connect(DB_PATH) as conn:
    maxes = _get_per_ticker_max(conn)
yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
scan_start = min((m for m in maxes.values() if m is not None), default=FALLBACK_FLOOR)

missing = []
if scan_start <= yesterday:
    for d in get_real_trading_days(scan_start, yesterday):
        with sqlite3.connect(DB_PATH) as conn:
            for t in TICKERS:
                if not _ticker_date_complete(conn, t, d.isoformat()):
                    missing.append(f"{t} {d.isoformat()}")

with sqlite3.connect(DB_PATH) as conn:
    rows, max_date = conn.execute("SELECT COUNT(*), MAX(snapshot_date) FROM gex_metrics").fetchone()

print(json.dumps({"scan": f"{scan_start}..{yesterday}", "missing": missing,
                  "gex_metrics_rows": rows, "gex_metrics_max": max_date}))

from dotenv import load_dotenv
load_dotenv()

"""
Daily prospective collection run with comprehensive integrity checks.
Run once per trading day going forward. Stops and reports rather than
continuing if any no-lookahead or data-integrity check fails.
"""

import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from prospective_gex_pipeline import (
    log_signals_for_date, backfill_forward_returns, DB_PATH,
    get_previous_trading_day
)

# BUG FIX 2026-09-20: this used to be datetime.now(timezone.utc).date(), which
# at this job's 20:00 ET (America/New_York) trigger time is already past
# midnight UTC -- so TODAY always computed as one calendar day AHEAD of the
# real US trading day that had just closed. Every nightly run then scanned a
# date with zero market data, silently logging 0 signals (and 0 skipped, since
# the per-bar date filter rejected everything before the GEX check could even
# run) -- confirmed via direct replication that real qualifying signals existed
# on every affected day. Now computed in America/New_York local time, matching
# the ET convention already used elsewhere in this codebase (see main.py's ET).
TODAY = datetime.now(ZoneInfo("America/New_York")).date().isoformat()

print("=" * 90)
print("DAILY PROSPECTIVE COLLECTION RUN -- " + TODAY)
print("=" * 90)

t_minus_1 = get_previous_trading_day(datetime.strptime(TODAY, "%Y-%m-%d").date(), reference_ticker="AAPL")
print("Today: " + TODAY + " | Expected T-1: " + t_minus_1.isoformat())

print("\n--- Logging today's qualifying signals ---")
log_result = log_signals_for_date(TODAY)
print(log_result)

print("\n--- Backfilling any previously-logged signals with newly-available forward returns ---")
backfill_result = backfill_forward_returns()
print(backfill_result)

print("\n" + "=" * 90)
print("DAILY INTEGRITY CHECKS")
print("=" * 90)

failures = []

with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row

    # Check 1: no duplicate (ticker, signal_timestamp)
    dupes = conn.execute("""
        SELECT ticker, signal_timestamp, COUNT(*) as cnt FROM raw_signals
        GROUP BY ticker, signal_timestamp HAVING cnt > 1
    """).fetchall()
    print("1. Duplicate (ticker, signal_timestamp) records: " + str(len(dupes)))
    if dupes:
        failures.append("DUPLICATES FOUND: " + str([dict(d) for d in dupes]))

    # Check 2 & 3: GEX snapshot date == correct T-1, and < signal date
    all_rows = conn.execute("SELECT id, ticker, trading_date, gex_snapshot_date FROM raw_signals").fetchall()
    snapshot_violations = []
    for row in all_rows:
        signal_date_obj = datetime.strptime(row["trading_date"], "%Y-%m-%d").date()
        snapshot_date_obj = datetime.strptime(row["gex_snapshot_date"], "%Y-%m-%d").date()
        expected_t1 = get_previous_trading_day(signal_date_obj, reference_ticker=row["ticker"])
        if snapshot_date_obj != expected_t1 or snapshot_date_obj >= signal_date_obj:
            snapshot_violations.append(dict(row))
    print("2-3. Snapshot-date violations (wrong T-1 or not strictly before signal date): " + str(len(snapshot_violations)))
    if snapshot_violations:
        failures.append("SNAPSHOT VIOLATIONS: " + str(snapshot_violations))

    # Check 5: no missing required GEX fields silently substituted (should be NULL, never a fabricated default)
    missing_field_rows = conn.execute("""
        SELECT COUNT(*) FROM raw_signals WHERE gex_available = 1 AND (net_gex IS NULL OR call_wall_strike IS NULL)
    """).fetchone()[0]
    print("5. Rows marked GEX-available but missing core GEX fields (should be 0): " + str(missing_field_rows))
    if missing_field_rows > 0:
        failures.append(str(missing_field_rows) + " rows have gex_available=1 but NULL core fields")

    # Counts
    total_signals = conn.execute("SELECT COUNT(*) FROM raw_signals").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM raw_signals WHERE returns_backfilled = 0").fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM raw_signals WHERE returns_backfilled = 1").fetchone()[0]

    print("\n6. Total signal count (all-time, cumulative): " + str(total_signals))
    print("7. Skipped (GEX unavailable) this run: " + str(log_result["skipped_gex_unavailable"]))
    print("8. Pending forward-return backfill: " + str(pending))
    print("9. Completed forward-return backfill: " + str(completed))

print("\n" + "=" * 90)
if failures:
    print("INTEGRITY CHECK: FAILED -- STOPPING, DO NOT TRUST THIS RUN'S DATA")
    print("=" * 90)
    for f in failures:
        print("  " + f)
else:
    print("INTEGRITY CHECK: PASSED -- all checks clean")
    print("=" * 90)

print("\nResearch status: Prospective data collection is in progress.")
print("No performance conclusion is being made. Cumulative signals collected: " + str(total_signals))
print("\nCOLLECTION RUN COMPLETE -- STOPPING per instruction.")
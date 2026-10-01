from dotenv import load_dotenv
load_dotenv()

"""
Incremental historical GEX updater. Added 2026-09-22, revised same day
after the first run crashed on a transient local network/DNS outage.

BACKGROUND: gex_data_loader.py's historical batch run was an intentional,
FROZEN, fixed-window research dataset (TRAIN_START/TRAIN_END/HOLDOUT_END
constants, aligned to V1's own frozen backtest window) -- not a bug, not
a forgotten job. It was never meant to be an ongoing pipeline, and has
correctly never been touched since. This file does NOT modify
gex_data_loader.py or gex_calculator.py, and does NOT touch their
TRAIN_START/HOLDOUT_END constants -- those stay exactly as they are.

This is a NEW, separate, self-healing INCREMENTAL script that reuses
process_ticker_day() (gex_data_loader.py) and calculate_gex_for_ticker_day()
(gex_calculator.py) AS-IS, unmodified.

REVISION NOTE (2026-09-22, same day): the first version tracked only a
single GLOBAL MAX(snapshot_date) to decide what's "done". A run that
night hit a real, transient local network/DNS outage (affecting both
EODHD and Alpaca connections intermittently -- confirmed by many
successful calls interleaved with many failures in the same run, not an
EODHD-side problem) and crashed uncaught partway through, leaving several
dates with PARTIAL ticker coverage (e.g. 2026-09-09 only got 3 of 6
tickers). A global-max design would have silently never retried those
missing tickers on subsequent runs, since the global max would already
be past their date. Fixed here: completeness is tracked PER (ticker,
date) pair -- both sign_convention rows must exist for a (ticker, date)
to count as done -- and calculate_gex_for_ticker_day() is now wrapped in
its own try/except (process_ticker_day() already has one internally) so
a single transient failure logs and continues rather than crashing the
whole run. One retry with a short delay is attempted for connection-type
errors specifically, before giving up on that (ticker, date) for this run
and leaving it for the next one.

Always targets T-1 or earlier (never same-day) -- EODHD's real publishing
lag was directly observed this session to exceed same-day, and even
next-morning same-day-minus-one can be unavailable. Never fabricates --
a ticker-day with no real data available yet simply produces zero rows
and is picked up on a later run once EODHD actually publishes it.
"""

import sys
import os
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, r"C:\Users\fmkri\Downloads\Python-Backend\Python-Backend")
os.chdir(r"C:\Users\fmkri\Downloads\Python-Backend\Python-Backend")

import sqlite3
from gex_data_loader import process_ticker_day, get_real_trading_days, DB_PATH
from gex_calculator import calculate_gex_for_ticker_day

TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR", "SPY"]
# SPY added 2026-09-24, AFTER its dedicated one-time historical backfill
# (gex_spy_historical_backfill.py) completed and was independently verified
# (142 rows, 71/71 target days, 2026-06-10 to 2026-09-21, no gaps, no
# pagination truncation -- CLAUDE.md Section 43). SPY was deliberately
# excluded from this list during the initial backfill design because this
# script's scan-start logic (_get_per_ticker_max, below) derives from the
# MINIMUM of existing tickers' own maxes -- adding a brand-new ticker with
# no prior data (max=None) would only have scanned forward from the OTHER
# tickers' shared recent max, never triggering a genuine historical build
# for SPY. That blocker no longer applies now that SPY has a real,
# populated max date matching the other tickers' own recent state -- this
# script's ordinary per-(ticker,date) completeness logic now handles SPY
# exactly like the other six, no special-casing needed.
FALLBACK_FLOOR = "2026-09-09"  # only used if a ticker somehow has zero rows in the whole table yet


def _get_per_ticker_max(conn):
    maxes = {}
    for ticker in TICKERS:
        row = conn.execute("SELECT MAX(snapshot_date) as mx FROM gex_metrics WHERE ticker=?", (ticker,)).fetchone()
        maxes[ticker] = row[0]
    return maxes


def _ticker_date_complete(conn, ticker, date_str):
    row = conn.execute(
        "SELECT COUNT(DISTINCT sign_convention) as n FROM gex_metrics WHERE ticker=? AND snapshot_date=?",
        (ticker, date_str)
    ).fetchone()
    return row[0] >= 2  # both model_a and flipped


def run_incremental_update():
    print("=" * 100)
    print("INCREMENTAL HISTORICAL GEX UPDATE -- " + datetime.now(timezone.utc).isoformat())
    print("=" * 100)

    with sqlite3.connect(DB_PATH) as conn:
        per_ticker_max = _get_per_ticker_max(conn)
    print("Current per-ticker MAX(snapshot_date):")
    for t, mx in per_ticker_max.items():
        print("  " + t + ": " + str(mx))

    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    earliest_start = min((mx for mx in per_ticker_max.values() if mx is not None), default=FALLBACK_FLOOR)
    scan_start = (datetime.strptime(earliest_start, "%Y-%m-%d").date()).isoformat()  # re-scan from the earliest ticker's own max (inclusive) to catch partial days

    if scan_start > yesterday:
        print("Nothing to scan (earliest ticker max is already >= yesterday). Done.")
        return {"attempted": [], "note": "already_up_to_date"}

    print("Scanning real trading days from " + scan_start + " through " + yesterday + " for any (ticker, date) gaps...")
    trading_days = None
    for attempt in range(3):
        try:
            trading_days = get_real_trading_days(scan_start, yesterday)
            break
        except Exception as exc:
            print("  get_real_trading_days failed (attempt " + str(attempt + 1) + "/3): " + str(exc)[:150])
            if attempt < 2:
                time.sleep(10)
    if trading_days is None:
        print("Could not determine the trading-day calendar after 3 attempts -- network still unstable. Stopping this run cleanly, nothing corrupted, safe to re-run later.")
        return {"attempted": [], "error": "trading_calendar_unavailable"}
    print("Found " + str(len(trading_days)) + " real trading day(s) in range: " + str(trading_days))

    filled = []
    still_missing = []
    for d in trading_days:
        date_str = d.isoformat()
        for ticker in TICKERS:
            with sqlite3.connect(DB_PATH) as conn:
                already_done = _ticker_date_complete(conn, ticker, date_str)
            if already_done:
                continue  # this exact (ticker, date) is already fully populated, skip

            summary = process_ticker_day(ticker, date_str)
            if summary["contracts_retained"] == 0:
                print("  " + ticker + " " + date_str + ": 0 contracts (not published yet or genuinely excluded) errors=" + str(summary["errors"]))
                still_missing.append((ticker, date_str))
                continue

            success = False
            last_exc = None
            for attempt in range(2):  # one retry on a transient connection error
                try:
                    results = calculate_gex_for_ticker_day(ticker, date_str)
                    success = bool(results)
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt == 0:
                        print("  " + ticker + " " + date_str + ": calculate_gex_for_ticker_day failed (" + str(exc)[:120] + "...), retrying once in 5s")
                        time.sleep(5)
                    else:
                        print("  " + ticker + " " + date_str + ": calculate_gex_for_ticker_day failed twice, giving up this run: " + str(exc)[:200])

            if success:
                filled.append((ticker, date_str))
                print("  " + ticker + " " + date_str + ": OK, GEX computed and stored (contracts_retained=" + str(summary["contracts_retained"]) + ")")
            else:
                still_missing.append((ticker, date_str))

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT MIN(snapshot_date) as mn, MAX(snapshot_date) as mx, COUNT(*) as n FROM gex_metrics").fetchone()
        final_min, final_max, final_count = row[0], row[1], row[2]
        per_ticker_max_after = _get_per_ticker_max(conn)

    print("\n" + "=" * 100)
    print("RESULT")
    print("=" * 100)
    print("(ticker, date) pairs newly filled this run: " + str(len(filled)))
    for t, d in filled:
        print("  + " + t + " " + d)
    print("(ticker, date) pairs still missing after this run: " + str(len(still_missing)))
    for t, d in still_missing:
        print("  - " + t + " " + d)
    print("\ngex_metrics overall range now: " + str(final_min) + " to " + str(final_max) + ", " + str(final_count) + " total rows")
    print("Per-ticker MAX(snapshot_date) now:")
    for t, mx in per_ticker_max_after.items():
        print("  " + t + ": " + str(mx))

    return {
        "filled": filled, "still_missing": still_missing,
        "final_min": final_min, "final_max": final_max, "final_count": final_count,
        "per_ticker_max_after": per_ticker_max_after,
    }


if __name__ == "__main__":
    run_incremental_update()

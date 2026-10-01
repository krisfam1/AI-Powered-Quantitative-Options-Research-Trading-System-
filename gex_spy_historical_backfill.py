from dotenv import load_dotenv
load_dotenv()

"""
One-time historical GEX backfill for SPY -- dedicated script, per explicit
instruction. Does NOT add SPY to gex_historical_incremental_update.py's
TICKERS list (that script's scan-start logic derives from the MINIMUM of
existing tickers' own per-ticker maxes, so adding a brand-new ticker there
would only scan forward from the other tickers' shared recent max, not
trigger a genuine full historical build for SPY -- already scoped and
confirmed in the prior session pass).

Reuses process_ticker_day() (gex_data_loader.py) and
calculate_gex_for_ticker_day() (gex_calculator.py) UNMODIFIED -- same
two functions the original 6-stock historical build and the later
incremental updater both used, unchanged.

PAGINATION: process_ticker_day() -> _fetch_raw_chain_paginated() already
implements correct, real pagination (follows JSON:API links.next as the
primary mechanism, with the token-reattachment fix already applied;
falls back to page[offset] increment only when links is empty; a 20-page
circuit breaker; explicitly returns pagination_complete + pages_requested
+ records_retrieved for every call) -- confirmed by direct code read
before writing this script, not assumed. This is NOT the same buggy
pattern found earlier this session in an unrelated one-off diagnostic
script (diagnose_expiration_existence.py's fetch_all_real_expirations(),
which incorrectly checked a client-side type-filtered count instead of
the raw response count). Since SPY's chain is confirmed materially
deeper than the 6-stock universe (a single unfiltered test query already
filled a 1000-record page before reaching near-term expirations), this
script explicitly surfaces pagination_complete/pages_requested for every
single (ticker, date) below and flags any day that hits the 20-page cap,
rather than silently trusting "some records came back."

Target window: 2026-06-10 through 2026-09-21 -- deliberately matching
the 6-stock table's original historical range exactly, for comparability
(per explicit instruction), even though the live 6-stock table has since
grown one day further (to 2026-09-22) via separate incremental-update
work. Not extended here.

Resilience: wraps get_real_trading_days() and calculate_gex_for_ticker_day()
in retry logic, matching the lesson already learned and applied in
gex_historical_incremental_update.py (Section 40) after two real
transient-network crashes during the original 6-stock backfill.
"""

import sys
import os
import time
sys.path.insert(0, r"C:\Users\fmkri\Downloads\Python-Backend\Python-Backend")
os.chdir(r"C:\Users\fmkri\Downloads\Python-Backend\Python-Backend")

import sqlite3
from datetime import datetime, timezone
from gex_data_loader import process_ticker_day, get_real_trading_days, DB_PATH
from gex_calculator import calculate_gex_for_ticker_day

TICKER = "SPY"
WINDOW_START = "2026-06-10"
WINDOW_END = "2026-09-21"


def run_spy_backfill():
    print("=" * 100)
    print("SPY HISTORICAL GEX BACKFILL -- " + datetime.now(timezone.utc).isoformat())
    print("Target window: " + WINDOW_START + " to " + WINDOW_END + " (matching 6-stock table's original range)")
    print("=" * 100)

    trading_days = None
    for attempt in range(3):
        try:
            trading_days = get_real_trading_days(WINDOW_START, WINDOW_END)
            break
        except Exception as exc:
            print("  get_real_trading_days failed (attempt " + str(attempt + 1) + "/3): " + str(exc)[:150])
            if attempt < 2:
                time.sleep(10)
    if trading_days is None:
        print("Could not determine the trading-day calendar after 3 attempts. Stopping cleanly, nothing corrupted.")
        return {"error": "trading_calendar_unavailable"}
    print("Found " + str(len(trading_days)) + " real trading day(s) in range.\n")

    filled = []
    still_missing = []
    pagination_incomplete_days = []
    per_day_pagination = []

    with sqlite3.connect(DB_PATH) as _conn:
        _already_done = set(
            r[0] for r in _conn.execute(
                "SELECT DISTINCT snapshot_date FROM gex_metrics WHERE ticker=?", (TICKER,)
            ).fetchall()
        )
    print("Already-complete dates from a prior run, will be skipped: " + str(len(_already_done)))

    for d in trading_days:
        date_str = d.isoformat()
        if date_str in _already_done:
            continue

        # process_ticker_day() is idempotent (deletes-then-reinserts for this
        # ticker/date), so it's safe to call even if partially run before.
        summary = None
        for _fetch_attempt in range(3):
            summary = process_ticker_day(TICKER, date_str)
            if summary["contracts_retained"] > 0 or _fetch_attempt == 2:
                break
            print("  " + TICKER + " " + date_str + ": fetch attempt " + str(_fetch_attempt + 1) + "/3 got 0 contracts (errors=" + str(summary["errors"]) + "), retrying in 8s")
            time.sleep(8)
        per_day_pagination.append({
            "date": date_str, "records_retrieved": summary["records_retrieved"],
            "pages_requested": summary["pages_requested"], "pagination_complete": summary["pagination_complete"],
            "contracts_retained": summary["contracts_retained"],
        })
        if not summary["pagination_complete"]:
            pagination_incomplete_days.append(date_str)
            print("  " + TICKER + " " + date_str + ": *** PAGINATION INCOMPLETE (hit 20-page cap) *** "
                  "records_retrieved=" + str(summary["records_retrieved"]) + " pages=" + str(summary["pages_requested"]))

        if summary["contracts_retained"] == 0:
            print("  " + TICKER + " " + date_str + ": 0 contracts retained (pages=" + str(summary["pages_requested"]) +
                  ", raw_retrieved=" + str(summary["records_retrieved"]) + ") errors=" + str(summary["errors"]))
            still_missing.append(date_str)
            continue

        success = False
        last_exc = None
        for attempt in range(2):
            try:
                results = calculate_gex_for_ticker_day(TICKER, date_str)
                success = bool(results)
                break
            except Exception as exc:
                last_exc = exc
                if attempt == 0:
                    print("  " + TICKER + " " + date_str + ": calculate_gex_for_ticker_day failed (" + str(exc)[:120] + "), retrying once in 5s")
                    time.sleep(5)
                else:
                    print("  " + TICKER + " " + date_str + ": calculate_gex_for_ticker_day failed twice, giving up: " + str(exc)[:200])

        if success:
            filled.append(date_str)
            print("  " + TICKER + " " + date_str + ": OK, GEX computed and stored "
                  "(pages=" + str(summary["pages_requested"]) + ", raw_retrieved=" + str(summary["records_retrieved"]) +
                  ", contracts_retained=" + str(summary["contracts_retained"]) + ")")
        else:
            still_missing.append(date_str)

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT MIN(snapshot_date), MAX(snapshot_date), COUNT(*) FROM gex_metrics WHERE ticker=?", (TICKER,)).fetchone()
        spy_min, spy_max, spy_count = row

    print("\n" + "=" * 100)
    print("RESULT")
    print("=" * 100)
    print("Dates filled this run: " + str(len(filled)) + " / " + str(len(trading_days)))
    print("Dates still missing (0 contracts or calc failure): " + str(len(still_missing)))
    for d in still_missing:
        print("  - " + d)
    print("\nDays with INCOMPLETE pagination (hit 20-page cap, data may be truncated): " + str(len(pagination_incomplete_days)))
    for d in pagination_incomplete_days:
        print("  *** " + d)
    max_pages_seen = max((p["pages_requested"] for p in per_day_pagination), default=0)
    print("Max pages requested for any single (ticker,day): " + str(max_pages_seen) + " (cap is 20)")

    print("\nSPY rows in gex_metrics now: " + str(spy_count) + ", range " + str(spy_min) + " to " + str(spy_max))

    return {
        "filled": filled, "still_missing": still_missing,
        "pagination_incomplete_days": pagination_incomplete_days,
        "max_pages_seen": max_pages_seen,
        "spy_min": spy_min, "spy_max": spy_max, "spy_count": spy_count,
    }


if __name__ == "__main__":
    run_spy_backfill()

from dotenv import load_dotenv
load_dotenv()

"""
Data-generation pass for the strike-positioning (OI skew) pre-registration
(CLAUDE.md Section 39, preregister_strike_positioning_experiment.py,
config_hash ae3b3a7df686159c0e3dcad1556f6433c64bee2828a1d2c4bee5cd3b71cded33
-- re-verified unchanged immediately before this script was written).

FETCHES AND SAVES DATA ONLY -- does not run the primary test, does not
compute correlations, does not call preregister_experiment()/
run_experiment(). Stage 1 execution is a separate, later, deliberate step,
per explicit instruction.

Builds ONLY Stage 1 (train_period = 2026-01-15 to 2026-06-10, per the
pre-registration's own config) -- Stage 2 is rolling/open-ended and not
touched here.

REUSE, NOT REIMPLEMENTATION: `compute_oi_skew()` (the exact +/-10%
moneyness, 7-45 DTE, log(put_OI/call_OI) logic, zero-handled by exclusion)
and `_fetch_raw_chain_paginated()` (the validated, id-date-safe, full-
pagination EODHD fetch) are imported directly from
`generate_xgboost_volatility_dataset.py` / `gex_data_loader.py` and used
UNMODIFIED -- this script defines no OI-skew or chain-fetch logic of its
own. Distinct from that script's own dataset in every other way: this
pre-registration's feature set is oi_skew ALONE (no term structure, no
Greeks, no trailing realized vol), and the target is FORWARD RETURN of
the underlying (not realized volatility).

Writes to a NEW, separate database (strike_positioning_oi_skew_dataset.db)
-- does not touch xgboost_volatility_dataset.db, ml_xgboost_interaction_
data.db, ml_training_data.db, or any GEX/IV-term-structure database.

RESUMABILITY / CONCURRENCY SAFETY: same discipline as the RF v2 automation
fix and the volatility-dataset script (CLAUDE.md Sections 44/45/52) --
this project's background-execution tooling has silently double-launched
scripts before. An exclusive lockfile is acquired at startup via
os.O_CREAT|os.O_EXCL; a second concurrent instance exits immediately
rather than racing. Both DB tables additionally carry a
UNIQUE(ticker, obs_date) constraint with INSERT OR IGNORE as a second,
independent layer of protection. Fetch errors are NOT marked seen, so
they retry naturally on the next run.
"""

import os
import sqlite3
from datetime import datetime, timezone

import numpy as np
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from gex_data_loader import _fetch_raw_chain_paginated
from generate_xgboost_volatility_dataset import compute_oi_skew

DB_PATH = "strike_positioning_oi_skew_dataset.db"
LOG_PATH = "strike_positioning_oi_skew_generation_log.txt"
LOCK_PATH = "strike_positioning_oi_skew_generation.lock"

TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]

# Stage 1 window, EXACTLY as pinned in the pre-registration's own
# `train_period` field -- entirely pre-V1-window, matching IV term
# structure's Stage 1 dates for cross-hypothesis comparability.
STAGE1_START = "2026-01-15"
STAGE1_END = "2026-06-10"

FORWARD_HORIZONS = [10, 20, 50]
MAX_FORWARD = max(FORWARD_HORIZONS)


# ---------------------------------------------------------------------------
# Concurrency lock
# ---------------------------------------------------------------------------

def acquire_lock():
    try:
        fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


def release_lock():
    try:
        os.remove(LOCK_PATH)
    except FileNotFoundError:
        pass


def log(fh, msg: str) -> None:
    print(msg, flush=True)
    fh.write(msg + "\n")
    fh.flush()


# ---------------------------------------------------------------------------
# DB schema
# ---------------------------------------------------------------------------

def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS oi_skew_training_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT, obs_date TEXT,
            oi_skew REAL, spot_price REAL,
            target_return_10d REAL, target_return_20d REAL, target_return_50d REAL,
            pages_requested INTEGER, pagination_complete INTEGER,
            generated_at TEXT,
            UNIQUE(ticker, obs_date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS oi_skew_excluded (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT, obs_date TEXT, reason TEXT,
            pages_requested INTEGER, pagination_complete INTEGER,
            logged_at TEXT,
            UNIQUE(ticker, obs_date)
        )
    """)
    conn.commit()


def load_seen(conn: sqlite3.Connection):
    seen = set()
    for ticker, obs_date in conn.execute("SELECT ticker, obs_date FROM oi_skew_training_examples"):
        seen.add((ticker, obs_date))
    for ticker, obs_date in conn.execute("SELECT ticker, obs_date FROM oi_skew_excluded"):
        seen.add((ticker, obs_date))
    return seen


def log_exclusion(conn, ticker, obs_date, reason, pages, pag_complete):
    conn.execute(
        "INSERT OR IGNORE INTO oi_skew_excluded "
        "(ticker, obs_date, reason, pages_requested, pagination_complete, logged_at) "
        "VALUES (?,?,?,?,?,?)",
        (ticker, obs_date, reason, pages, int(pag_complete), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Daily bars (fetched from STAGE1_START through "today" -- comfortably
# covers STAGE1_END + 50 trading days of real forward data, since today
# is 2026-09-26 and STAGE1_END is 2026-06-10)
# ---------------------------------------------------------------------------

def fetch_daily_closes(ticker: str):
    api_key = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    client = StockHistoricalDataClient(api_key, secret_key)
    start = datetime.strptime(STAGE1_START, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.now(timezone.utc)
    req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame(1, TimeFrameUnit.Day), start=start, end=end, feed=DataFeed.IEX)
    bars = list(client.get_stock_bars(req)[ticker])
    return bars


# ---------------------------------------------------------------------------
# Main per-ticker loop
# ---------------------------------------------------------------------------

def process_ticker(ticker, conn, log_fh, seen):
    log(log_fh, f"\n=== {ticker}: fetching daily bars {STAGE1_START} to today ===")
    bars = fetch_daily_closes(ticker)
    dates = [b.timestamp.date() for b in bars]
    closes = [float(b.close) for b in bars]
    n = len(closes)
    log(log_fh, f"{ticker}: {n} daily bars ({dates[0]}..{dates[-1]})")

    stage1_end_date = datetime.strptime(STAGE1_END, "%Y-%m-%d").date()

    # Candidates: obs_date within Stage 1 window (dates[0] is already >=
    # STAGE1_START since bars were fetched starting there), AND enough
    # forward bars exist to compute the 50-day target.
    candidate_indices = [i for i in range(n - MAX_FORWARD) if dates[i] <= stage1_end_date]
    total_candidates = len(candidate_indices)
    log(log_fh, f"{ticker}: {total_candidates} Stage-1 candidate trading days ({STAGE1_START} to {STAGE1_END}, forward window computable)")

    saved, excl_oi, excl_error = 0, 0, 0

    for count, i in enumerate(candidate_indices):
        obs_date = dates[i]
        date_str = obs_date.isoformat()
        key = (ticker, date_str)
        if key in seen:
            continue

        spot_price = closes[i]
        forward_returns = {h: float(np.log(closes[i + h] / spot_price)) for h in FORWARD_HORIZONS}

        try:
            fetch_result = _fetch_raw_chain_paginated(ticker, date_str)
        except Exception as exc:
            excl_error += 1
            log(log_fh, f"  [{ticker} {date_str}] fetch error, will retry on next run: {exc}")
            continue  # NOT marked seen -- retried on rerun

        pages_requested = fetch_result["pages_requested"]
        pagination_complete = fetch_result["pagination_complete"]
        id_matched = [r.get("attributes", {}) for r in fetch_result["records"] if str(r.get("id", "")).endswith("-" + date_str)]

        oi_skew = compute_oi_skew(id_matched, obs_date, spot_price)
        if oi_skew is None:
            excl_oi += 1
            log_exclusion(conn, ticker, date_str, "oi_skew_unavailable", pages_requested, pagination_complete)
            seen.add(key)
            continue

        conn.execute(
            """INSERT OR IGNORE INTO oi_skew_training_examples
               (ticker, obs_date, oi_skew, spot_price,
                target_return_10d, target_return_20d, target_return_50d,
                pages_requested, pagination_complete, generated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                ticker, date_str, oi_skew, spot_price,
                forward_returns[10], forward_returns[20], forward_returns[50],
                pages_requested, int(pagination_complete), datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        seen.add(key)
        saved += 1

        if (count + 1) % 25 == 0 or (count + 1) == total_candidates:
            log(log_fh, f"  [{ticker}] {count + 1}/{total_candidates} scanned -- saved={saved} excl_oi={excl_oi} excl_error={excl_error}")

    log(log_fh, f"{ticker} DONE: saved={saved} excl_oi={excl_oi} excl_error={excl_error}")
    return {"total": total_candidates, "saved": saved, "excl_oi": excl_oi, "excl_error": excl_error}


def main():
    if not acquire_lock():
        print(f"LOCK HELD ({LOCK_PATH} exists) -- another instance appears to already be running. Exiting without touching data.", flush=True)
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        init_db(conn)
        seen = load_seen(conn)

        with open(LOG_PATH, "a", encoding="utf-8") as log_fh:
            log(log_fh, f"\n{'=' * 100}\n=== RUN START {datetime.now(timezone.utc).isoformat()} | Stage 1 window {STAGE1_START} to {STAGE1_END} | resuming with {len(seen)} already-processed (ticker,date) pairs ===")

            all_tallies = {}
            for ticker in TICKERS:
                all_tallies[ticker] = process_ticker(ticker, conn, log_fh, seen)

            log(log_fh, "\n=== PER-TICKER SUMMARY ===")
            agg_total = agg_saved = agg_excl_oi = agg_excl_error = 0
            for ticker, t in all_tallies.items():
                log(log_fh, f"  {ticker}: total={t['total']} saved={t['saved']} excl_oi={t['excl_oi']} excl_error={t['excl_error']}")
                agg_total += t["total"]; agg_saved += t["saved"]; agg_excl_oi += t["excl_oi"]; agg_excl_error += t["excl_error"]
            log(log_fh, f"  AGGREGATE: total={agg_total} saved={agg_saved} excl_oi={agg_excl_oi} excl_error={agg_excl_error}")

            final_saved = conn.execute("SELECT COUNT(*) FROM oi_skew_training_examples").fetchone()[0]
            final_excluded = conn.execute("SELECT COUNT(*) FROM oi_skew_excluded").fetchone()[0]
            log(log_fh, f"\n=== RUN COMPLETE {datetime.now(timezone.utc).isoformat()} ===")
            log(log_fh, f"Final saved N (DB total): {final_saved}")
            log(log_fh, f"Final excluded total (DB total): {final_excluded}")

        conn.close()
    finally:
        release_lock()


if __name__ == "__main__":
    main()

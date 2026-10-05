from dotenv import load_dotenv
load_dotenv()

"""
Incremental Stage-2 data-generation script for iv_term_structure_slope_v1_20260921
(CLAUDE.md Section 33). NOT a new experiment, NOT a Stage 1 re-derivation --
Stage 1 already closed (SUGGESTIVE, correlation -0.28 to -0.31, p=0.001-0.002,
robust) with its own locked, reported result. This script exists solely to
grow Stage 2 (the genuinely out-of-sample, rolling window) incrementally and
PERSIST it -- fixing the design gap found 2026-09-30: Stage 1's original
execution never saved its raw observations to a database, only the final
statistical result was recorded, so every Stage 2 check since has had to
start from zero rather than accumulating.

SCOPE, DELIBERATELY NARROW -- matches iv_term_structure_slope_v1_20260921's
own locked design exactly, nothing more:
  - Universe: the ORIGINAL 6 tickers only (AAPL, TSLA, NVDA, AMD, SMCI, MSTR)
    -- this experiment's own universe, NOT the 59-ticker broader universe
    (a separate, later, unrelated experiment).
  - Window: Stage 2 only, fixed start 2026-09-10 (CLAUDE.md Section 33's
    locked boundary), open end -- never touches or regenerates Stage 1's
    own 2023-10-02..2026-06-10 window.
  - Signal: term_structure_slope_pct/near_iv/far_iv/matched strike, via
    select_near_far() IMPORTED UNCHANGED from generate_xgboost_volatility_
    dataset.py -- the exact PRIMARY convention already locked for this
    experiment (near = soonest expiration in [7,16] DTE, far = latest
    expiration in [30,45] DTE, matched strike = median of the common-
    strike intersection, EXCLUDE if no common strike -- no nearest-strike
    fallback here; that fallback is a declared ROBUSTNESS CHECK on the
    already-locked Stage 1 data, not part of the primary persisted
    dataset, and is computed separately, after the fact, exactly as it
    was for Stage 1).
  - Target: forward realized volatility at 10/20/50-day horizons only --
    no trailing-vol feature, no Greeks, no OI skew. This experiment tests
    slope vs. forward realized vol directly; those other features belong
    to the separate XGBoost/RF volatility-prediction track (Sections 45+),
    not to this one.
  - No moneyness/strike-matching against a live spot price is needed for
    the slope itself (select_near_far() takes no spot_price argument --
    confirmed by reading its signature) -- so unlike
    generate_broader_universe_volatility_dataset.py, this script needs
    ONLY the split/dividend-ADJUSTED price series (for real, economically
    correct log-return-based realized vol), never a raw/unadjusted one.
    There is no strike-matching-against-real-quotes step here that raw
    prices would be needed for.

QUOTA SAFETY, per the same fix already validated in
generate_broader_universe_volatility_dataset.py (CLAUDE.md Section 60,
2026-09-29/30): a single 429 from the UnicornBay endpoint stops the ENTIRE
run immediately -- no retry, no continuing to the next ticker. Built in
from the start here rather than retrofitted, since the pattern is already
proven.

PER EXPLICIT INSTRUCTION (2026-09-30): this script is built now but NOT
scheduled and NOT run yet. Hold until either (a) the 59-ticker broader-
universe backfill finishes, or (b) explicit confirmation the EODHD quota
situation has changed. Once given the go-ahead, register a scheduled task
the same way GEX_Historical_Incremental_Update / RF_v2_Stage2_Nightly_Update
already are (see their XML templates) so this stops requiring a manual
check every time.

Writes to a NEW, separate database (iv_termstructure_stage2_dataset.db) --
does not touch xgboost_volatility_dataset.db, broader_universe_volatility_
dataset.db, gex_data_cache.db, or prospective_gex_validation.db.

RESUMABILITY / CONCURRENCY SAFETY: identical mechanism to every other
data-generation script in this project -- an exclusive lockfile
(iv_termstructure_stage2_generation.lock) via os.O_CREAT|os.O_EXCL, plus a
UNIQUE(ticker, obs_date) DB constraint with INSERT OR IGNORE as a second,
independent layer of protection.
"""

import math
import os
import sqlite3
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import requests
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from gex_data_loader import _fetch_raw_chain_paginated
from generate_xgboost_volatility_dataset import select_near_far, NEAR_DTE, FAR_DTE

DB_PATH = "iv_termstructure_stage2_dataset.db"
LOG_PATH = "iv_termstructure_stage2_generation_log.txt"
LOCK_PATH = "iv_termstructure_stage2_generation.lock"

# iv_term_structure_slope_v1_20260921's OWN universe -- the original 6 tickers,
# not the 59-ticker broader universe (a separate experiment).
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]

STAGE2_START = "2026-09-10"  # locked, CLAUDE.md Section 33 -- the fixed rolling-window start
FORWARD_HORIZONS = [10, 20, 50]
MAX_FORWARD = max(FORWARD_HORIZONS)
TRADING_DAYS_PER_YEAR = 252
OPTION_TYPE = "call"
ET = ZoneInfo("America/New_York")
MARKET_CLOSE_ET = time(16, 0)


class QuotaExhaustedError(Exception):
    """Same contract as generate_broader_universe_volatility_dataset.py's fix
    (CLAUDE.md Section 60, validated 2026-09-29/30): raised the instant a 429
    is seen. The whole run must stop -- no retry, no next-ticker fallthrough."""
    pass


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
        CREATE TABLE IF NOT EXISTS termstructure_stage2_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT, obs_date TEXT,
            term_structure_slope_pct REAL, near_iv REAL, far_iv REAL,
            near_dte INTEGER, near_strike REAL, near_contract TEXT,
            target_realized_vol_10d REAL, target_realized_vol_20d REAL, target_realized_vol_50d REAL,
            pages_requested INTEGER, pagination_complete INTEGER,
            generated_at TEXT,
            UNIQUE(ticker, obs_date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS termstructure_stage2_excluded (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT, obs_date TEXT, reason TEXT,
            near_bucket_populated INTEGER, far_bucket_populated INTEGER,
            pages_requested INTEGER, pagination_complete INTEGER,
            logged_at TEXT,
            UNIQUE(ticker, obs_date)
        )
    """)
    conn.commit()


def load_seen(conn: sqlite3.Connection):
    seen = set()
    for ticker, obs_date in conn.execute("SELECT ticker, obs_date FROM termstructure_stage2_examples"):
        seen.add((ticker, obs_date))
    for ticker, obs_date in conn.execute("SELECT ticker, obs_date FROM termstructure_stage2_excluded"):
        seen.add((ticker, obs_date))
    return seen


def log_exclusion(conn, ticker, obs_date, reason, near_pop, far_pop, pages, pag_complete):
    conn.execute(
        "INSERT OR IGNORE INTO termstructure_stage2_excluded "
        "(ticker, obs_date, reason, near_bucket_populated, far_bucket_populated, pages_requested, pagination_complete, logged_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (ticker, obs_date, reason, int(near_pop), int(far_pop), pages, int(pag_complete), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Daily bars / realized vol -- ADJUSTED ONLY (no strike-matching against
# spot needed here, unlike the broader-universe script; see module docstring)
# ---------------------------------------------------------------------------

def fetch_adjusted_closes(ticker: str):
    api_key = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    client = StockHistoricalDataClient(api_key, secret_key)
    start = datetime.strptime(STAGE2_START, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.now(timezone.utc)
    req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame(1, TimeFrameUnit.Day), start=start, end=end, feed=DataFeed.IEX, adjustment=Adjustment.ALL)
    bars = list(client.get_stock_bars(req)[ticker])
    return bars


def latest_usable_day(now=None):
    """Last calendar day whose daily bar is guaranteed complete. Before 16:00 ET,
    today's bar is still forming (Alpaca returns it during the session), so the
    cutoff is yesterday; from 16:00 ET on, it is today. Conservative on early-close
    days (13:00), which simply wait until 16:00. FIX 2026-10-01: rows are never
    recomputed once saved, so a partial close must never reach n or a candidate."""
    now_et = (now or datetime.now(timezone.utc)).astimezone(ET)
    if now_et.time() < MARKET_CLOSE_ET:
        return now_et.date() - timedelta(days=1), now_et
    return now_et.date(), now_et


def annualized_stdev(log_returns_window) -> float | None:
    if len(log_returns_window) < 2:
        return None
    return float(np.std(log_returns_window, ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))


# ---------------------------------------------------------------------------
# Main per-ticker loop
# ---------------------------------------------------------------------------

class BarFetchError(Exception):
    """Alpaca daily-bar fetch failed (e.g. no network after a Modern Standby wake). The ticker is
    skipped for this run; nothing is written for it, so the next run picks it up unchanged."""


def process_ticker(ticker, conn, log_fh, seen):
    log(log_fh, f"\n=== {ticker}: fetching adjusted daily bars {STAGE2_START} to today ===")
    try:
        bars = fetch_adjusted_closes(ticker)
    except Exception as exc:  # FIX 2026-10-05: a DNS failure here used to crash the whole run (exit 1)
        log(log_fh, f"{ticker}: daily-bar fetch FAILED, ticker skipped this run, nothing written: {exc}")
        raise BarFetchError(str(exc)) from exc
    cutoff, now_et = latest_usable_day()
    dropped = [b.timestamp.date() for b in bars if b.timestamp.date() > cutoff]
    bars = [b for b in bars if b.timestamp.date() <= cutoff]
    log(log_fh, f"{ticker}: now {now_et.strftime('%Y-%m-%d %H:%M %Z')} -> latest usable day {cutoff} "
                f"(dropped incomplete/future bars: {[d.isoformat() for d in dropped] or 'none'})")
    dates = [b.timestamp.date() for b in bars]
    closes = [float(b.close) for b in bars]
    n = len(closes)
    log_returns = np.diff(np.log(np.array(closes, dtype=float)))
    log(log_fh, f"{ticker}: {n} daily bars ({dates[0] if dates else '-'}..{dates[-1] if dates else '-'})")

    tally = {"total": 0, "near": 0, "far": 0, "both": 0, "saved": 0}
    saved, excl_ts, excl_error = 0, 0, 0

    # No trailing-window burn-in needed (this experiment has no trailing-vol
    # feature) -- candidates start at index 0, bounded only by forward-return
    # computability.
    candidate_range = range(0, n - MAX_FORWARD)
    total_candidates = len(candidate_range)
    log(log_fh, f"{ticker}: {total_candidates} candidate trading days (forward window computable)")

    for count, i in enumerate(candidate_range):
        obs_date = dates[i]
        date_str = obs_date.isoformat()
        key = (ticker, date_str)
        if key in seen:
            continue

        forward_vols = {h: annualized_stdev(log_returns[i:i + h]) for h in FORWARD_HORIZONS}
        if any(v is None for v in forward_vols.values()):
            continue

        try:
            fetch_result = _fetch_raw_chain_paginated(ticker, date_str)
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                log(log_fh, f"  [{ticker} {date_str}] 429 TOO MANY REQUESTS -- stopping the ENTIRE run immediately, "
                            f"not just this candidate. No in-process retry, no continuing to the next ticker.")
                raise QuotaExhaustedError(str(exc)) from exc
            excl_error += 1
            log(log_fh, f"  [{ticker} {date_str}] fetch error, will retry on next run: {exc}")
            continue
        except Exception as exc:
            excl_error += 1
            log(log_fh, f"  [{ticker} {date_str}] fetch error, will retry on next run: {exc}")
            continue

        pages_requested = fetch_result["pages_requested"]
        pagination_complete = fetch_result["pagination_complete"]
        id_matched = [r.get("attributes", {}) for r in fetch_result["records"] if str(r.get("id", "")).endswith("-" + date_str)]

        ts_result, near_pop, far_pop = select_near_far(id_matched, obs_date)
        tally["total"] += 1
        tally["near"] += int(near_pop)
        tally["far"] += int(far_pop)
        tally["both"] += int(near_pop and far_pop)

        if ts_result is None:
            excl_ts += 1
            log_exclusion(conn, ticker, date_str, "term_structure_unavailable", near_pop, far_pop, pages_requested, pagination_complete)
            seen.add(key)
            continue

        conn.execute(
            """INSERT OR IGNORE INTO termstructure_stage2_examples
               (ticker, obs_date, term_structure_slope_pct, near_iv, far_iv, near_dte, near_strike, near_contract,
                target_realized_vol_10d, target_realized_vol_20d, target_realized_vol_50d,
                pages_requested, pagination_complete, generated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ticker, date_str, ts_result["slope_pct"], ts_result["near_iv"], ts_result["far_iv"],
                ts_result["near_dte"], ts_result["near_strike"], ts_result["near_contract"],
                forward_vols[10], forward_vols[20], forward_vols[50],
                pages_requested, int(pagination_complete), datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        seen.add(key)
        saved += 1
        tally["saved"] += 1

        if (count + 1) % 20 == 0 or (count + 1) == total_candidates:
            log(log_fh, f"  [{ticker}] {count + 1}/{total_candidates} scanned -- saved={saved} excl_ts={excl_ts} excl_error={excl_error} "
                        f"(near_populated={tally['near']}/{tally['total']}, far_populated={tally['far']}/{tally['total']}, both={tally['both']}/{tally['total']})")

    log(log_fh, f"{ticker} DONE: saved={saved} excl_ts={excl_ts} excl_error={excl_error} "
                f"near_populated={tally['near']}/{tally['total']} far_populated={tally['far']}/{tally['total']} both={tally['both']}/{tally['total']}")
    return tally


def main():
    if not acquire_lock():
        print(f"LOCK HELD ({LOCK_PATH} exists) -- another instance appears to already be running. Exiting without touching data.", flush=True)
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        init_db(conn)
        seen = load_seen(conn)

        with open(LOG_PATH, "a", encoding="utf-8") as log_fh:
            log(log_fh, f"\n{'=' * 100}\n=== RUN START {datetime.now(timezone.utc).isoformat()} | Stage 2 window {STAGE2_START} to today | "
                        f"{len(TICKERS)} tickers | resuming with {len(seen)} already-processed (ticker,date) pairs ===")

            all_tallies = {}
            quota_exhausted = False
            bar_fetch_failed = []
            for ticker in TICKERS:
                try:
                    all_tallies[ticker] = process_ticker(ticker, conn, log_fh, seen)
                except BarFetchError:
                    bar_fetch_failed.append(ticker)
                    continue
                except QuotaExhaustedError as exc:
                    log(log_fh, f"\n=== STOPPED ON QUOTA EXHAUSTION at ticker={ticker}, {datetime.now(timezone.utc).isoformat()} ===")
                    log(log_fh, f"429 detected: {exc}")
                    log(log_fh, "Remaining tickers this run: " + ", ".join(TICKERS[TICKERS.index(ticker):]))
                    quota_exhausted = True
                    break

            log(log_fh, "\n=== PER-TICKER SUMMARY (tickers not yet reached this run are simply absent) ===")
            for ticker, t in all_tallies.items():
                log(log_fh, f"  {ticker}: total={t['total']} saved={t['saved']}")

            final_saved = conn.execute("SELECT COUNT(*) FROM termstructure_stage2_examples").fetchone()[0]
            final_excluded = conn.execute("SELECT COUNT(*) FROM termstructure_stage2_excluded").fetchone()[0]
            if quota_exhausted:
                log(log_fh, f"\n=== RUN STOPPED EARLY (QUOTA) {datetime.now(timezone.utc).isoformat()} -- NOT a clean completion ===")
            elif bar_fetch_failed:
                # Deliberately NOT "RUN COMPLETE": the health check must still flag a run that skipped tickers.
                log(log_fh, f"\n=== RUN INCOMPLETE (NETWORK) {datetime.now(timezone.utc).isoformat()} -- daily bars unavailable for "
                            f"{len(bar_fetch_failed)}/{len(TICKERS)} tickers: {', '.join(bar_fetch_failed)}; they are retried next run ===")
            else:
                log(log_fh, f"\n=== RUN COMPLETE {datetime.now(timezone.utc).isoformat()} ===")
            log(log_fh, f"Final saved N (DB total, day-clustering NOT yet applied -- this is raw row count): {final_saved}")
            log(log_fh, f"Final excluded total (DB total): {final_excluded}")
            n_distinct_days = conn.execute("SELECT COUNT(DISTINCT obs_date) FROM termstructure_stage2_examples").fetchone()[0]
            log(log_fh, f"Distinct calendar days represented: {n_distinct_days} (the day-clustered N the pre-registration's N>=100 threshold actually applies to)")

        conn.close()
    finally:
        release_lock()


if __name__ == "__main__":
    main()

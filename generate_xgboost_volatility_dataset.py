from dotenv import load_dotenv
load_dotenv()

"""
Data-generation pass for the XGBoost-vs-Ridge forward-realized-volatility
pre-registration (CLAUDE.md Section 45, preregister_xgboost_volatility_
experiment.py, config_hash 76f200b96fdabb10bb0af2edfc12e4a098abf664108e
4349711ed70f0b3ea04b).

FETCHES AND SAVES DATA ONLY -- does not fit Ridge/XGBoost, does not
compute correlations, does not call preregister_experiment()/
run_experiment(). Stage 1 execution is a separate, later, deliberate step.

USES THE FULL PAGINATED FETCH (gex_data_loader.py:_fetch_raw_chain_
paginated, the same already-validated method the GEX pipeline uses --
follows links.next, re-appends the API token, offset fallback, 20-page
circuit breaker, tracks pagination_complete) FROM THE START, for every
single ticker-day, not just for spot-checks. The pre-registration's own
feasibility check used single-page queries and found NVDA/MSTR showing
zero near-bucket expirations at one sample date -- explicitly flagged
there as a single-page-query artifact that must not leak into the real
run. This script never uses a single-page query anywhere.

Per-ticker near/far DTE bucket population is tallied explicitly and
reported separately from the aggregate, on the same discipline that
caught the SPY OPEX check's silent 0/72 no-op (CLAUDE.md Section 43) --
a check that "passes" in aggregate can still be silently degenerate for
one specific ticker, and that must be checked for directly, not assumed
away by an overall count looking healthy.

Writes to a NEW, separate database (xgboost_volatility_dataset.db) --
does not touch ml_xgboost_interaction_data.db, ml_training_data.db, or
any IV-term-structure/GEX database, per the pre-registration's own
explicit non-interference constraint.

RESUMABILITY / CONCURRENCY SAFETY: this project's background-execution
tooling has twice silently double-launched a script as two genuinely
concurrent OS processes this session (see CLAUDE.md Section 44's
disclosed operational note). This script defends against that directly:
an exclusive lockfile (xgboost_volatility_generation.lock) is acquired
at startup via os.O_CREAT|os.O_EXCL and a second concurrent instance
exits immediately rather than racing; the DB tables also carry a
UNIQUE(ticker, obs_date) constraint with INSERT OR IGNORE as a second,
independent layer of protection.
"""

import json
import math
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import numpy as np
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from gex_data_loader import _fetch_raw_chain_paginated
from options_pricing import calculate_delta, calculate_gamma, calculate_theta, calculate_charm, calculate_vega

DB_PATH = "xgboost_volatility_dataset.db"
LOG_PATH = "xgboost_volatility_generation_log.txt"
LOCK_PATH = "xgboost_volatility_generation.lock"

TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
START_DATE = "2023-10-02"  # empirically confirmed EODHD id-date-clean depth cliff, Section 44/45
NEAR_DTE = (7, 16)
FAR_DTE = (30, 45)
TRAILING_WINDOW = 20
FORWARD_HORIZONS = [10, 20, 50]
MAX_FORWARD = max(FORWARD_HORIZONS)
TRADING_DAYS_PER_YEAR = 252
OPTION_TYPE = "call"


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
        CREATE TABLE IF NOT EXISTS volatility_training_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT, obs_date TEXT,
            term_structure_slope_pct REAL, near_iv REAL, far_iv REAL,
            near_dte INTEGER, near_strike REAL, near_contract TEXT,
            oi_skew REAL, trailing_realized_vol_20d REAL,
            delta REAL, gamma REAL, theta REAL, charm REAL, vega_per_1pct_iv REAL,
            target_realized_vol_10d REAL, target_realized_vol_20d REAL, target_realized_vol_50d REAL,
            spot_price REAL, pages_requested INTEGER, pagination_complete INTEGER,
            generated_at TEXT,
            UNIQUE(ticker, obs_date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS volatility_excluded (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT, obs_date TEXT, reason TEXT,
            near_bucket_populated INTEGER, far_bucket_populated INTEGER,
            pages_requested INTEGER, pagination_complete INTEGER,
            logged_at TEXT,
            UNIQUE(ticker, obs_date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bucket_population_summary (
            ticker TEXT PRIMARY KEY,
            total_candidate_days INTEGER,
            near_bucket_populated_days INTEGER,
            far_bucket_populated_days INTEGER,
            both_populated_days INTEGER,
            saved_days INTEGER,
            updated_at TEXT
        )
    """)
    conn.commit()


def load_seen(conn: sqlite3.Connection):
    seen = set()
    for ticker, obs_date in conn.execute("SELECT ticker, obs_date FROM volatility_training_examples"):
        seen.add((ticker, obs_date))
    for ticker, obs_date in conn.execute("SELECT ticker, obs_date FROM volatility_excluded"):
        seen.add((ticker, obs_date))
    return seen


def log_exclusion(conn, ticker, obs_date, reason, near_pop, far_pop, pages, pag_complete):
    conn.execute(
        "INSERT OR IGNORE INTO volatility_excluded "
        "(ticker, obs_date, reason, near_bucket_populated, far_bucket_populated, pages_requested, pagination_complete, logged_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (ticker, obs_date, reason, int(near_pop), int(far_pop), pages, int(pag_complete), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Daily bars / realized vol
# ---------------------------------------------------------------------------

def fetch_daily_closes(ticker: str, adjustment: Adjustment = Adjustment.RAW):
    """
    FIXED 2026-09-27 (CLAUDE.md Section 54-adjacent finding), then REFINED
    same day after a second bug was caught. History of this function:

    1. ORIGINAL bug: this call omitted `adjustment=` entirely, which
       resolves server-side to RAW (unadjusted) prices. Confirmed
       empirically that this produced real, severe split-discontinuity
       contamination for NVDA (10:1 split 2024-06-10) and SMCI (10:1 split
       2024-09-30) -- trailing/target realized-vol features hit the
       dataset-wide max (~8.3 vs. a normal ~0.3-1.0) in multi-week windows
       around each split.
    2. FIRST FIX (wrong on its own): switched everything to
       Adjustment.ALL. This broke a DIFFERENT thing -- EODHD's options
       chain reports strikes in REAL, historically-quoted terms (i.e. an
       unadjusted, as-actually-traded basis). Using a split-ADJUSTED spot
       price to compute the +/-10% moneyness band or Greeks against those
       REAL strikes produces a ~10x mismatch for any date BEFORE a split
       (confirmed empirically: SMCI 2024-06-03 adjusted close=$77.03 vs.
       real quoted chain strikes clustering at $850-865 that same day) --
       this silently exploded oi_skew_unavailable exclusions for exactly
       the split-affected tickers (SMCI's excl_oi went from 5 to 206 in a
       full regeneration attempt under this wrong fix).
    3. CORRECT FIX (current): TWO price series, each used only for what it
       is actually valid for. RAW (unadjusted) closes remain the correct
       choice for anything matched against the EODHD options chain --
       spot_price for the moneyness band, and both spot/strike sides of
       the Greeks calculation -- because the REAL chain was genuinely
       quoted against the REAL (unadjusted) historical price on that date.
       ADJUSTED (Adjustment.ALL) closes are used ONLY to compute
       log-return-based realized volatility (trailing_realized_vol_20d,
       target_realized_vol_10d/20d/50d), where a real, split-corrected
       economic return series is what's actually needed. This function now
       takes an explicit `adjustment` argument so both series can be
       fetched from the same call site without duplicating fetch logic.
    """
    api_key = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    client = StockHistoricalDataClient(api_key, secret_key)
    start = datetime.strptime(START_DATE, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.now(timezone.utc)
    req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame(1, TimeFrameUnit.Day), start=start, end=end, feed=DataFeed.IEX, adjustment=adjustment)
    bars = list(client.get_stock_bars(req)[ticker])
    return bars


def annualized_stdev(log_returns_window) -> float | None:
    if len(log_returns_window) < 2:
        return None
    return float(np.std(log_returns_window, ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))


# ---------------------------------------------------------------------------
# Term structure / OI skew / Greeks
# ---------------------------------------------------------------------------

def select_near_far(id_matched_attrs, obs_date, option_type=OPTION_TYPE):
    """Returns (result_or_None, near_populated, far_populated).
    result mirrors iv_term_structure_slope_v1_20260921's locked convention
    exactly: NEAR = soonest expiration in [7,16] DTE, FAR = latest
    expiration in [30,45] DTE (widest-spread), matched strike = median of
    the common-strike intersection."""
    by_exp = {}
    for a in id_matched_attrs:
        if a.get("type") != option_type:
            continue
        vol = a.get("volatility")
        # BUGFIX 2026-09-25: a real EODHD record can have volatility=0.0 (not
        # None) -- degenerate data that crashes calculate_delta() with a
        # ZeroDivisionError (divides by volatility*sqrt(t)). Require strictly
        # positive IV, not just "not None", consistent with this project's
        # established exclude-never-fabricate discipline.
        if vol is None or vol <= 0 or a.get("strike") is None or a.get("exp_date") is None:
            continue
        exp = datetime.strptime(a["exp_date"], "%Y-%m-%d").date()
        by_exp.setdefault(exp, []).append(a)

    near_exps = sorted(e for e in by_exp if NEAR_DTE[0] <= (e - obs_date).days <= NEAR_DTE[1])
    far_exps = sorted(e for e in by_exp if FAR_DTE[0] <= (e - obs_date).days <= FAR_DTE[1])
    near_populated = bool(near_exps)
    far_populated = bool(far_exps)

    if not near_populated or not far_populated:
        return None, near_populated, far_populated

    near_exp = near_exps[0]
    far_exp = far_exps[-1]
    near_contracts = by_exp[near_exp]
    far_contracts = by_exp[far_exp]
    near_strikes = set(c["strike"] for c in near_contracts)
    far_strikes = set(c["strike"] for c in far_contracts)
    common = sorted(near_strikes & far_strikes)
    if not common:
        return None, near_populated, far_populated

    matched_strike = common[len(common) // 2]
    near_contract = next(c for c in near_contracts if c["strike"] == matched_strike)
    far_contract = next(c for c in far_contracts if c["strike"] == matched_strike)
    near_dte = (near_exp - obs_date).days

    result = {
        "slope_pct": far_contract["volatility"] - near_contract["volatility"],
        "near_iv": near_contract["volatility"], "far_iv": far_contract["volatility"],
        "near_strike": matched_strike, "near_dte": near_dte,
        "near_contract": near_contract.get("contract"),
    }
    return result, near_populated, far_populated


def compute_oi_skew(id_matched_attrs, obs_date, spot_price):
    lo, hi = spot_price * 0.90, spot_price * 1.10
    call_oi, put_oi = 0, 0
    for a in id_matched_attrs:
        strike, exp_str, oi = a.get("strike"), a.get("exp_date"), a.get("open_interest")
        if strike is None or exp_str is None or oi is None:
            continue
        exp = datetime.strptime(exp_str, "%Y-%m-%d").date()
        dte = (exp - obs_date).days
        if not (7 <= dte <= 45) or not (lo <= strike <= hi):
            continue
        if a.get("type") == "call":
            call_oi += oi
        elif a.get("type") == "put":
            put_oi += oi
    if call_oi <= 0 or put_oi <= 0:
        return None
    return math.log(put_oi / call_oi)


def compute_greeks(spot_price, strike, dte, iv):
    return {
        "delta": calculate_delta(spot_price, strike, dte, iv, option_type=OPTION_TYPE),
        "gamma": calculate_gamma(spot_price, strike, dte, iv),
        "theta": calculate_theta(spot_price, strike, dte, iv, option_type=OPTION_TYPE),
        "charm": calculate_charm(spot_price, strike, dte, iv, option_type=OPTION_TYPE),
        "vega_per_1pct_iv": calculate_vega(spot_price, strike, dte, iv) / 100,
    }


# ---------------------------------------------------------------------------
# Main per-ticker loop
# ---------------------------------------------------------------------------

def process_ticker(ticker, conn, log_fh, seen):
    log(log_fh, f"\n=== {ticker}: fetching daily bars {START_DATE} to today (raw + split/dividend-adjusted) ===")
    raw_bars = fetch_daily_closes(ticker, adjustment=Adjustment.RAW)
    adj_bars = fetch_daily_closes(ticker, adjustment=Adjustment.ALL)
    dates = [b.timestamp.date() for b in raw_bars]
    adj_dates = [b.timestamp.date() for b in adj_bars]
    if dates != adj_dates:
        raise RuntimeError(f"{ticker}: raw and adjusted bar date series don't align ({len(dates)} vs {len(adj_dates)} bars) -- refusing to proceed with misaligned series")
    closes = [float(b.close) for b in raw_bars]       # RAW -- for EODHD chain matching (spot_price) and Greeks
    adj_closes = [float(b.close) for b in adj_bars]   # ADJUSTED -- for realized-vol return calculations only
    n = len(closes)
    log_returns = np.diff(np.log(np.array(adj_closes, dtype=float)))
    log(log_fh, f"{ticker}: {n} daily bars ({dates[0]}..{dates[-1]}), raw/adjusted date series confirmed aligned")

    tally = {"total": 0, "near": 0, "far": 0, "both": 0, "saved": 0}
    saved, excl_ts, excl_oi, excl_error = 0, 0, 0, 0

    candidate_range = range(TRAILING_WINDOW, n - MAX_FORWARD)
    total_candidates = len(candidate_range)
    log(log_fh, f"{ticker}: {total_candidates} candidate trading days (trailing/forward windows both computable)")

    for count, i in enumerate(candidate_range):
        obs_date = dates[i]
        date_str = obs_date.isoformat()
        key = (ticker, date_str)
        if key in seen:
            continue

        trailing_vol = annualized_stdev(log_returns[i - TRAILING_WINDOW:i])
        forward_vols = {h: annualized_stdev(log_returns[i:i + h]) for h in FORWARD_HORIZONS}
        if trailing_vol is None or any(v is None for v in forward_vols.values()):
            continue  # index bounds already guarantee this shouldn't happen; safety only

        try:
            fetch_result = _fetch_raw_chain_paginated(ticker, date_str)
        except Exception as exc:
            excl_error += 1
            log(log_fh, f"  [{ticker} {date_str}] fetch error, will retry on next run: {exc}")
            continue  # NOT marked seen -- retried on rerun

        pages_requested = fetch_result["pages_requested"]
        pagination_complete = fetch_result["pagination_complete"]
        id_matched = [r.get("attributes", {}) for r in fetch_result["records"] if str(r.get("id", "")).endswith("-" + date_str)]

        spot_price = closes[i]

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

        oi_skew = compute_oi_skew(id_matched, obs_date, spot_price)
        if oi_skew is None:
            excl_oi += 1
            log_exclusion(conn, ticker, date_str, "oi_skew_unavailable", near_pop, far_pop, pages_requested, pagination_complete)
            seen.add(key)
            continue

        greeks = compute_greeks(spot_price, ts_result["near_strike"], ts_result["near_dte"], ts_result["near_iv"])

        conn.execute(
            """INSERT OR IGNORE INTO volatility_training_examples
               (ticker, obs_date, term_structure_slope_pct, near_iv, far_iv, near_dte, near_strike, near_contract,
                oi_skew, trailing_realized_vol_20d, delta, gamma, theta, charm, vega_per_1pct_iv,
                target_realized_vol_10d, target_realized_vol_20d, target_realized_vol_50d,
                spot_price, pages_requested, pagination_complete, generated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ticker, date_str, ts_result["slope_pct"], ts_result["near_iv"], ts_result["far_iv"],
                ts_result["near_dte"], ts_result["near_strike"], ts_result["near_contract"],
                oi_skew, trailing_vol,
                greeks["delta"], greeks["gamma"], greeks["theta"], greeks["charm"], greeks["vega_per_1pct_iv"],
                forward_vols[10], forward_vols[20], forward_vols[50],
                spot_price, pages_requested, int(pagination_complete), datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        seen.add(key)
        saved += 1
        tally["saved"] += 1

        if (count + 1) % 50 == 0 or (count + 1) == total_candidates:
            log(log_fh, f"  [{ticker}] {count + 1}/{total_candidates} scanned -- saved={saved} excl_ts={excl_ts} excl_oi={excl_oi} excl_error={excl_error} "
                        f"(near_populated={tally['near']}/{tally['total']}, far_populated={tally['far']}/{tally['total']}, both={tally['both']}/{tally['total']})")

    conn.execute(
        "INSERT OR REPLACE INTO bucket_population_summary "
        "(ticker, total_candidate_days, near_bucket_populated_days, far_bucket_populated_days, both_populated_days, saved_days, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (ticker, tally["total"], tally["near"], tally["far"], tally["both"], tally["saved"], datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()

    log(log_fh, f"{ticker} DONE: saved={saved} excl_ts={excl_ts} excl_oi={excl_oi} excl_error={excl_error} "
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
            log(log_fh, f"\n{'=' * 100}\n=== RUN START {datetime.now(timezone.utc).isoformat()} | window {START_DATE} to today | resuming with {len(seen)} already-processed (ticker,date) pairs ===")

            all_tallies = {}
            for ticker in TICKERS:
                all_tallies[ticker] = process_ticker(ticker, conn, log_fh, seen)

            log(log_fh, "\n=== PER-TICKER NEAR/FAR BUCKET POPULATION SUMMARY (not just the aggregate) ===")
            agg_total = agg_near = agg_far = agg_both = 0
            for ticker, t in all_tallies.items():
                near_pct = (t["near"] / t["total"] * 100) if t["total"] else 0
                far_pct = (t["far"] / t["total"] * 100) if t["total"] else 0
                both_pct = (t["both"] / t["total"] * 100) if t["total"] else 0
                log(log_fh, f"  {ticker}: total={t['total']} near_populated={t['near']} ({near_pct:.1f}%) far_populated={t['far']} ({far_pct:.1f}%) both={t['both']} ({both_pct:.1f}%) saved={t['saved']}")
                agg_total += t["total"]; agg_near += t["near"]; agg_far += t["far"]; agg_both += t["both"]
            if agg_total:
                log(log_fh, f"  AGGREGATE: total={agg_total} near_populated={agg_near} ({agg_near/agg_total*100:.1f}%) far_populated={agg_far} ({agg_far/agg_total*100:.1f}%) both={agg_both} ({agg_both/agg_total*100:.1f}%)")

            final_saved = conn.execute("SELECT COUNT(*) FROM volatility_training_examples").fetchone()[0]
            final_excluded = conn.execute("SELECT COUNT(*) FROM volatility_excluded").fetchone()[0]
            log(log_fh, f"\n=== RUN COMPLETE {datetime.now(timezone.utc).isoformat()} ===")
            log(log_fh, f"Final saved N (DB total): {final_saved}")
            log(log_fh, f"Final excluded total (DB total): {final_excluded}")

        conn.close()
    finally:
        release_lock()


if __name__ == "__main__":
    main()

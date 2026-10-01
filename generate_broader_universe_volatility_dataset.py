from dotenv import load_dotenv
load_dotenv()

"""
Data-generation pass for the new, freshly-scoped broader-universe ML
volatility hypothesis (Target C, relative-to-own-history -- see
target_design_comparison_v1.md and
target_c_baseline_and_walkforward_design_v1.md). NOT a continuation of
RF v1/v2, XGBoost v1, or regularized XGBoost v2 (CLAUDE.md Section 58,
permanently closed).

Extends generate_xgboost_volatility_dataset.py's exact, already-validated
methodology (same feature set: term-structure slope, OI skew, trailing
20-day realized vol, 5 real-IV Greeks; same 3 forward realized-vol
horizons: 10/20/50-day) UNCHANGED, to the FULL 59-ticker universe approved
in broader_universe_feasibility_report.md (existing 6 + all 53 candidates
that passed feasibility). No new feature logic, no new fetch logic --
every function below is either reused verbatim or a straight
parameter-substitution of the original.

Deliberately does NOT apply the Target C transform (per-ticker trailing
126-day mean/std demeaning) here -- that is a separate, later,
fast-to-redo-anytime step once the full preregistration is locked,
exactly mirroring how xgboost_volatility_v2_stage1_execution.py was kept
separate from generate_xgboost_volatility_dataset.py. This script only
fetches and saves the same RAW ingredients at the new, wider scale.

Writes to a NEW, separate database (broader_universe_volatility_dataset.db)
-- does not touch xgboost_volatility_dataset.db or any other existing
dataset.

This script is DELIBERATELY BOTH the Stage-1 historical backfill AND the
ongoing Stage-2 accumulation mechanism at once (per explicit instruction
not to let Stage 2 automation stall the way it did for RF v2, CLAUDE.md
Section 52) -- it is designed to be re-run indefinitely, safely, on a
nightly schedule: each run resumes from wherever it left off (via the
seen-set + UNIQUE constraint + INSERT OR IGNORE), and as each new real
trading day closes, MAX_FORWARD=50 fewer days become the "not yet
forward-computable" tail, so the set of eligible candidate days grows by
one ticker-day per ticker per new trading day, automatically extending
Stage 2 without any code change.

RESUMABILITY / CONCURRENCY SAFETY: identical mechanism to
generate_xgboost_volatility_dataset.py -- an exclusive lockfile
(broader_universe_volatility_generation.lock) acquired via
os.O_CREAT|os.O_EXCL, plus a UNIQUE(ticker, obs_date) DB constraint with
INSERT OR IGNORE as a second, independent layer of protection.
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

import requests

from gex_data_loader import _fetch_raw_chain_paginated
from options_pricing import calculate_delta, calculate_gamma, calculate_theta, calculate_charm, calculate_vega


class QuotaExhaustedError(Exception):
    """
    FIX 2026-09-30 (CLAUDE.md Section 60's quota-exhaustion incident): the
    2026-09-29 run hit a real EODHD UnicornBay 429 (Too Many Requests)
    partway through AMZN and, having no rate-limit-aware handling at all,
    silently cascaded through ~34,224 further failed candidate-days over
    ~7.7 hours before "completing" -- looking superficially fine (exit 0)
    while doing almost nothing useful for the rest of the run.

    Per explicit instruction: since it's unknown whether failed (429)
    requests count against the daily quota the same as successful ones,
    this assumes the WORSE-CASE answer (yes, they count) -- so a single
    429 is treated as fatal for the WHOLE RUN, not just that one
    candidate day. No quick or repeated in-process retry is attempted;
    the "substantial wait" is simply deferring to this task's own next
    scheduled nightly trigger (~24h away), which is a genuinely long,
    safe backoff rather than a short in-process sleep-and-hammer loop.
    """
    pass


DB_PATH = "broader_universe_volatility_dataset.db"
LOG_PATH = "broader_universe_volatility_generation_log.txt"
LOCK_PATH = "broader_universe_volatility_generation.lock"

# Full 59-ticker universe approved 2026-09-29 (broader_universe_feasibility_report.md):
# existing 6 research tickers + all 53 new candidates that passed Step 1 feasibility.
TICKERS = [
    # existing 6
    "AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR",
    # 53 new candidates
    "MSFT", "GOOGL", "AMZN", "META", "AVGO", "INTC", "MU", "QCOM", "TXN", "LRCX", "AMAT", "ASML", "ARM",
    "F", "GM", "RIVN", "LCID", "NIO",
    "WMT", "COST", "TGT", "NKE", "SBUX", "MCD", "HD", "DIS",
    "JPM", "BAC", "GS", "MS", "V", "MA", "PYPL", "SOFI",
    "UNH", "JNJ", "PFE", "LLY", "MRNA",
    "XOM", "CVX", "OXY",
    "BA", "CAT", "GE",
    "COIN", "RIOT", "MARA", "PLTR", "SNAP", "ROKU", "DKNG", "AFRM",
]
assert len(TICKERS) == 59, f"expected 59 tickers, got {len(TICKERS)}"

START_DATE = "2023-10-02"  # empirically confirmed EODHD id-date-clean depth cliff for the original 6+SPY
                            # (Section 44/45) AND independently reconfirmed 2026-09-29 for all 7 IPO-limited
                            # candidates (ARM/RIVN/LCID/SOFI/COIN/PLTR/AFRM) at this same date -- see
                            # ipo_ticker_depth_and_density_check.md. No later per-ticker cliff exists in
                            # this universe; one shared START_DATE is correct for all 59 tickers.
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
    """Dual raw+adjusted series, identical convention to
    generate_xgboost_volatility_dataset.py (CLAUDE.md Section 56): RAW for
    EODHD-chain matching (spot_price, Greeks), ADJUSTED for realized-vol
    return calculations."""
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
# Term structure / OI skew / Greeks (unchanged from generate_xgboost_volatility_dataset.py)
# ---------------------------------------------------------------------------

def select_near_far(id_matched_attrs, obs_date, option_type=OPTION_TYPE):
    by_exp = {}
    for a in id_matched_attrs:
        if a.get("type") != option_type:
            continue
        vol = a.get("volatility")
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
# Main per-ticker loop (unchanged from generate_xgboost_volatility_dataset.py)
# ---------------------------------------------------------------------------

def process_ticker(ticker, conn, log_fh, seen):
    log(log_fh, f"\n=== {ticker}: fetching daily bars {START_DATE} to today (raw + split/dividend-adjusted) ===")
    # FIX 2026-10-01 (CLAUDE.md Section 60): this call had NO error handling at
    # all, unlike the EODHD fetch below -- a transient local network/DNS outage
    # (confirmed twice: "Failed to resolve 'eodhd.com'", which also took out
    # Alpaca's own host during the same window) crashed the whole run with an
    # unhandled exception right here, twice in the identical spot, even though
    # the EODHD-side failures that preceded it were handled correctly. A
    # network failure here is exactly as retriable as an EODHD fetch failure --
    # skip this ticker for this run (it will be retried in full next run, since
    # nothing for it gets marked "seen" below this point) rather than killing
    # every ticker still queued behind it.
    try:
        raw_bars = fetch_daily_closes(ticker, adjustment=Adjustment.RAW)
        adj_bars = fetch_daily_closes(ticker, adjustment=Adjustment.ALL)
    except Exception as exc:
        log(log_fh, f"  [{ticker}] fetch error on daily bars (network/DNS?), skipping this ticker for this run, will retry next run: {exc}")
        return {"total": 0, "near": 0, "far": 0, "both": 0, "saved": 0}
    dates = [b.timestamp.date() for b in raw_bars]
    adj_dates = [b.timestamp.date() for b in adj_bars]
    if dates != adj_dates:
        raise RuntimeError(f"{ticker}: raw and adjusted bar date series don't align ({len(dates)} vs {len(adj_dates)} bars) -- refusing to proceed with misaligned series")
    closes = [float(b.close) for b in raw_bars]
    adj_closes = [float(b.close) for b in adj_bars]
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
            continue

        try:
            fetch_result = _fetch_raw_chain_paginated(ticker, date_str)
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                log(log_fh, f"  [{ticker} {date_str}] 429 TOO MANY REQUESTS -- stopping the ENTIRE run immediately, "
                            f"not just this candidate. Assuming the worse-case (failed calls count against the daily "
                            f"quota) -- no in-process retry, no continuing to the next ticker. Will resume on the "
                            f"next scheduled nightly run (~24h backoff) or a deliberate manual rerun.")
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
            log(log_fh, f"\n{'=' * 100}\n=== RUN START {datetime.now(timezone.utc).isoformat()} | window {START_DATE} to today | {len(TICKERS)} tickers | resuming with {len(seen)} already-processed (ticker,date) pairs ===")

            all_tallies = {}
            quota_exhausted = False
            for ticker in TICKERS:
                try:
                    all_tallies[ticker] = process_ticker(ticker, conn, log_fh, seen)
                except QuotaExhaustedError as exc:
                    log(log_fh, f"\n=== STOPPED ON QUOTA EXHAUSTION at ticker={ticker}, {datetime.now(timezone.utc).isoformat()} ===")
                    log(log_fh, f"429 detected: {exc}")
                    log(log_fh, "Remaining tickers this run: " + ", ".join(TICKERS[TICKERS.index(ticker):]))
                    quota_exhausted = True
                    break

            log(log_fh, "\n=== PER-TICKER NEAR/FAR BUCKET POPULATION SUMMARY (not just the aggregate; tickers not yet reached this run are simply absent) ===")
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
            if quota_exhausted:
                log(log_fh, f"\n=== RUN STOPPED EARLY (QUOTA) {datetime.now(timezone.utc).isoformat()} -- NOT a clean completion, deliberately stopped on first 429 ===")
            else:
                log(log_fh, f"\n=== RUN COMPLETE {datetime.now(timezone.utc).isoformat()} ===")
            log(log_fh, f"Final saved N (DB total): {final_saved}")
            log(log_fh, f"Final excluded total (DB total): {final_excluded}")

        conn.close()
    finally:
        release_lock()


if __name__ == "__main__":
    main()

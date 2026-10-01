from dotenv import load_dotenv
load_dotenv()

"""
Prospective, forward-only data-collection pipeline for the call-wall-
distance hypothesis. Treats the existing finding as a FROZEN HYPOTHESIS,
not a proven result. Collects real, forward, never-before-touched data
starting from today onward -- no backward search for historical windows.

FROZEN BASELINE (unchanged): bullish regime, 7-factor entry score >= 20,
real breakout gate, call direction. NO strategy optimization.

NO-LOOKAHEAD RULE: for trading day T, only T-1's validated EOD GEX
snapshot may be used, via the real trading calendar and the existing
record-ID snapshot-date methodology. If T-1 GEX is unavailable or fails
integrity checks, the observation is excluded, never substituted.

Two-phase design (forward returns require real, un-elapsed future
bars, so logging and return-backfilling are necessarily separate):
1. log_signals_for_date(date) -- captures signal + T-1 GEX the day it occurs
2. backfill_forward_returns() -- fills in returns once enough real time
   has passed for a previously-logged signal

Does NOT run any statistical test. This script only builds and
verifies the pipeline.
"""

import sqlite3
from datetime import datetime, timezone, timedelta
import backtest_engine as be
from backtest_engine import get_daily_regime
from entry_scorer import calculate_entry_score
from gex_lookup import get_gex_for_signal
from gex_data_loader import get_previous_trading_day

DB_PATH = "prospective_gex_validation.db"
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
HORIZONS_BARS = {"5bar": 5, "10bar": 10, "20bar": 20, "50bar": 50}


def _init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS raw_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT, trading_date TEXT, signal_timestamp TEXT,
                bar_index INTEGER, entry_score REAL, entry_price REAL,
                gex_snapshot_date TEXT, gex_available INTEGER,
                net_gex REAL, gamma_flip_price REAL, call_wall_strike REAL,
                put_wall_strike REAL, gamma_gradient REAL,
                call_wall_distance_pct REAL,
                return_5bar REAL, return_10bar REAL, return_20bar REAL, return_50bar REAL,
                mfe REAL, mae REAL, returns_backfilled INTEGER DEFAULT 0,
                data_quality_flag TEXT, logged_at TEXT,
                UNIQUE(ticker, signal_timestamp)
            )
        """)


def log_signals_for_date(date_str: str) -> dict:
    """Scans one trading day for baseline-qualifying signals, logs each with its T-1 GEX. Forward returns are NULL until backfilled.

    FIX: fetches a 10-day trailing window (not just the single target
    day) so check_breakout's 20-bar lookback and the index>=60 minimum
    can draw on PRIOR days' bars, exactly as every earlier validated
    script tonight did. Without this, only the last ~85 minutes of each
    day would have enough same-day history to be checked at all -- a
    real, systematic under-detection bias in the original version.
    """
    _init_db()
    obs_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    fetch_start = obs_date - timedelta(days=10)
    logged = 0
    skipped_gex_unavailable = 0

    with sqlite3.connect(DB_PATH) as conn:
        for ticker in TICKERS:
            bars = be.get_historical_bars(ticker, fetch_start, obs_date + timedelta(days=1))
            if not bars:
                continue
            for index in range(60, len(bars)):
                if bars[index].timestamp.date() != obs_date.date():
                    continue  # only log signals ON the target date; earlier bars are lookback context only
                if not be.check_breakout(bars, index, lookback=20):
                    continue
                timestamp = bars[index].timestamp
                try:
                    spy_regime = get_daily_regime("SPY", timestamp, period=50)
                except Exception:
                    spy_regime = "neutral"
                if spy_regime != "bullish":
                    continue
                try:
                    score_result = calculate_entry_score(ticker, bars, index, "call", spy_regime=spy_regime)
                except Exception:
                    continue
                if score_result["total_score"] < 20:
                    continue

                gex = get_gex_for_signal(ticker, timestamp)
                if not gex.get("available"):
                    skipped_gex_unavailable += 1
                    continue  # per instruction: exclude, never substitute

                entry_price = float(bars[index].close)
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO raw_signals (ticker, trading_date, signal_timestamp, bar_index, entry_score, entry_price, gex_snapshot_date, gex_available, net_gex, gamma_flip_price, call_wall_strike, put_wall_strike, gamma_gradient, call_wall_distance_pct, data_quality_flag, logged_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (ticker, date_str, str(timestamp), index, score_result["total_score"], entry_price,
                         gex["gex_snapshot_date"], 1, gex.get("net_gex_normalized"), gex.get("gamma_flip_price"),
                         gex.get("call_wall_strike"), gex.get("put_wall_strike"), gex.get("gamma_gradient_at_spot"),
                         gex.get("call_wall_distance_pct"), "clean", datetime.now(timezone.utc).isoformat())
                    )
                    logged += 1
                except sqlite3.IntegrityError:
                    pass
        conn.commit()

    return {"date": date_str, "logged": logged, "skipped_gex_unavailable": skipped_gex_unavailable}


def backfill_forward_returns() -> dict:
    """Fills in forward returns for previously-logged signals where enough real time has now elapsed."""
    _init_db()
    updated = 0
    still_pending = 0

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM raw_signals WHERE returns_backfilled = 0").fetchall()

        for row in rows:
            ticker = row["ticker"]
            signal_ts = datetime.fromisoformat(row["signal_timestamp"])
            bars = be.get_historical_bars(ticker, signal_ts, signal_ts + timedelta(days=10))
            if not bars:
                still_pending += 1
                continue

            entry_price = row["entry_price"]
            returns = {}
            max_price = entry_price
            min_price = entry_price
            complete = True
            for label, n in HORIZONS_BARS.items():
                if n - 1 < len(bars):
                    price = float(bars[n - 1].close)
                    returns[label] = (price - entry_price) / entry_price
                else:
                    complete = False

            if not complete:
                still_pending += 1
                continue

            for b in bars[:HORIZONS_BARS["50bar"]]:
                max_price = max(max_price, float(b.high))
                min_price = min(min_price, float(b.low))
            mfe = (max_price - entry_price) / entry_price
            mae = (min_price - entry_price) / entry_price

            conn.execute(
                "UPDATE raw_signals SET return_5bar=?, return_10bar=?, return_20bar=?, return_50bar=?, mfe=?, mae=?, returns_backfilled=1 WHERE id=?",
                (returns["5bar"], returns["10bar"], returns["20bar"], returns["50bar"], mfe, mae, row["id"])
            )
            updated += 1
        conn.commit()

    return {"updated": updated, "still_pending": still_pending}


def run_no_lookahead_verification(test_date_str: str) -> dict:
    """Verifies T-1 resolution and no-lookahead compliance using a real, already-available trading day."""
    obs_date = datetime.strptime(test_date_str, "%Y-%m-%d").date()
    t_minus_1 = get_previous_trading_day(obs_date, reference_ticker="AAPL")

    gex = get_gex_for_signal("AAPL", datetime.strptime(test_date_str, "%Y-%m-%d").replace(hour=14, minute=30, tzinfo=timezone.utc))

    result = {
        "test_date": test_date_str, "computed_t_minus_1": t_minus_1.isoformat(),
        "gex_available": gex.get("available"), "gex_snapshot_date": gex.get("gex_snapshot_date"),
    }
    if gex.get("available"):
        snap_date = datetime.strptime(gex["gex_snapshot_date"], "%Y-%m-%d").date()
        result["snapshot_matches_t_minus_1"] = (snap_date == t_minus_1)
        result["snapshot_before_signal_date"] = (snap_date < obs_date)
    return result


if __name__ == "__main__":
    print("=" * 90)
    print("PROSPECTIVE PIPELINE -- BUILD AND VERIFICATION ONLY (no statistical test)")
    print("=" * 90)

    print("\n--- No-lookahead verification, using the most recent known-available real trading day ---")
    verification = run_no_lookahead_verification("2026-09-08")
    print(verification)

    print("\n--- Testing log_signals_for_date() on a real, already-elapsed day (2026-09-04) ---")
    print("(Using a real past day here ONLY to verify the pipeline logs correctly -- prospective")
    print(" collection going forward will use today's and future real trading days.)")
    log_result = log_signals_for_date("2026-09-04")
    print(log_result)

    print("\n--- Testing backfill_forward_returns() ---")
    backfill_result = backfill_forward_returns()
    print(backfill_result)

    print("\n--- Verifying logged data structure ---")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        sample = conn.execute("SELECT * FROM raw_signals LIMIT 1").fetchone()
        if sample:
            print(dict(sample))
        else:
            print("No rows logged (may indicate no qualifying signals on the test date, or GEX unavailable).")

    print("\nPIPELINE VERIFICATION COMPLETE -- STOPPING per instruction. No statistical test run.")
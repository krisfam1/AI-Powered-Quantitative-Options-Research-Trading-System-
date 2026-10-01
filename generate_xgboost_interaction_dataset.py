from dotenv import load_dotenv
load_dotenv()

"""
Data-generation pass for the XGBoost feature-interaction pre-registration
(CLAUDE.md Section 44, `preregister_xgboost_interaction_experiment.py`,
config_hash 35b5e9b722d3f87928819a29dd0c72584c3d9d0d9b696e135a34f555409fd31f).

FETCHES AND SAVES DATA ONLY. Does NOT compute correlations, does NOT fit
XGBoost or Random Forest, does NOT call preregister_experiment() or
run_experiment(). Stage 1 execution is a separate, later, deliberate step.

Reuses run_options_backtest(..., collect_features=True) -- the SAME
mechanism generate_training_data.py already uses -- over the full
empirically-confirmed 2023-10-02-to-present EODHD-depth window (Section 44),
instead of that script's 90-day default. generate_training_data.py and its
573-row ml_training_data.db are left completely untouched; this writes to a
brand-new database/table.

THE REAL-IV SWAP (per explicit 2026-09-24 instruction, see Section 44's
correction): after the backtest produces each trade's proxy-featured entry
(delta/gamma/theta/charm/vega_per_1pct_iv computed from
calculate_historical_volatility(), V1's realized-vol proxy, via
feature_extraction.py unmodified), this script looks up REAL historical
EODHD implied volatility for that exact (ticker, entry date, strike, 14 DTE)
via the already-validated v2_iv_pricing_model.py:get_v2_entry_iv() -- T-1-
safe, id-date-safe, 8.8%-median-error methodology, reused unchanged -- and
RECOMPUTES the five Greeks with that real IV. realized_volatility and
realized_vol_percentile are intentionally left untouched (still proxy-based
-- a genuinely different, still-valid realized-vol feature, not part of the
swap). Trades with no real matching contract at T-1 are EXCLUDED, never
substituted with the proxy, and logged to a separate excluded_trades table
with a reason -- never silently dropped.

The 3 named interaction features (Section 44) are computed AFTER the real-IV
swap, using the swapped gamma where applicable, so they reflect the actual
base features Model A/B will train on, not the pre-swap proxy values.

RESUMABLE BY DESIGN: every successfully processed trade (saved or excluded)
is committed to SQLite immediately and keyed on (ticker, entry_date,
exit_date), which is a real natural key here -- run_options_backtest allows
at most one open position per ticker at a time, so a given ticker can never
produce two trades sharing both dates. A rerun after an interruption (e.g.
the network outage that hit the original GEX backfill mid-run) reloads the
already-processed key set and skips straight past everything already done,
so nothing is redone and nothing is silently reprocessed twice.
"""

import json
import sqlite3
import time
from datetime import datetime, timezone

from options_backtest_engine import run_options_backtest
from options_pricing import calculate_delta, calculate_gamma, calculate_theta, calculate_charm, calculate_vega
from v2_iv_pricing_model import get_v2_entry_iv

DB_PATH = "ml_xgboost_interaction_data.db"
LOG_PATH = "xgboost_dataset_generation_log.txt"

TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
START = datetime(2023, 10, 2, tzinfo=timezone.utc)  # empirically confirmed EODHD id-date-clean depth cliff, Section 44
END = datetime.now(timezone.utc)
OPTION_TYPE = "call"  # matches this experiment's baseline convention (same as generate_training_data.py's default / V1's calls-only choice)
TARGET_DTE = 14


def _log(fh, msg: str) -> None:
    print(msg)
    fh.write(msg + "\n")
    fh.flush()


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS xgboost_training_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            entry_date TEXT,
            exit_date TEXT,
            exit_reason TEXT,
            pnl_pct REAL,
            pnl_dollars REAL,
            won INTEGER,
            real_iv REAL,
            real_iv_snapshot_date TEXT,
            real_iv_contract TEXT,
            real_iv_actual_dte INTEGER,
            features_json TEXT,
            generated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS excluded_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            entry_date TEXT,
            exit_date TEXT,
            strike REAL,
            reason TEXT,
            logged_at TEXT
        )
    """)
    # BUGFIX 2026-09-25: excluded_trades originally had no `strike` column, and the
    # first full run's dedup key was (ticker, entry_date, exit_date) alone -- unsafe,
    # since a ticker can complete more than one full round-trip on the same calendar
    # day (confirmed: 19 genuine same-day collisions across the 6 tickers, e.g. AAPL
    # 2025-08-06 had two distinct reversal_guard-exited trades that day at different
    # strikes). Adding strike as a column and as part of the dedup key fixes this --
    # strike differed in every one of the 19 confirmed collisions.
    try:
        conn.execute("ALTER TABLE excluded_trades ADD COLUMN strike REAL")
    except sqlite3.OperationalError:
        pass  # column already exists (fresh DB created with it, or already migrated)
    conn.commit()


def _load_seen(conn: sqlite3.Connection):
    seen_saved = set()
    for ticker, entry_date, exit_date, pnl_dollars, features_json in conn.execute(
        "SELECT ticker, entry_date, exit_date, pnl_dollars, features_json FROM xgboost_training_examples"
    ):
        strike = json.loads(features_json).get("strike") if features_json else None
        seen_saved.add((ticker, entry_date, exit_date, strike, round(pnl_dollars, 6) if pnl_dollars is not None else None))

    seen_excluded = set()
    for ticker, entry_date, exit_date, strike in conn.execute(
        "SELECT ticker, entry_date, exit_date, strike FROM excluded_trades"
    ):
        seen_excluded.add((ticker, entry_date, exit_date, strike))

    return seen_saved, seen_excluded


def _log_excluded(conn: sqlite3.Connection, ticker: str, entry_date, exit_date, reason: str, strike: float = None) -> None:
    conn.execute(
        "INSERT INTO excluded_trades (ticker, entry_date, exit_date, strike, reason, logged_at) VALUES (?,?,?,?,?,?)",
        (ticker, str(entry_date), str(exit_date), strike, reason, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def _run_backtest_with_retry(ticker: str, log_fh, attempts: int = 3, delay_s: int = 10) -> dict:
    last_exc = None
    for attempt in range(attempts):
        try:
            return run_options_backtest(
                ticker, START, END, dte_target=TARGET_DTE,
                exit_mode="reversal_guard", entry_mode="weighted",
                entry_score_threshold=20, target_delta=0.30,
                apply_spread_cost=True, collect_features=True,
                option_type=OPTION_TYPE,
            )
        except Exception as exc:
            last_exc = exc
            _log(log_fh, f"  [{ticker}] backtest fetch attempt {attempt + 1}/{attempts} failed: {exc}")
            if attempt < attempts - 1:
                time.sleep(delay_s)
    raise RuntimeError(f"{ticker}: backtest failed after {attempts} attempts") from last_exc


def _get_real_iv_with_retry(ticker: str, signal_timestamp, strike: float, target_dte: int, attempts: int = 3, delay_s: int = 3):
    for attempt in range(attempts):
        try:
            return get_v2_entry_iv(ticker, signal_timestamp, strike, option_type=OPTION_TYPE, target_dte=target_dte)
        except Exception:
            if attempt < attempts - 1:
                time.sleep(delay_s)
            else:
                raise


def process_ticker(ticker: str, conn: sqlite3.Connection, log_fh, seen_saved: set, seen_excluded: set) -> dict:
    _log(log_fh, f"\n=== {ticker}: running backtest over {START.date()} to {END.date()} (option_type={OPTION_TYPE}) ===")
    result = _run_backtest_with_retry(ticker, log_fh)
    trades = result.get("trades", [])
    _log(log_fh, f"{ticker}: {len(trades)} raw trades from backtest -- now looking up real historical IV per trade (skipping any already processed by a prior run)")

    saved = 0
    excluded_no_iv = 0
    excluded_no_features = 0
    excluded_error = 0
    already_done = 0

    for i, trade in enumerate(trades):
        entry_date = trade["entry_date"]
        exit_date = trade["exit_date"]
        features = trade.get("entry_features")
        strike = features["strike"] if features else None

        # BUGFIX 2026-09-25: dedup key now includes strike (and, for the saved-set,
        # pnl_dollars) so two genuine same-day round-trips on the same ticker are
        # never mistaken for the same trade -- see _load_seen/_init_db for the
        # full root-cause note. excl_key intentionally omits pnl_dollars (an
        # exclusion never has a computed pnl relevant to real-IV lookup identity).
        save_key = (ticker, str(entry_date), str(exit_date), strike, round(trade["pnl_dollars"], 6))
        excl_key = (ticker, str(entry_date), str(exit_date), strike)

        if save_key in seen_saved or excl_key in seen_excluded:
            already_done += 1
            continue

        if not features:
            excluded_no_features += 1
            seen_excluded.add(excl_key)
            _log_excluded(conn, ticker, entry_date, exit_date, "no_entry_features", strike=None)
            continue

        dte = features["dte"]
        signal_timestamp = datetime.combine(entry_date, datetime.min.time(), tzinfo=timezone.utc)

        try:
            iv_result = _get_real_iv_with_retry(ticker, signal_timestamp, strike, dte)
        except Exception as exc:
            excluded_error += 1
            seen_excluded.add(excl_key)
            _log_excluded(conn, ticker, entry_date, exit_date, f"network_error_after_retries: {exc}", strike=strike)
            continue

        if iv_result is None:
            excluded_no_iv += 1
            seen_excluded.add(excl_key)
            _log_excluded(conn, ticker, entry_date, exit_date, "no_real_contract_at_t_minus_1", strike=strike)
            continue

        real_iv = iv_result["historical_iv"]
        stock_price = features["stock_price"]

        new_features = dict(features)
        new_features["delta"] = calculate_delta(stock_price, strike, dte, real_iv, option_type=OPTION_TYPE)
        new_features["gamma"] = calculate_gamma(stock_price, strike, dte, real_iv)
        new_features["theta"] = calculate_theta(stock_price, strike, dte, real_iv, option_type=OPTION_TYPE)
        new_features["charm"] = calculate_charm(stock_price, strike, dte, real_iv, option_type=OPTION_TYPE)
        new_features["vega_per_1pct_iv"] = calculate_vega(stock_price, strike, dte, real_iv) / 100
        # realized_volatility / realized_vol_percentile intentionally NOT touched -- not part of the swap

        new_features["realized_volatility_x_relative_volume"] = (
            new_features["realized_volatility"] * new_features["relative_volume"]
        )
        new_features["gamma_x_moneyness"] = new_features["gamma"] * new_features["moneyness"]
        new_features["breakout_magnitude_score_x_trend_strength_score"] = (
            new_features["breakout_magnitude_score"] * new_features["trend_strength_score"]
        )

        conn.execute(
            """INSERT INTO xgboost_training_examples
               (ticker, entry_date, exit_date, exit_reason, pnl_pct, pnl_dollars, won,
                real_iv, real_iv_snapshot_date, real_iv_contract, real_iv_actual_dte,
                features_json, generated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ticker, str(entry_date), str(exit_date), trade["exit_reason"],
                trade["pnl_pct"], trade["pnl_dollars"],
                1 if trade["pnl_dollars"] > 0 else 0,
                real_iv, iv_result["snapshot_date"], iv_result["contract"], iv_result["actual_dte"],
                json.dumps(new_features), datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        seen_saved.add(save_key)
        saved += 1

        if (i + 1) % 25 == 0 or (i + 1) == len(trades):
            _log(
                log_fh,
                f"  [{ticker}] {i + 1}/{len(trades)} trades scanned -- saved={saved} "
                f"excluded_no_iv={excluded_no_iv} excluded_no_features={excluded_no_features} "
                f"excluded_error={excluded_error} already_done={already_done}",
            )

    summary = {
        "raw_trades": len(trades), "saved": saved, "excluded_no_iv": excluded_no_iv,
        "excluded_no_features": excluded_no_features, "excluded_error": excluded_error,
        "already_done": already_done,
    }
    _log(log_fh, f"{ticker} DONE: {summary}")
    return summary


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    _init_db(conn)
    seen_saved, seen_excluded = _load_seen(conn)

    with open(LOG_PATH, "a", encoding="utf-8") as log_fh:
        _log(log_fh, f"\n{'=' * 100}\n=== RUN START {datetime.now(timezone.utc).isoformat()} | window {START.date()} to {END.date()} | resuming with {len(seen_saved)} already-saved + {len(seen_excluded)} already-excluded rows ===")

        totals = {"raw_trades": 0, "saved": 0, "excluded_no_iv": 0, "excluded_no_features": 0, "excluded_error": 0, "already_done": 0}
        for ticker in TICKERS:
            r = process_ticker(ticker, conn, log_fh, seen_saved, seen_excluded)
            for k in totals:
                totals[k] += r[k]

        final_n = conn.execute("SELECT COUNT(*) FROM xgboost_training_examples").fetchone()[0]
        final_excluded = conn.execute("SELECT COUNT(*) FROM excluded_trades").fetchone()[0]
        _log(log_fh, f"\n=== RUN COMPLETE {datetime.now(timezone.utc).isoformat()} ===")
        _log(log_fh, f"Final saved N (this run's DB total): {final_n}")
        _log(log_fh, f"Final excluded total (this run's DB total): {final_excluded}")
        _log(log_fh, f"This run's totals across all tickers: {totals}")

    conn.close()


if __name__ == "__main__":
    main()

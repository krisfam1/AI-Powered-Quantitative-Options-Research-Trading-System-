from dotenv import load_dotenv
load_dotenv()

"""
Data-preparation layer for ML Experiment 1. Makes NO research decisions
-- its only job is: raw validated data -> Feature Factory -> clean,
fully-provenanced observation rows, ready for ml_experiment1_executor.py.

Locked design:
- Observation population: EXACT Phase 6 candidate signal set (breakout
  gate + 7-factor score >= 20, bullish regime, calls only, same 6
  tickers, same clean window) -- reuses the identical, already-validated
  signal-finding logic, not a new population.
- Missing-data rule: any row missing ANY of the 10 locked features is
  excluded from consideration entirely (both models).
- Purging: 20-bar embargo at train/validation and validation/test
  boundaries -- no training/validation label may reach into the
  following partition's prices.
- Primary-test population: greedy non-overlapping selection,
  chronological WITHIN EACH TICKER, pooled across tickers afterward
  with ticker metadata retained.
"""

import json
from datetime import datetime, timezone
import backtest_engine as be
from entry_scorer import calculate_entry_score
from backtest_engine import get_daily_regime
from features_underlying import past_return_n, breakout_strength, atr_normalized
from features_options import dte_at_index, delta_at_index, iv_vs_realized_vol, iv_percentile
from features_regime import spy_trend_state, relative_strength_vs_spy, vwap_distance
from options_backtest_engine import calculate_historical_volatility
from data_layer_iv_helper import get_timestamp_safe_historical_iv
from gex_data_loader import get_previous_trading_day

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
TARGET_HORIZON = 20
DTE_TARGET = 14  # consistent with the project's standing convention

LOCKED_FEATURES = [
    "past_return_n", "breakout_strength", "atr_normalized",
    "dte_at_index", "delta_at_index", "iv_vs_realized_vol", "iv_percentile",
    "spy_trend_state", "relative_strength_vs_spy", "vwap_distance",
]


def find_phase6_candidate_signals(ticker, bars, spy_bars):
    """
    EXACT reproduction of the Phase 6 signal-finding logic (breakout
    gate + 7-factor score >= 20, bullish regime, calls only) -- proven
    no-lookahead throughout tonight's Phase 6 work. Not a new population.
    """
    signals = []
    for index in range(60, len(bars)):
        bar_date = bars[index].timestamp.date()
        ts = datetime.combine(bar_date, datetime.min.time(), tzinfo=timezone.utc)
        try:
            regime = get_daily_regime(ticker, ts, period=50)
        except Exception:
            continue
        if regime != "bullish":
            continue
        if not be.check_breakout(bars, index, lookback=20):
            continue
        try:
            score_result = calculate_entry_score(ticker, bars, index, "call", spy_regime="bullish")
        except Exception:
            continue
        if score_result["total_score"] >= 20:
            signals.append(index)
    return signals


def compute_feature_row(ticker, bars, spy_bars, index, target):
    """
    Computes all 10 locked features + full provenance metadata for one
    candidate observation. Returns a row dict (with None for any
    feature that couldn't be computed -- exclusion is decided later,
    identically for both models, per the locked missing-data rule).
    """
    bar = bars[index]
    current_price = float(bar.close)
    strike = round(current_price / 5) * 5  # ATM-ish proxy strike, consistent with project's DTE=14 convention
    expiry_date = (bar.timestamp + __import__("datetime").timedelta(days=DTE_TARGET)).date()

    row = {"ticker": ticker, "signal_timestamp": bar.timestamp.isoformat(), "signal_index": index, "target": target}

    row["past_return_n"] = past_return_n(bars, index, n=20)
    row["breakout_strength"] = breakout_strength(bars, index, lookback=20)
    row["atr_normalized"] = atr_normalized(bars, index, period=14)

    dte = dte_at_index(bars, index, expiry_date)
    row["dte_at_index"] = dte

    realized_vol = None
    try:
        realized_vol = calculate_historical_volatility(bars, index, cache_namespace="ml_exp1_dataprep")
    except Exception:
        pass

    if dte is not None and dte > 0 and realized_vol:
        row["delta_at_index"] = delta_at_index(bars, index, strike, dte, realized_vol, vol_source="realized_vol")
    else:
        row["delta_at_index"] = None

    iv_result = None
    try:
        iv_result = get_timestamp_safe_historical_iv(ticker, bar.timestamp.date(), strike, target_dte=DTE_TARGET)
    except Exception:
        pass

    if iv_result and realized_vol:
        row["iv_vs_realized_vol"] = iv_vs_realized_vol(bars, index, iv_result["iv"])
        row["iv_snapshot_date"] = iv_result["snapshot_date"]
        row["raw_current_iv"] = iv_result["iv"]
    else:
        row["iv_vs_realized_vol"] = None
        row["iv_snapshot_date"] = None
        row["raw_current_iv"] = None

    # iv_percentile is filled in by a SEPARATE batch pass (fill_iv_percentile_column,
    # below) AFTER all rows for a ticker exist.
    row["iv_percentile"] = None

    row["spy_trend_state"] = spy_trend_state(bar.timestamp)
    row["relative_strength_vs_spy"] = relative_strength_vs_spy(bars, spy_bars, index, n=20)
    row["vwap_distance"] = vwap_distance(bars, index)

    row["contract_symbol_proxy"] = ticker + expiry_date.strftime("%y%m%d") + "C" + str(int(strike * 1000)).zfill(8)
    row["realized_vol_used"] = realized_vol
    row["strike_used"] = strike
    row["expiry_used"] = expiry_date.isoformat()

    return row


def build_observation_matrix(rows):
    """Locked missing-data rule: exclude a row if ANY of the 10 locked
    features is None. Applied identically -- both models see the same
    filtered set."""
    complete_rows = []
    excluded = []
    for row in rows:
        missing = [f for f in LOCKED_FEATURES if row.get(f) is None]
        if missing or row.get("target") is None:
            excluded.append({"ticker": row["ticker"], "signal_timestamp": row["signal_timestamp"], "missing": missing or ["target"]})
        else:
            complete_rows.append(row)
    return complete_rows, excluded


def chronological_split_with_purging(rows, train_frac=0.6, val_frac=0.2, horizon=TARGET_HORIZON):
    """
    Standard chronological split, THEN purges any train/validation
    observation whose target window [i, i+horizon] crosses into the
    NEXT partition. Test set requires no purging (nothing follows it).
    """
    n = len(rows)
    train_end = int(n * train_frac)
    val_end = train_end + int(n * val_frac)

    train_raw = rows[:train_end]
    val_raw = rows[train_end:val_end]
    test = rows[val_end:]

    train_boundary_idx = rows[train_end]["signal_index"] if train_end < n else None
    val_boundary_idx = rows[val_end]["signal_index"] if val_end < n else None

    train = [r for r in train_raw if train_boundary_idx is None or (r["signal_index"] + horizon) <= train_boundary_idx]
    val = [r for r in val_raw if val_boundary_idx is None or (r["signal_index"] + horizon) <= val_boundary_idx]

    purged_train = len(train_raw) - len(train)
    purged_val = len(val_raw) - len(val)

    return train, val, test, {"purged_train": purged_train, "purged_val": purged_val}


def greedy_nonoverlapping_selection(test_rows_by_ticker, horizon=TARGET_HORIZON):
    """
    LOCKED selection rule, fully deterministic:
    - Chronological WITHIN each ticker (test_rows_by_ticker must already
      be sorted by signal_index ascending, per-ticker).
    - Greedily keep an observation only if its target window
      [signal_index, signal_index+horizon] does not overlap the window
      of the most recently kept observation for that SAME ticker.
    - Ties (identical signal_index across tickers) are a non-issue --
      selection is per-ticker independent; pooling happens after.
    - Result pooled across tickers, ticker identity retained on each row.
    """
    selected = []
    for ticker, rows in test_rows_by_ticker.items():
        rows_sorted = sorted(rows, key=lambda r: r["signal_index"])
        last_window_end = None
        for r in rows_sorted:
            window_start = r["signal_index"]
            window_end = r["signal_index"] + horizon
            if last_window_end is None or window_start >= last_window_end:
                selected.append(r)
                last_window_end = window_end
    return selected

def fill_iv_percentile_column(rows_for_ticker, ticker_iv_series):
    """
    INTEGRATION step: fills in row["iv_percentile"] for every row of a
    single ticker, using that ticker's cached IV series and each row's
    own raw_current_iv. Mutates rows_for_ticker in place; returns it.
    """
    from iv_percentile_batch import compute_iv_percentile_for_observation
    for row in rows_for_ticker:
        if row.get("raw_current_iv") is None:
            continue
        signal_date = row["signal_timestamp"][:10]
        from datetime import date as _date
        obs_date = _date.fromisoformat(signal_date)
        row["iv_percentile"] = compute_iv_percentile_for_observation(obs_date, row["raw_current_iv"], ticker_iv_series)
    return rows_for_ticker

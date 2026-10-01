from dotenv import load_dotenv
load_dotenv()

"""
Chronological train/holdout validation of the primary hypothesis:
"Buying calls when the strategy produces a qualifying signal during a
bullish SPY regime has a repeatable out-of-sample edge."

Includes a REGIME-CONDITIONED random control -- random entries sampled
ONLY from bullish-regime moments (not just any random moment), for a
fair, apples-to-apples comparison. Also runs the same chronological
check on bearish x put, since that showed a real negative pattern
earlier.

Does NOT modify, optimize, or retune anything based on results.
"""

import random
import statistics
import backtest_engine as be
from backtest_engine import get_daily_regime
from entry_scorer import calculate_entry_score
from signal_validation_core import calculate_forward_stats, TICKERS
from datetime import datetime, timezone, timedelta

SMALL_SAMPLE_THRESHOLD = 20


def collect_data():
    """Every bar tagged with regime; qualifying signals tagged separately -- lets us build both the signal group and a properly regime-conditioned random pool."""
    end = datetime.now(timezone.utc)
    full_start = end - timedelta(days=90)
    train_holdout_split = end - timedelta(days=30)

    signals = []
    regime_tagged_bars = []  # (ticker, index, bars_ref, regime, period) for EVERY bar, for random pool

    for ticker in TICKERS:
        bars = be.get_historical_bars(ticker, full_start, end)
        if not bars:
            continue

        for index in range(60, len(bars)):
            timestamp = bars[index].timestamp
            try:
                spy_regime = get_daily_regime("SPY", timestamp, period=50)
            except Exception:
                spy_regime = "neutral"
            period = "train" if timestamp < train_holdout_split else "holdout"
            regime_tagged_bars.append((ticker, index, bars, spy_regime, period))

            for direction in ["call", "put"]:
                if direction == "call" and not be.check_breakout(bars, index, lookback=20):
                    continue
                if direction == "put" and not be.check_breakdown(bars, index, lookback=20):
                    continue
                try:
                    score_result = calculate_entry_score(ticker, bars, index, direction, spy_regime=spy_regime)
                except Exception:
                    continue
                if score_result["total_score"] < 20:
                    continue
                fwd_stats = calculate_forward_stats(bars, index, direction)
                signals.append({
                    "ticker": ticker, "direction": direction, "spy_regime": spy_regime,
                    "period": period, **fwd_stats,
                })
        print(ticker + ": done")

    return signals, regime_tagged_bars


def _stats_row(values_dict_list, metric):
    values = [d[metric] for d in values_dict_list if metric in d]
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "win_rate": None, "flag": ""}
    wins = len([v for v in values if v > 0])
    flag = " [SMALL SAMPLE]" if n < SMALL_SAMPLE_THRESHOLD else ""
    return {"n": n, "mean": round(statistics.mean(values) * 100, 3), "win_rate": round(wins / n * 100, 1), "flag": flag}


def print_full_stats(group, label):
    print("\n--- " + label + " (n=" + str(len(group)) + ") ---")
    for metric in ["return_5bar", "return_10bar", "return_20bar", "return_50bar", "mfe", "mae"]:
        s = _stats_row(group, metric)
        if s["n"] == 0:
            print("  " + metric + ": no data")
        else:
            print("  " + metric + ": n=" + str(s["n"]) + " mean=" + str(s["mean"]) + "% win_rate=" + str(s["win_rate"]) + "%" + s["flag"])
    return {m: _stats_row(group, m) for m in ["return_5bar", "return_10bar", "return_20bar", "return_50bar"]}


def build_regime_random_control(regime_tagged_bars, regime, period, direction, n, seed=42):
    pool = [(t, i, b) for (t, i, b, r, p) in regime_tagged_bars if r == regime and p == period]
    random.seed(seed)
    sample = random.sample(pool, min(n, len(pool)))
    results = []
    for ticker, index, bars in sample:
        stats = calculate_forward_stats(bars, index, direction)
        results.append(stats)
    return results


def analyze_hypothesis(signals, regime_tagged_bars, regime, direction, label):
    print("\n" + "=" * 90)
    print("HYPOTHESIS TEST: " + label)
    print("=" * 90)

    group = [s for s in signals if s["spy_regime"] == regime and s["direction"] == direction]
    train = [s for s in group if s["period"] == "train"]
    holdout = [s for s in group if s["period"] == "holdout"]

    train_stats = print_full_stats(train, "TRAIN")
    holdout_stats = print_full_stats(holdout, "HOLDOUT")

    print("\n--- Regime-conditioned RANDOM CONTROL (same regime, same period, same sample sizes) ---")
    rand_train = build_regime_random_control(regime_tagged_bars, regime, "train", direction, len(train))
    rand_holdout = build_regime_random_control(regime_tagged_bars, regime, "holdout", direction, len(holdout))
    print_full_stats(rand_train, "RANDOM CONTROL -- TRAIN")
    print_full_stats(rand_holdout, "RANDOM CONTROL -- HOLDOUT")

    print("\n--- TRAIN -> HOLDOUT DEGRADATION (signal group) ---")
    for metric in ["return_5bar", "return_10bar", "return_20bar", "return_50bar"]:
        t, h = train_stats[metric], holdout_stats[metric]
        if t["mean"] is None or h["mean"] is None:
            print("  " + metric + ": insufficient data")
            continue
        mean_change = round(h["mean"] - t["mean"], 3)
        wr_change = round(h["win_rate"] - t["win_rate"], 1)
        still_positive = h["mean"] > 0
        print("  " + metric + ": mean change=" + str(mean_change) + "pp, win_rate change=" + str(wr_change) + "pp, holdout still positive=" + str(still_positive))

    return train, holdout


if __name__ == "__main__":
    print("Collecting all data (signals + full regime-tagged bar universe)...\n")
    signals, regime_tagged_bars = collect_data()
    print("\nTotal signals: " + str(len(signals)))

    bull_call_train, bull_call_holdout = analyze_hypothesis(signals, regime_tagged_bars, "bullish", "call", "Bullish regime x CALL (primary hypothesis)")

    print("\n\n--- PER-TICKER BREAKDOWN, bullish x call ---")
    for ticker in TICKERS:
        subset = [s for s in signals if s["spy_regime"] == "bullish" and s["direction"] == "call" and s["ticker"] == ticker]
        print_full_stats(subset, "TICKER: " + ticker)

    bear_put_train, bear_put_holdout = analyze_hypothesis(signals, regime_tagged_bars, "bearish", "put", "Bearish regime x PUT (secondary check)")
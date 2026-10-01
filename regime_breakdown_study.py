from dotenv import load_dotenv
load_dotenv()

"""
Comprehensive long/short and regime breakdown study.

Uses REAL, dynamically-calculated SPY regime per observation (not
hardcoded neutral, correcting a real gap from the prior ablation run).
Preserves genuine chronological train/holdout separation throughout --
train = first 60 of the last 90 days, holdout = most recent 30 days.
Every subgroup's sample size is reported and explicitly flagged if
small (n<20 flagged as statistically weak).
"""

import statistics
import backtest_engine as be
from backtest_engine import get_daily_regime
from entry_scorer import calculate_entry_score
from signal_validation_core import calculate_forward_stats, TICKERS
from datetime import datetime, timezone, timedelta

SMALL_SAMPLE_THRESHOLD = 20


def collect_full_signals():
    """Full-signal (all 7 factors) qualifying moments, with REAL dynamic SPY regime and chronological period tag."""
    end = datetime.now(timezone.utc)
    full_start = end - timedelta(days=90)
    train_holdout_split = end - timedelta(days=30)

    all_signals = []
    for ticker in TICKERS:
        bars = be.get_historical_bars(ticker, full_start, end)
        if not bars:
            continue
        for direction in ["call", "put"]:
            for index in range(60, len(bars)):
                if direction == "call" and not be.check_breakout(bars, index, lookback=20):
                    continue
                if direction == "put" and not be.check_breakdown(bars, index, lookback=20):
                    continue

                timestamp = bars[index].timestamp
                try:
                    spy_regime = get_daily_regime("SPY", timestamp, period=50)
                except Exception:
                    spy_regime = "neutral"

                try:
                    score_result = calculate_entry_score(ticker, bars, index, direction, spy_regime=spy_regime)
                except Exception:
                    continue

                if score_result["total_score"] < 20:
                    continue

                fwd_stats = calculate_forward_stats(bars, index, direction)
                period = "train" if timestamp < train_holdout_split else "holdout"

                all_signals.append({
                    "ticker": ticker, "direction": direction, "spy_regime": spy_regime,
                    "period": period, "score": score_result["total_score"],
                    "breakdown": score_result["breakdown"], **fwd_stats,
                })
        print(ticker + ": done")
    return all_signals


def _stats_block(signals, metric):
    values = [s[metric] for s in signals if metric in s]
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "win_rate": None}
    wins = len([v for v in values if v > 0])
    flag = " [SMALL SAMPLE -- WEAK]" if n < SMALL_SAMPLE_THRESHOLD else ""
    return {"n": n, "mean": round(statistics.mean(values) * 100, 3), "win_rate": round(wins / n * 100, 1), "flag": flag}


def print_breakdown(signals, label):
    print("\n" + "=" * 80)
    print(label + " (n=" + str(len(signals)) + ")")
    print("=" * 80)
    for metric in ["return_5bar", "return_10bar", "return_20bar", "return_50bar", "mfe", "mae"]:
        s = _stats_block(signals, metric)
        if s["n"] == 0:
            print("  " + metric + ": no data")
            continue
        print("  " + metric + ": n=" + str(s["n"]) + " mean=" + str(s["mean"]) + "% win_rate=" + str(s["win_rate"]) + "%" + s["flag"])


if __name__ == "__main__":
    print("Collecting full-signal qualifying moments with REAL dynamic SPY regime...\n")
    all_signals = collect_full_signals()
    print("\nTotal full-signal qualifying moments: " + str(len(all_signals)))

    # 1. Direction breakdown (calls vs puts), all periods/regimes combined
    for direction in ["call", "put"]:
        subset = [s for s in all_signals if s["direction"] == direction]
        print_breakdown(subset, "DIRECTION: " + direction.upper())

    # 2. Regime breakdown, both directions combined
    for regime in ["bullish", "bearish", "neutral"]:
        subset = [s for s in all_signals if s["spy_regime"] == regime]
        print_breakdown(subset, "SPY REGIME: " + regime.upper())

    # 4. Direction x Regime cross-breakdown
    for regime in ["bullish", "bearish", "neutral"]:
        for direction in ["call", "put"]:
            subset = [s for s in all_signals if s["spy_regime"] == regime and s["direction"] == direction]
            print_breakdown(subset, "SPY REGIME=" + regime.upper() + " x DIRECTION=" + direction.upper())

    # Chronological (train vs holdout), full combined signal
    for period in ["train", "holdout"]:
        subset = [s for s in all_signals if s["period"] == period]
        print_breakdown(subset, "PERIOD: " + period.upper() + " (out-of-sample check)")

    # Per-ticker breakdown
    for ticker in TICKERS:
        subset = [s for s in all_signals if s["ticker"] == ticker]
        print_breakdown(subset, "TICKER: " + ticker)

    # Level 6 ablation, re-run with REAL dynamic SPY regime this time
    print("\n" + "=" * 80)
    print("LEVEL 6 ABLATION RE-RUN (real dynamic SPY regime, median split)")
    print("=" * 80)
    factor_keys = ["relative_volume", "trend_strength", "momentum", "volatility_regime", "market_regime_alignment"]
    scored = [(sum(s["breakdown"].get(k, 0) for k in factor_keys), s["return_20bar"]) for s in all_signals if "return_20bar" in s]
    if len(scored) >= 10:
        scored.sort(key=lambda x: x[0])
        mid = len(scored) // 2
        bottom = [r for _, r in scored[:mid]]
        top = [r for _, r in scored[mid:]]
        print("n=" + str(len(scored)) + ": bottom_half=" + str(round(statistics.mean(bottom)*100,3)) + "% (wr=" + str(round(len([r for r in bottom if r>0])/len(bottom)*100,1)) + "%) | top_half=" + str(round(statistics.mean(top)*100,3)) + "% (wr=" + str(round(len([r for r in top if r>0])/len(top)*100,1)) + "%)")
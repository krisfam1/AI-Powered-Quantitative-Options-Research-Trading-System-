from dotenv import load_dotenv
load_dotenv()

"""
Clean underlying-stock signal validation -- NO option pricing involved,
using only real, accurate stock price data. Answers one question
honestly: does the current entry signal (breakout/breakdown + weighted
entry score) have a genuine, repeatable out-of-sample edge on the
underlying, independent of the synthetic options-pricing layer?

For every qualifying signal: 5/10/20/50-bar forward returns, max
favorable excursion (MFE), max adverse excursion (MAE). Compared
against a RANDOMIZED CONTROL of the same size -- the critical
comparison, since a trending stock shows positive returns for almost
any random entry; the real question is whether the signal beats that.

Sign convention: positive = favorable for the position's direction
(both calls and puts), negative = adverse. This makes call and put
results directly comparable.
"""

import random
import statistics
import backtest_engine as be
from entry_scorer import calculate_entry_score

HORIZONS = [5, 10, 20, 50]
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]


def find_qualifying_signals(ticker: str, bars: list, direction: str, entry_score_threshold: float = 20, spy_regime: str = "neutral") -> list:
    """Every index where the CURRENT entry logic qualifies: breakout/breakdown gate + weighted score >= threshold."""
    signals = []
    for index in range(60, len(bars)):
        if direction == "call" and not be.check_breakout(bars, index, lookback=20):
            continue
        if direction == "put" and not be.check_breakdown(bars, index, lookback=20):
            continue
        try:
            score_result = calculate_entry_score(ticker, bars, index, direction, spy_regime=spy_regime)
        except Exception:
            continue
        if score_result["total_score"] >= entry_score_threshold:
            signals.append({"index": index, "score": score_result["total_score"], "timestamp": bars[index].timestamp})
    return signals


def calculate_forward_stats(bars: list, index: int, direction: str, horizons: list = HORIZONS) -> dict:
    """Forward returns at each horizon, plus MFE/MAE up to the longest horizon. Positive = favorable for the position."""
    entry_price = float(bars[index].close)
    max_horizon = max(horizons)

    prices_ahead = []
    results = {}
    for h in range(1, max_horizon + 1):
        if index + h >= len(bars):
            break
        price = float(bars[index + h].close)
        prices_ahead.append(price)
        if h in horizons:
            raw_ret = (price - entry_price) / entry_price
            results["return_" + str(h) + "bar"] = raw_ret if direction == "call" else -raw_ret

    if prices_ahead:
        if direction == "call":
            results["mfe"] = (max(prices_ahead) - entry_price) / entry_price
            results["mae"] = (min(prices_ahead) - entry_price) / entry_price
        else:
            results["mfe"] = (entry_price - min(prices_ahead)) / entry_price
            results["mae"] = (entry_price - max(prices_ahead)) / entry_price

    return results


def generate_random_control(bars: list, n: int, seed: int = 42) -> list:
    """N random indices, NOT conditioned on any signal -- the critical baseline comparison."""
    random.seed(seed)
    valid_range = range(60, len(bars) - max(HORIZONS) - 1)
    if len(valid_range) < n:
        return list(valid_range)
    return random.sample(list(valid_range), n)


def _summarize(stat_dicts: list, key: str) -> dict:
    values = [d[key] for d in stat_dicts if key in d]
    if not values:
        return {"n": 0, "mean": None, "median": None, "win_rate_pct": None}
    wins = [v for v in values if v > 0]
    return {
        "n": len(values),
        "mean": round(statistics.mean(values) * 100, 3),
        "median": round(statistics.median(values) * 100, 3),
        "win_rate_pct": round(len(wins) / len(values) * 100, 1),
    }


def run_core_validation():
    all_signal_stats = []
    all_random_stats = []

    for ticker in TICKERS:
        for direction in ["call", "put"]:
            from datetime import datetime, timezone, timedelta
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=90)
            bars = be.get_historical_bars(ticker, start, end)
            if not bars:
                continue

            signals = find_qualifying_signals(ticker, bars, direction)
            print(ticker + " " + direction + ": " + str(len(signals)) + " qualifying signals")

            for sig in signals:
                stats = calculate_forward_stats(bars, sig["index"], direction)
                stats["ticker"] = ticker
                stats["direction"] = direction
                stats["score"] = sig["score"]
                all_signal_stats.append(stats)

            random_indices = generate_random_control(bars, len(signals))
            for idx in random_indices:
                stats = calculate_forward_stats(bars, idx, direction)
                stats["ticker"] = ticker
                stats["direction"] = direction
                all_random_stats.append(stats)

    print("\n" + "=" * 80)
    print("SIGNAL vs. RANDOM CONTROL -- forward returns and excursion (ALL tickers/directions combined)")
    print("=" * 80)

    for key in ["return_5bar", "return_10bar", "return_20bar", "return_50bar", "mfe", "mae"]:
        sig_summary = _summarize(all_signal_stats, key)
        rand_summary = _summarize(all_random_stats, key)
        print("\n" + key + ":")
        print("  SIGNAL: n=" + str(sig_summary["n"]) + " mean=" + str(sig_summary["mean"]) + "% median=" + str(sig_summary["median"]) + "% win_rate=" + str(sig_summary["win_rate_pct"]) + "%")
        print("  RANDOM: n=" + str(rand_summary["n"]) + " mean=" + str(rand_summary["mean"]) + "% median=" + str(rand_summary["median"]) + "% win_rate=" + str(rand_summary["win_rate_pct"]) + "%")

    return all_signal_stats, all_random_stats


if __name__ == "__main__":
    run_core_validation()
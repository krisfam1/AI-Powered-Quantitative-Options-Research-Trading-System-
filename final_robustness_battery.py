from dotenv import load_dotenv
load_dotenv()

"""
Final robustness battery for the frozen bullish x call baseline -- three
genuinely new tests, none touching or optimizing the strategy itself:

1. Statistical significance (t-test): is the observed signal-vs-random
   difference actually distinguishable from noise, or could pure chance
   easily produce what we're seeing?

2. Signal clustering/autocorrelation: are the ~761 "signals" genuinely
   independent observations, or mostly the same few trending moves
   counted many times over consecutive bars? If heavily clustered, the
   real effective sample size is much smaller than the raw count.

3. Multi-seed random control stability: does the signal's advantage
   hold up regardless of which specific random sample was drawn, or
   was the earlier result sensitive to one lucky/unlucky seed?
"""

import random
import statistics
from scipy import stats
import backtest_engine as be
from backtest_engine import get_daily_regime
from entry_scorer import calculate_entry_score
from signal_validation_core import calculate_forward_stats, TICKERS
from datetime import datetime, timezone, timedelta

end = datetime.now(timezone.utc)
full_start = end - timedelta(days=90)


def collect_bullish_call_signals_and_pool():
    signals = []
    bullish_pool = []  # (ticker, index, bars) for every bullish-regime bar, for random control
    for ticker in TICKERS:
        bars = be.get_historical_bars(ticker, full_start, end)
        if not bars:
            continue
        for index in range(60, len(bars)):
            timestamp = bars[index].timestamp
            try:
                spy_regime = get_daily_regime("SPY", timestamp, period=50)
            except Exception:
                continue
            if spy_regime != "bullish":
                continue
            bullish_pool.append((ticker, index, bars))

            if not be.check_breakout(bars, index, lookback=20):
                continue
            try:
                score_result = calculate_entry_score(ticker, bars, index, "call", spy_regime=spy_regime)
            except Exception:
                continue
            if score_result["total_score"] < 20:
                continue
            fwd_stats = calculate_forward_stats(bars, index, "call")
            signals.append({"ticker": ticker, "index": index, **fwd_stats})
        print(ticker + ": done")
    return signals, bullish_pool


if __name__ == "__main__":
    print("Collecting bullish x call signals and full bullish-regime bar pool...\n")
    signals, bullish_pool = collect_bullish_call_signals_and_pool()
    print("\nTotal signals: " + str(len(signals)) + " | Bullish-regime bar pool: " + str(len(bullish_pool)))

    print("\n" + "=" * 80)
    print("TEST 1: Statistical significance (t-test, signal vs. one random control sample)")
    print("=" * 80)
    random.seed(42)
    random_sample = random.sample(bullish_pool, min(len(signals), len(bullish_pool)))
    random_results = [calculate_forward_stats(bars, idx, "call") for (t, idx, bars) in random_sample]

    for metric in ["return_5bar", "return_10bar", "return_20bar", "return_50bar"]:
        sig_vals = [s[metric] for s in signals if metric in s]
        rand_vals = [r[metric] for r in random_results if metric in r]
        if len(sig_vals) < 10 or len(rand_vals) < 10:
            print(metric + ": insufficient data")
            continue
        t_stat, p_value = stats.ttest_ind(sig_vals, rand_vals, equal_var=False)
        significant = "YES (p<0.05)" if p_value < 0.05 else "NO (p>=0.05)"
        print(metric + ": signal_mean=" + str(round(statistics.mean(sig_vals)*100,3)) + "% random_mean=" + str(round(statistics.mean(rand_vals)*100,3)) + "% | t=" + str(round(t_stat,3)) + " p=" + str(round(p_value,4)) + " -- statistically significant: " + significant)

    print("\n" + "=" * 80)
    print("TEST 2: Signal clustering / autocorrelation (real effective sample size)")
    print("=" * 80)
    for ticker in TICKERS:
        ticker_indices = sorted([s["index"] for s in signals if s["ticker"] == ticker])
        if len(ticker_indices) < 2:
            continue
        clusters = 1
        for i in range(1, len(ticker_indices)):
            if ticker_indices[i] - ticker_indices[i-1] > 12:  # more than 1 hour apart = new cluster
                clusters += 1
        print(ticker + ": " + str(len(ticker_indices)) + " raw signals -> ~" + str(clusters) + " independent clusters (gap > 12 bars = 1hr)")

    print("\n" + "=" * 80)
    print("TEST 3: Multi-seed random control stability (return_20bar)")
    print("=" * 80)
    sig_vals_20 = [s["return_20bar"] for s in signals if "return_20bar" in s]
    sig_mean_20 = statistics.mean(sig_vals_20)
    print("Signal mean (fixed): " + str(round(sig_mean_20*100, 3)) + "%")
    for seed in [1, 2, 3, 4, 5]:
        random.seed(seed)
        sample = random.sample(bullish_pool, min(len(signals), len(bullish_pool)))
        rand_results = [calculate_forward_stats(bars, idx, "call") for (t, idx, bars) in sample]
        rand_vals = [r["return_20bar"] for r in rand_results if "return_20bar" in r]
        rand_mean = statistics.mean(rand_vals)
        beats_random = sig_mean_20 > rand_mean
        print("  Seed " + str(seed) + ": random_mean=" + str(round(rand_mean*100,3)) + "% | signal beats random: " + str(beats_random))
from dotenv import load_dotenv
load_dotenv()

"""
Phase 6 EXPLORATORY analyses (pre-specified). NONE of these are
confirmatory and NONE can overturn the primary confirmatory result
(p=0.996-0.997, signal did not beat regime-matched random control).
Baseline strategy, thresholds, score weights, data window unchanged.
"""

import statistics
from datetime import datetime, timezone
from collections import defaultdict
import backtest_engine as be
from entry_scorer import calculate_entry_score
from backtest_engine import get_daily_regime

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
HORIZONS = [5, 10, 20, 50]
SCORE_BINS = [(20, 30), (30, 40), (40, 999)]  # predefined BEFORE seeing outcomes

print("Rebuilding real signal population (identical methodology to the confirmatory run)...\n")
all_bars = {}
daily_regime = {}
for ticker in TICKERS:
    bars = be.get_historical_bars(ticker, FIXED_START, FIXED_END)
    all_bars[ticker] = bars
    for d in sorted(set(b.timestamp.date() for b in bars)):
        ts = datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)
        try:
            daily_regime[(ticker, d)] = get_daily_regime(ticker, ts, period=50)
        except Exception:
            daily_regime[(ticker, d)] = "unknown"

real_signals = []
for ticker in TICKERS:
    bars = all_bars[ticker]
    for index in range(60, len(bars)):
        bar_date = bars[index].timestamp.date()
        if daily_regime.get((ticker, bar_date)) != "bullish":
            continue
        if not be.check_breakout(bars, index, lookback=20):
            continue
        try:
            score_result = calculate_entry_score(ticker, bars, index, "call", spy_regime="bullish")
        except Exception:
            continue
        if score_result["total_score"] >= 20:
            real_signals.append({"ticker": ticker, "index": index, "date": bar_date, "score": score_result["total_score"]})

def forward_return(bars, index, horizon):
    if index + horizon >= len(bars):
        return None
    entry = float(bars[index].close)
    exitp = float(bars[index + horizon].close)
    return (exitp - entry) / entry

for sig in real_signals:
    for h in HORIZONS:
        sig["ret" + str(h)] = forward_return(all_bars[sig["ticker"]], sig["index"], h)

valid_signals = [s for s in real_signals if s["ret20"] is not None]
print("Total valid signals: " + str(len(valid_signals)) + "\n")

def day_clustered_mean(signals, key):
    by_day = defaultdict(list)
    for s in signals:
        if s.get(key) is not None:
            by_day[s["date"]].append(s[key])
    means = [statistics.mean(v) for v in by_day.values()]
    return statistics.mean(means) if means else None, len(means)

print("=" * 100)
print("EXPLORATORY 1: LEAVE-ONE-TICKER-OUT")
print("=" * 100)
print("(All results EXPLORATORY -- descriptive only, no significance testing)")
full_T, full_days = day_clustered_mean(valid_signals, "ret20")
print("Full population: T=" + str(round(full_T*100,4)) + "% (n=" + str(len(valid_signals)) + ", days=" + str(full_days) + ")")
for excl in TICKERS:
    subset = [s for s in valid_signals if s["ticker"] != excl]
    T, days = day_clustered_mean(subset, "ret20")
    print("  Excluding " + excl + ": T=" + str(round(T*100,4) if T else None) + "% (n=" + str(len(subset)) + ", days=" + str(days) + ")")

print("\n" + "=" * 100)
print("EXPLORATORY 2: PREDEFINED SCORE BINS")
print("=" * 100)
print("(Bins defined BEFORE examining outcomes: [20-30), [30-40), [40+))")
for low, high in SCORE_BINS:
    bin_signals = [s for s in valid_signals if low <= s["score"] < high]
    if not bin_signals:
        print("  [" + str(low) + "-" + str(high) + "): no signals")
        continue
    T, days = day_clustered_mean(bin_signals, "ret20")
    returns = [s["ret20"] for s in bin_signals]
    win_rate = len([r for r in returns if r > 0]) / len(returns) * 100
    print("  [" + str(low) + "-" + str(high) + "): n=" + str(len(bin_signals)) + " mean_return=" + str(round(statistics.mean(returns)*100,3)) + "% day_clustered_T=" + str(round(T*100,3) if T else None) + "% win_rate=" + str(round(win_rate,1)) + "%")

print("\n" + "=" * 100)
print("EXPLORATORY 3: HOLDING-HORIZON ROBUSTNESS (5/10/20/50 bars)")
print("=" * 100)
for h in HORIZONS:
    key = "ret" + str(h)
    h_signals = [s for s in valid_signals if s.get(key) is not None]
    T, days = day_clustered_mean(h_signals, key)
    returns = [s[key] for s in h_signals]
    win_rate = len([r for r in returns if r > 0]) / len(returns) * 100
    print("  " + str(h) + "-bar: n=" + str(len(h_signals)) + " mean=" + str(round(statistics.mean(returns)*100,3)) + "% day_clustered_T=" + str(round(T*100,3) if T else None) + "% win_rate=" + str(round(win_rate,1)) + "%")

print("\n" + "=" * 100)
print("EXPLORATORY 4: CONCENTRATION ANALYSIS")
print("=" * 100)
by_ticker_contribution = defaultdict(list)
for s in valid_signals:
    by_ticker_contribution[s["ticker"]].append(s["ret20"])
print("Contribution by ticker (sum of ret20, and count):")
for tk in TICKERS:
    vals = by_ticker_contribution[tk]
    if vals:
        print("  " + tk + ": sum=" + str(round(sum(vals)*100,2)) + "% n=" + str(len(vals)) + " mean=" + str(round(statistics.mean(vals)*100,3)) + "%")

by_day_contribution = defaultdict(list)
for s in valid_signals:
    by_day_contribution[s["date"]].append(s["ret20"])
day_sums = sorted([(d, sum(v)) for d, v in by_day_contribution.items()], key=lambda x: x[1])
print("\nLargest single-day negative contributor: " + str(day_sums[0][0]) + " sum_ret20=" + str(round(day_sums[0][1]*100,3)) + "%")
print("Largest single-day positive contributor: " + str(day_sums[-1][0]) + " sum_ret20=" + str(round(day_sums[-1][1]*100,3)) + "%")

sorted_signals = sorted(valid_signals, key=lambda s: s["ret20"])
print("\nLargest individual losers (ret20):")
for s in sorted_signals[:5]:
    print("  " + s["ticker"] + " " + str(s["date"]) + " score=" + str(round(s["score"],1)) + " ret20=" + str(round(s["ret20"]*100,2)) + "%")
print("Largest individual winners (ret20):")
for s in sorted_signals[-5:]:
    print("  " + s["ticker"] + " " + str(s["date"]) + " score=" + str(round(s["score"],1)) + " ret20=" + str(round(s["ret20"]*100,2)) + "%")

top10_sum = sum(s["ret20"] for s in sorted_signals[-10:])
total_sum = sum(s["ret20"] for s in valid_signals)
print("\nTop 10 winners' contribution to total ret20 sum: " + str(round(top10_sum/total_sum*100,1) if total_sum else None) + "% of total")

print("\n" + "=" * 100)
print("REMINDER: ALL RESULTS ABOVE ARE EXPLORATORY/DESCRIPTIVE")
print("=" * 100)
print("Primary confirmatory result stands unchanged: p=0.996-0.997 (primary control),")
print("p=1.0 (secondary control) -- the signal did NOT beat regime-matched random control.")
print("Exploratory findings above may help explain the PATTERN of this result but cannot")
print("overturn or supersede the confirmatory conclusion.")

print("\nPHASE 6 EXPLORATORY ANALYSES COMPLETE.")
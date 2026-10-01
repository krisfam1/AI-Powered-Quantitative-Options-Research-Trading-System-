from dotenv import load_dotenv
load_dotenv()

import backtest_engine as be
from entry_scorer import calculate_entry_score
from datetime import datetime, timezone, timedelta

end = datetime.now(timezone.utc)
start = end - timedelta(days=90)

ticker = "AMD"
threshold = 15

bars = be.get_historical_bars(ticker, start, end)
print("Scanning " + str(len(bars)) + " bars for " + ticker + " at threshold " + str(threshold) + "...\n")

qualifying_scores = []

for index in range(60, len(bars)):
    for direction in ["call", "put"]:
        try:
            result = calculate_entry_score(ticker, bars, index, direction)
            if result["total_score"] >= threshold:
                qualifying_scores.append(result["breakdown"])
        except Exception:
            continue

print("Total qualifying signals found: " + str(len(qualifying_scores)) + "\n")

if qualifying_scores:
    factor_names = list(qualifying_scores[0].keys())
    print("Average contribution per factor, among qualifying signals:")
    for factor in factor_names:
        avg = sum(s[factor] for s in qualifying_scores) / len(qualifying_scores)
        nonzero_pct = len([s for s in qualifying_scores if s[factor] > 0]) / len(qualifying_scores) * 100
        print("  " + factor + ": avg=" + str(round(avg, 2)) + "  (nonzero in " + str(round(nonzero_pct, 1)) + "% of signals)")

    print("\nHow many signals had ZERO breakout_magnitude (no real breakout at all):")
    zero_breakout = len([s for s in qualifying_scores if s["breakout_magnitude"] == 0])
    print("  " + str(zero_breakout) + " of " + str(len(qualifying_scores)) + " (" + str(round(zero_breakout/len(qualifying_scores)*100, 1)) + "%)")
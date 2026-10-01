from dotenv import load_dotenv
load_dotenv()

"""
Look-ahead bias check: for a real sample of qualifying bullish x call
signals, recomputes the entry score using ONLY bars truncated up to and
including the signal index (removing all future bars entirely), and
compares against the score computed with the full bars array (which
includes future data). If there's no look-ahead leak, these must be
IDENTICAL -- any difference would mean some function is inadvertently
using future information the strategy would not have had access to in
real time.
"""

import backtest_engine as be
from backtest_engine import get_daily_regime
from entry_scorer import calculate_entry_score
from datetime import datetime, timezone, timedelta

end = datetime.now(timezone.utc)
start = end - timedelta(days=90)

TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
SAMPLE_SIZE_PER_TICKER = 15

mismatches = []
total_checked = 0

for ticker in TICKERS:
    bars = be.get_historical_bars(ticker, start, end)
    if not bars:
        continue

    checked_for_ticker = 0
    for index in range(60, len(bars)):
        if checked_for_ticker >= SAMPLE_SIZE_PER_TICKER:
            break
        if not be.check_breakout(bars, index, lookback=20):
            continue

        timestamp = bars[index].timestamp
        try:
            spy_regime_full = get_daily_regime("SPY", timestamp, period=50)
        except Exception:
            continue

        score_full = calculate_entry_score(ticker, bars, index, "call", spy_regime=spy_regime_full)
        if score_full["total_score"] < 20:
            continue

        truncated_bars = bars[:index + 1]
        breakout_truncated = be.check_breakout(truncated_bars, index, lookback=20)
        score_truncated = calculate_entry_score(ticker, truncated_bars, index, "call", spy_regime=spy_regime_full)

        total_checked += 1
        checked_for_ticker += 1

        if not breakout_truncated:
            mismatches.append(ticker + " idx=" + str(index) + ": breakout check DIFFERS with future data removed")
        if abs(score_full["total_score"] - score_truncated["total_score"]) > 0.01:
            mismatches.append(ticker + " idx=" + str(index) + ": score DIFFERS -- full=" + str(score_full["total_score"]) + " truncated=" + str(score_truncated["total_score"]))

print("Total signals checked: " + str(total_checked))
print("Mismatches found: " + str(len(mismatches)))
if mismatches:
    print("\nLOOK-AHEAD BIAS DETECTED:")
    for m in mismatches:
        print("  " + m)
else:
    print("\nNo look-ahead bias detected -- entry scores are identical whether or not future bars are present in the data.")
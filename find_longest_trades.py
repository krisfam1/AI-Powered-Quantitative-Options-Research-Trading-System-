from dotenv import load_dotenv
load_dotenv()

"""
Step 1: search the full 6-ticker V1 dataset for the genuinely
longest-held trades. Does not manufacture or extend anything --
reports what actually exists.
"""

from datetime import datetime, timezone
from portfolio_backtest import run_portfolio_backtest

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]

print("Searching all 6 tickers for the longest-held V1 trades...\n")
all_trades = []
for ticker in TICKERS:
    v1 = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v1")
    for t in v1["closed_trades"]:
        t["_ticker"] = ticker
        t["_holding_days"] = (t["exit_date"] - t["entry_date"]).days
        all_trades.append(t)
    print(ticker + ": " + str(len(v1["closed_trades"])) + " trades processed")

all_trades_sorted = sorted(all_trades, key=lambda t: t["_holding_days"], reverse=True)

print("\n" + "=" * 90)
print("TOP 10 LONGEST-HELD TRADES (all tickers)")
print("=" * 90)
for t in all_trades_sorted[:10]:
    print(t["_ticker"] + ": entry=" + str(t["entry_date"]) + " exit=" + str(t["exit_date"]) + " holding_days=" + str(t["_holding_days"]) + " strike=" + str(t["strike"]) + " exit_reason=" + t["exit_reason"])

print("\n" + "=" * 90)
print("HOLDING-PERIOD DISTRIBUTION")
print("=" * 90)
from collections import Counter
dist = Counter(t["_holding_days"] for t in all_trades)
for days in sorted(dist.keys()):
    print(str(days) + " days: " + str(dist[days]) + " trades")

print("\nSEARCH COMPLETE.")
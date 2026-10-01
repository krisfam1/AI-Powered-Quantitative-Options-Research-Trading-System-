from dotenv import load_dotenv
load_dotenv()

"""
Step 1: Audits the local 126-trade sample for same-day ticker
collisions (same ticker, same calendar date, multiple distinct
signal clusters) -- the suspected root cause of the reproduction
mismatch. Regenerates the LOCAL, free sample only (no API calls, no
strategy changes) to get exact timestamps, which were never saved to
iv_correction_diagnostic.db.
"""

from datetime import datetime, timezone
from portfolio_backtest import run_portfolio_backtest

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]

print("Regenerating the local 126-trade sample (free, no API cost)...\n")
all_trades = []
for ticker in TICKERS:
    result = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call")
    for t in result["closed_trades"]:
        t["_ticker"] = ticker
        all_trades.append(t)

all_trades = sorted(all_trades, key=lambda t: (str(t["entry_date"]), t["_ticker"]))
sample = all_trades[::2]
print("Sample size: " + str(len(sample)) + "\n")

by_ticker_date = {}
for t in sample:
    key = (t["_ticker"], str(t["entry_date"]))
    by_ticker_date.setdefault(key, []).append(t)

collisions = {k: v for k, v in by_ticker_date.items() if len(v) > 1}

print("=" * 100)
print("COLLISION AUDIT")
print("=" * 100)
print("Total distinct (ticker, date) keys: " + str(len(by_ticker_date)))
print("Keys with MULTIPLE trades (collisions): " + str(len(collisions)))
print("Total trades involved in collisions: " + str(sum(len(v) for v in collisions.values())))
print("Records that would be OVERWRITTEN (all but the last-inserted): " + str(sum(len(v) - 1 for v in collisions.values())))

if collisions:
    print("\nExact colliding trades:")
    for (ticker, date), trades in sorted(collisions.items()):
        print("\n  " + ticker + " " + date + " -- " + str(len(trades)) + " trades:")
        for t in trades:
            print("    entry_premium=$" + str(round(t["entry_premium"],3)) + " strike=" + str(t["strike"]) + " exit_reason=" + t["exit_reason"] + " pnl=$" + str(round(t["pnl_dollars"],2)))
        print("  (INSERT OR REPLACE would have kept only the LAST of these -- the others were silently lost)")

expected_from_125_with_2_dupes = len(sample) - sum(len(v) - 1 for v in collisions.values())
print("\n" + "=" * 100)
print("DOES THIS EXPLAIN THE 126 -> 124 DISCREPANCY?")
print("=" * 100)
print("Sample size: " + str(len(sample)))
print("Expected saved count if collisions are the ONLY cause: " + str(expected_from_125_with_2_dupes))
print("Actual saved count in iv_correction_diagnostic.db: 124")
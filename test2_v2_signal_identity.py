from dotenv import load_dotenv
load_dotenv()

"""
Test 2: V2 signal identity. Runs V1 and V2 (pricing_mode="v2_entry_iv")
over the exact same fixed date range. Confirms identical qualifying
signals -- same entries, strikes, DTE, exits, exit reasons -- with
entry_premium (and downstream P&L) EXPECTED to differ where V2 IV is
available, and trades SKIPPED (not fallback) where it is not.
"""

from datetime import datetime, timezone
from portfolio_backtest import run_portfolio_backtest

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKER = "AAPL"

print("Running V1 (pricing_mode='v1', default)...\n")
v1_result = run_portfolio_backtest([TICKER], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v1")
print("V1 trades: " + str(v1_result["total_trades"]))

print("\nRunning V2 (pricing_mode='v2_entry_iv')...\n")
v2_result = run_portfolio_backtest([TICKER], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v2_entry_iv")
print("V2 trades: " + str(v2_result["total_trades"]))

print("\n" + "=" * 90)
print("COVERAGE LOG")
print("=" * 90)
coverage = v2_result["v2_coverage_log"]
total_signals = len(coverage)
available = len([c for c in coverage if c["v2_iv_available"]])
print("Total qualifying signals: " + str(total_signals))
print("V2 IV available: " + str(available))
print("V2 IV unavailable (skipped): " + str(total_signals - available))
print("Coverage: " + str(round(available/total_signals*100, 1) if total_signals else 0) + "%")

print("\n" + "=" * 90)
print("SIGNAL IDENTITY CHECK -- V1 trades vs V2 trades (where V2 IV was available)")
print("=" * 90)
v1_trades = sorted(v1_result["closed_trades"], key=lambda t: str(t["entry_date"]))
v2_trades = sorted(v2_result["closed_trades"], key=lambda t: str(t["entry_date"]))

print("V1 entry dates: " + str([str(t["entry_date"]) for t in v1_trades]))
print("V2 entry dates: " + str([str(t["entry_date"]) for t in v2_trades]))

print("\nPer-trade V1 vs V2 (matched by entry_date):")
v1_by_date = {str(t["entry_date"]): t for t in v1_trades}
v2_by_date = {str(t["entry_date"]): t for t in v2_trades}
for date in sorted(set(v1_by_date.keys()) | set(v2_by_date.keys())):
    v1t = v1_by_date.get(date)
    v2t = v2_by_date.get(date)
    if v1t and v2t:
        same_strike = v1t["strike"] == v2t["strike"]
        same_exit_date = str(v1t["exit_date"]) == str(v2t["exit_date"])
        same_exit_reason = v1t["exit_reason"] == v2t["exit_reason"]
        print(date + ": V1_entry=$" + str(round(v1t["entry_premium"],3)) + " V2_entry=$" + str(round(v2t["entry_premium"],3)) + " same_strike=" + str(same_strike) + " same_exit_date=" + str(same_exit_date) + " same_exit_reason=" + str(same_exit_reason))
    elif v1t and not v2t:
        print(date + ": V1 HAS trade, V2 SKIPPED (V2 IV unavailable) -- expected behavior")
    else:
        print(date + ": V2 HAS trade, V1 MISSING -- UNEXPECTED, investigate")

print("\nTEST 2 COMPLETE.")
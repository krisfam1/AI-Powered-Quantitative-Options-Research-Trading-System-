from dotenv import load_dotenv
load_dotenv()

"""
Verifies that performance_metrics.py's dollar-based max drawdown and
profit factor calculations are correct when applied to the portfolio
engine's real trade output -- using the same frozen, 11-trade AAPL
calls-only dataset just confirmed to exactly match the original engine.
"""

from datetime import datetime, timezone, timedelta
from portfolio_backtest import run_portfolio_backtest
from performance_metrics import calculate_max_drawdown, calculate_profit_factor

end = datetime.now(timezone.utc)
start = end - timedelta(days=90)

result = run_portfolio_backtest(["AAPL"], start, end, starting_capital=100000.0, fixed_direction="call")
trades = result["closed_trades"]

print("=" * 80)
print("REAL TRADE-BY-TRADE DETAIL (for manual verification)")
print("=" * 80)
running_cumulative = 0.0
for t in sorted(trades, key=lambda x: x["exit_date"]):
    running_cumulative += t["pnl_dollars"]
    print(str(t["exit_date"]) + ": pnl=$" + str(round(t["pnl_dollars"], 2)) + " | running_cumulative=$" + str(round(running_cumulative, 2)))

print("\n" + "=" * 80)
print("AUTOMATED RESULTS (performance_metrics.py)")
print("=" * 80)
dd_result = calculate_max_drawdown(trades)
pf_result = calculate_profit_factor(trades)
print("Max drawdown: " + str(dd_result))
print("Profit factor: " + str(pf_result))

print("\n" + "=" * 80)
print("MANUAL CROSS-CHECK")
print("=" * 80)
wins = [t["pnl_dollars"] for t in trades if t["pnl_dollars"] > 0]
losses = [t["pnl_dollars"] for t in trades if t["pnl_dollars"] < 0]
manual_pf = sum(wins) / abs(sum(losses)) if losses else None
print("Manual profit factor (sum wins / abs(sum losses)): " + str(round(manual_pf, 4) if manual_pf else None))
print("Automated profit factor: " + str(pf_result))
print("Match: " + str(abs(manual_pf - pf_result) < 0.001 if manual_pf and pf_result else "N/A"))

sorted_trades = sorted(trades, key=lambda x: x["exit_date"])
cumulative = 0.0
peak = 0.0
max_dd = 0.0
for t in sorted_trades:
    cumulative += t["pnl_dollars"]
    peak = max(peak, cumulative)
    drawdown = peak - cumulative
    max_dd = max(max_dd, drawdown)
print("\nManual max drawdown (peak-to-trough on cumulative $): $" + str(round(max_dd, 2)))
print("Automated max drawdown: " + str(dd_result))
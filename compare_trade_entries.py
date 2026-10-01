from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timezone, timedelta
from options_backtest_engine import run_options_backtest
from portfolio_backtest import run_portfolio_backtest

end = datetime.now(timezone.utc)
start = end - timedelta(days=30)

TICKER = "AAPL"

print("=" * 70)
print("ORIGINAL, VALIDATED ENGINE -- " + TICKER + " (calls only, matching its actual default)")
print("=" * 70)
original_result = run_options_backtest(
    TICKER, start, end, dte_target=14, option_type="call",
    entry_mode="weighted", entry_score_threshold=20,
    target_delta=0.30, apply_spread_cost=True, exit_mode="reversal_guard",
)
print("Total trades: " + str(original_result["total_trades"]))
original_dates = sorted(str(t["entry_date"]) for t in original_result.get("trades", []))
print("Entry dates: " + str(original_dates))

print("\n" + "=" * 70)
print("NEW PORTFOLIO ENGINE -- " + TICKER + " (calls only, for true apples-to-apples comparison)")
print("=" * 70)
portfolio_result = run_portfolio_backtest([TICKER], start, end, starting_capital=100000.0, fixed_direction="call")
print("Total trades: " + str(portfolio_result["total_trades"]))
portfolio_dates = sorted(str(t["entry_date"]) for t in portfolio_result["closed_trades"])
print("Entry dates: " + str(portfolio_dates))

print("\n" + "=" * 70)
print("DIFFERENCE")
print("=" * 70)
from collections import Counter
orig_counts = Counter(original_dates)
port_counts = Counter(portfolio_dates)
all_dates = sorted(set(original_dates) | set(portfolio_dates))
for d in all_dates:
    o = orig_counts.get(d, 0)
    p = port_counts.get(d, 0)
    if o != p:
        print("  " + d + ": original=" + str(o) + " portfolio=" + str(p))
from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timezone, timedelta, date
from portfolio_backtest import run_portfolio_backtest

end = datetime.now(timezone.utc)
start = end - timedelta(days=30)

result = run_portfolio_backtest(["AAPL"], start, end, starting_capital=100000.0)

target_date = date(2026, 8, 19)
print("All AAPL trades on " + str(target_date) + ":\n")

for t in result["closed_trades"]:
    if t["entry_date"] == target_date:
        print("Entry: " + str(t["entry_date"]) + " | Exit: " + str(t["exit_date"]))
        print("  option_type: " + t["option_type"] + " | strike: " + str(t["strike"]))
        print("  entry_premium: $" + str(round(t["entry_premium"], 2)) + " -> exit_premium: $" + str(round(t["exit_premium"], 2)))
        print("  exit_reason: " + t["exit_reason"] + " | pnl_pct: " + str(round(t["pnl_pct"], 1)) + "%")
        print("")
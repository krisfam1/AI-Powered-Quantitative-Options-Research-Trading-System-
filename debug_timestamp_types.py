from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timezone
from portfolio_backtest import run_portfolio_backtest
import backtest_engine as be

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)

result = run_portfolio_backtest(["AAPL"], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call")
trade = result["closed_trades"][0]

print("entry_date value: " + repr(trade["entry_date"]))
print("entry_date type: " + str(type(trade["entry_date"])))

bars = be.get_historical_bars("AAPL", FIXED_START, FIXED_END)
print("\nFirst bar timestamp value: " + repr(bars[0].timestamp))
print("First bar timestamp type: " + str(type(bars[0].timestamp)))

print("\nAll trade dict keys: " + str(list(trade.keys())))
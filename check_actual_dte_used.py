from dotenv import load_dotenv
load_dotenv()

import inspect
from options_backtest_engine import calculate_historical_volatility
from portfolio_backtest import run_portfolio_backtest
from datetime import datetime, timezone

# Search portfolio_backtest.py source for how it calls black_scholes_price -- specifically what DTE value it passes
import portfolio_backtest
source = inspect.getsource(portfolio_backtest)

# Find lines mentioning black_scholes_price calls
lines = source.split("\n")
for i, line in enumerate(lines):
    if "black_scholes_price(" in line:
        print("Line " + str(i) + ": " + line.strip())
        # print a few lines of context
        for j in range(max(0, i-3), min(len(lines), i+2)):
            print("  ctx[" + str(j) + "]: " + lines[j])
        print()
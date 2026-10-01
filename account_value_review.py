from dotenv import load_dotenv
load_dotenv()

import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetPortfolioHistoryRequest

api_key = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")
client = TradingClient(api_key, secret_key, paper=True)

print("=" * 60)
print("CURRENT ACCOUNT STATUS")
print("=" * 60)

account = client.get_account()
print("Equity:            $" + str(account.equity))
print("Cash:               $" + str(account.cash))
print("Buying power:        $" + str(account.buying_power))
print("Last equity (prior close): $" + str(account.last_equity))

try:
    todays_change = float(account.equity) - float(account.last_equity)
    print("Change since last close: $" + str(round(todays_change, 2)))
except Exception:
    pass

print("\n" + "=" * 60)
print("PORTFOLIO HISTORY")
print("=" * 60)

try:
    history_request = GetPortfolioHistoryRequest(period="1M", timeframe="1D")
    history = client.get_portfolio_history(history_request)

    if history.equity:
        print("Starting equity (earliest in window): $" + str(history.equity[0]))
        print("Current equity (most recent):         $" + str(history.equity[-1]))
        total_change = history.equity[-1] - history.equity[0]
        total_change_pct = (total_change / history.equity[0] * 100) if history.equity[0] else 0
        print("Total change: $" + str(round(total_change, 2)) + " (" + str(round(total_change_pct, 2)) + "%)")
        print("\nDay-by-day equity:")
        for i, (ts, eq) in enumerate(zip(history.timestamp, history.equity)):
            if eq is not None:
                print("  " + str(ts) + ": $" + str(eq))
    else:
        print("No portfolio history data returned.")
except Exception as exc:
    print("Could not fetch portfolio history: " + str(exc))
import os
from alpaca.trading.client import TradingClient

api_key = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")

trading_client = TradingClient(api_key, secret_key, paper=True)

account = trading_client.get_account()

print("Connection successful!")
print(f"Account status: {account.status}")
print(f"Cash: ${account.cash}")
print(f"Buying power: ${account.buying_power}")
print(f"Portfolio value: ${account.portfolio_value}")
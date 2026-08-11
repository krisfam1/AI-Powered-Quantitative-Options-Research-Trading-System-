import os
from datetime import datetime, timedelta, timezone

from alpaca.data import StockBarsRequest, StockHistoricalDataClient
from alpaca.data.enums import DataFeed
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
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

data_client = StockHistoricalDataClient(api_key, secret_key)

end = datetime.now(timezone.utc)
start = end - timedelta(days=30)
bars_request = StockBarsRequest(
    symbol_or_symbols="AAPL",
    timeframe=TimeFrame(1, TimeFrameUnit.Day),
    start=start,
    end=end,
    limit=10,
    feed=DataFeed.IEX,
)
bars = data_client.get_stock_bars(bars_request)

print("\nRecent AAPL daily bars:")
for bar in bars["AAPL"]:
    print(f"{bar.timestamp.date()}: close=${bar.close:.2f}, volume={bar.volume:,}")
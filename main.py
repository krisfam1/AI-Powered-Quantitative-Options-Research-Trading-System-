import os
from datetime import datetime, timedelta, timezone

from alpaca.data import StockBarsRequest, StockHistoricalDataClient
from alpaca.data.enums import DataFeed
from alpaca.data.historical.news import NewsClient, NewsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient

from backtest_engine import print_backtest_summary, run_backtest
import trade_log


trade_log.init_db()
trade_log.log_trade_entry(
    {
        "trade_id": "test-trade-001",
        "timestamp_entry": "2026-08-11T14:30:00+00:00",
        "ticker": "AAPL",
        "signal_type": "breakout",
        "volume_at_entry": 1500000.0,
        "relative_volume": 1.8,
        "price_action_pattern": "ascending triangle",
        "news_present": 1,
        "news_sentiment_score": 0.72,
        "news_headline_summary": "Apple product news supports bullish momentum",
        "entry_price": 325.50,
        "position_size": 10.0,
        "stop_loss_price": 320.00,
        "target_price": 335.00,
        "risk_amount": 55.00,
    }
)

with trade_log.sqlite3.connect(trade_log.DATABASE_PATH) as connection:
    trade_rows = connection.execute("SELECT * FROM trades").fetchall()

print("\nTrade log rows:")
for trade_row in trade_rows:
    print(trade_row)

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

news_client = NewsClient(api_key, secret_key)
news_request = NewsRequest(
    symbols="AAPL",
    limit=5,
    sort="desc",
)
news = news_client.get_news(news_request)

print("\nRecent AAPL news:")
for article in news.data["news"]:
    print(f"{article.created_at.date()}: {article.headline}")
    print(f"  Source: {article.source}")

backtest_end = datetime.now(timezone.utc)
backtest_start = backtest_end - timedelta(days=30)
run_backtest("AAPL", backtest_start, backtest_end)
print_backtest_summary()
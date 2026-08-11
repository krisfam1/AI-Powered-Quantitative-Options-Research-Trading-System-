import os
from datetime import datetime, timedelta, timezone

from alpaca.data import StockBarsRequest, StockHistoricalDataClient
from alpaca.data.enums import DataFeed
from alpaca.data.historical.news import NewsClient, NewsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient

import trade_log
import ai_analyst
import optimizer


# ── Trade log bootstrap ───────────────────────────────────────────────────────
trade_log.init_db()
trade_log.clear_trades()


# ── Alpaca connection ─────────────────────────────────────────────────────────
api_key = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")

trading_client = TradingClient(api_key, secret_key, paper=True)
account = trading_client.get_account()

print("\nConnection successful!")
print(f"Account status: {account.status}")
print(f"Cash: ${account.cash}")
print(f"Buying power: ${account.buying_power}")
print(f"Portfolio value: ${account.portfolio_value}")


# ── Market data clients ───────────────────────────────────────────────────────
data_client = StockHistoricalDataClient(api_key, secret_key)
news_client = NewsClient(api_key, secret_key)

TICKERS = ["AAPL", "TSLA", "NVDA", "KO", "JPM"]
NEWS_PER_TICKER = 8
DAILY_BARS_LOOKBACK_DAYS = 30

end = datetime.now(timezone.utc)
bars_start = end - timedelta(days=DAILY_BARS_LOOKBACK_DAYS)


# ── Per-ticker data fetch ─────────────────────────────────────────────────────
ticker_bars: dict[str, list] = {}
ticker_news: dict[str, list] = {}

for ticker in TICKERS:
    print(f"\nFetching data for {ticker}...")

    bars_request = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame(1, TimeFrameUnit.Day),
        start=bars_start,
        end=end,
        feed=DataFeed.IEX,
    )
    bars_response = data_client.get_stock_bars(bars_request)
    try:
        ticker_bars[ticker] = list(bars_response[ticker])
    except (KeyError, TypeError):
        ticker_bars[ticker] = []

    news_request = NewsRequest(
        symbols=ticker,
        limit=NEWS_PER_TICKER,
        sort="desc",
    )
    news_response = news_client.get_news(news_request)
    ticker_news[ticker] = news_response.data.get("news", [])

    bars = ticker_bars[ticker]
    news = ticker_news[ticker]

    if bars:
        print(f"  {len(bars)} daily bars  |  last close ${float(bars[-1].close):.2f}")
    if news:
        print(f"  {len(news)} news articles  |  latest: {news[0].headline[:60]}…")


# ── AI Wealth Management Research Desk ───────────────────────────────────────
print("\n" + "═" * 64)
print("  WEALTH MANAGEMENT RESEARCH DESK  —  powered by Claude")
print("═" * 64)

for ticker in TICKERS:
    print(f"\n{'─' * 60}")
    print(f"  RESEARCH BRIEF: {ticker}")
    print(f"{'─' * 60}")
    brief = ai_analyst.research_ticker(
        ticker=ticker,
        bars=ticker_bars[ticker],
        news_articles=ticker_news[ticker],
    )
    print(brief)


# ── Claude-Driven Optimization Loop ──────────────────────────────────────────
backtest_end = datetime.now(timezone.utc)
backtest_start = backtest_end - timedelta(days=90)

optimizer.run(
    tickers=TICKERS,
    start_date=backtest_start,
    end_date=backtest_end,
    target_win_rate=80.0,
    max_iterations=10,
)

import os
from datetime import datetime, timedelta, timezone

from alpaca.data import StockBarsRequest, StockHistoricalDataClient
from alpaca.data.enums import DataFeed
from alpaca.data.historical.news import NewsClient, NewsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient

from backtest_engine import run_multi_ticker_backtest
import trade_log
import ai_analyst


# ── Trade log bootstrap ───────────────────────────────────────────────────────
trade_log.init_db()
trade_log.clear_trades()
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


# ── Backtests ─────────────────────────────────────────────────────────────────
backtest_end = datetime.now(timezone.utc)
backtest_start = backtest_end - timedelta(days=90)

exit_strategies = {
    "fixed_pct": {
        "name": "fixed_pct",
        "mode": "fixed_pct",
        "stop_loss_pct": 0.01,
        "take_profit_pct": 0.02,
    },
    "atr_tight": {
        "name": "atr_tight",
        "mode": "atr",
        "atr_stop_multiplier": 1.5,
        "atr_target_multiplier": 2.5,
        "atr_trail_trigger": 1.0,
        "atr_trail_distance": 1.5,
    },
    "atr_loose": {
        "name": "atr_loose",
        "mode": "atr",
        "atr_stop_multiplier": 1.5,
        "atr_target_multiplier": 2.5,
        "atr_trail_trigger": 2.0,
        "atr_trail_distance": 2.0,
    },
}

comparison: dict[str, dict[str, float]] = {}
# Also track per-ticker stats for the best variant (atr_loose) to pass to research briefs
ticker_backtest_stats: dict[str, dict[str, float]] = {}

for variant_name, exit_strategy in exit_strategies.items():
    print(f"\nRunning {variant_name} across {', '.join(TICKERS)}...")
    trade_log.clear_trades()
    comparison[variant_name] = run_multi_ticker_backtest(
        TICKERS,
        backtest_start,
        backtest_end,
        exit_strategy,
    )

# Collect per-ticker stats for atr_loose (best performing variant from prior run)
from backtest_engine import run_backtest
print("\nCollecting per-ticker stats for atr_loose (for AI research context)...")
trade_log.clear_trades()
for ticker in TICKERS:
    prefix = f"atr_loose-{ticker.upper()}"
    stats = run_backtest(
        ticker,
        backtest_start,
        backtest_end,
        exit_strategies["atr_loose"],
        trade_id_prefix=prefix,
    )
    ticker_backtest_stats[ticker] = stats


# ── Strategy comparison table ─────────────────────────────────────────────────
print("\nExit strategy comparison:")
print(
    f"{'Variant':<12} {'Trades':>8} {'Win rate':>10} "
    f"{'Avg win':>10} {'Avg loss':>10} {'Net P&L':>10}"
)
print("-" * 64)
for variant_name, stats in comparison.items():
    print(
        f"{variant_name:<12} {int(stats['total_trades']):>8} "
        f"{stats['win_rate']:>9.2f}% {stats['average_win_pct']:>9.2f}% "
        f"{stats['average_loss_pct']:>9.2f}% {stats['net_pnl_pct']:>9.2f}%"
    )


# ── AI Wealth Management Research ─────────────────────────────────────────────
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
        backtest_stats=ticker_backtest_stats.get(ticker),
    )
    print(brief)

print(f"\n{'═' * 64}")
print("  STRATEGY ANALYSIS  —  Quantitative Portfolio Manager")
print(f"{'═' * 64}\n")
strategy_analysis = ai_analyst.compare_strategies(TICKERS, comparison)
print(strategy_analysis)

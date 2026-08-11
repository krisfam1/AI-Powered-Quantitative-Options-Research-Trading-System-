"""Main entry point.

Set MODE below to choose what happens when you click Run:

  "live"     – single pass of the live paper-trading signal check (fast, ~10 s)
  "research" – full research briefs + Claude optimisation loop (slow, ~10 min)
"""

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
import live_trader

# ── Choose run mode ───────────────────────────────────────────────────────────
MODE = "live"   # "live" | "research"

# ── Alpaca connection (shared by both modes) ──────────────────────────────────
api_key    = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")

trading_client = TradingClient(api_key, secret_key, paper=True)
account        = trading_client.get_account()

print("\nConnection successful!")
print(f"Account status:    {account.status}")
print(f"Cash:              ${float(account.cash):,.2f}")
print(f"Buying power:      ${float(account.buying_power):,.2f}")
print(f"Portfolio value:   ${float(account.portfolio_value):,.2f}")


# ════════════════════════════════════════════════════════════════════════════
# LIVE MODE — single-pass paper-trading signal check
# ════════════════════════════════════════════════════════════════════════════

LIVE_TICKERS = ["AAPL", "TSLA", "NVDA"]


def run_live_trading_cycle() -> None:
    """Check each ticker for entry signals and submit bracket orders if warranted.

    Loops through LIVE_TICKERS once, calls live_trader.check_signal_and_trade()
    for each, then prints a cycle summary.  Every check — fired or not — is
    logged to signal_log.db for review.
    """
    print("\n" + "═" * 68)
    print("  LIVE TRADING CYCLE  —  paper account")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("═" * 68)

    from pathlib import Path
    if Path("STOP_TRADING").exists():
        print("\n  ⛔  STOP_TRADING file present — all trading is paused.")
        print("      Remove the file to resume.\n")
        return

    results: list[dict] = []
    for ticker in LIVE_TICKERS:
        print(f"\n  Checking {ticker}...")
        result = live_trader.check_signal_and_trade(ticker)
        results.append(result)

        if result["signal_fired"]:
            print(f"    ✓  ORDER PLACED")
            print(f"       {result['note']}")
            print(f"       Order ID: {result['order_id']}")
        else:
            blocked_by = "; ".join(result["blocks"]) if result["blocks"] else result.get("note", "unknown")
            print(f"    –  No trade  →  {blocked_by}")

    # ── Cycle summary ─────────────────────────────────────────────────────────
    print("\n" + "─" * 68)
    print("  CYCLE SUMMARY")
    print("─" * 68)
    fired   = [r for r in results if r["signal_fired"]]
    skipped = [r for r in results if not r["signal_fired"]]

    print(f"  Tickers checked : {len(results)}")
    print(f"  Orders placed   : {len(fired)}")
    print(f"  No signal       : {len(skipped)}")

    if fired:
        print("\n  Orders this cycle:")
        for r in fired:
            print(
                f"    {r['ticker']:<6}  {r['position_size']} shares  "
                f"@ ~${r['entry_price']:.2f}   id={r['order_id']}"
            )

    if skipped:
        print("\n  Skipped:")
        for r in skipped:
            reason = (
                "; ".join(r["blocks"]) if r["blocks"]
                else r.get("note") or "—"
            )
            print(f"    {r['ticker']:<6}  {reason}")

    print("\n  Full signal history → signal_log.db")
    print("─" * 68 + "\n")


# ════════════════════════════════════════════════════════════════════════════
# RESEARCH MODE — full research briefs + Claude optimisation loop
# ════════════════════════════════════════════════════════════════════════════

RESEARCH_TICKERS        = ["AAPL", "TSLA", "NVDA", "KO", "JPM"]
NEWS_PER_TICKER         = 8
DAILY_BARS_LOOKBACK_DAYS = 30


def run_research_cycle() -> None:
    """Fetch market data, generate AI research briefs, then run the optimizer."""
    trade_log.init_db()
    trade_log.clear_trades()

    data_client = StockHistoricalDataClient(api_key, secret_key)
    news_client = NewsClient(api_key, secret_key)

    end        = datetime.now(timezone.utc)
    bars_start = end - timedelta(days=DAILY_BARS_LOOKBACK_DAYS)

    ticker_bars: dict[str, list] = {}
    ticker_news: dict[str, list] = {}

    for ticker in RESEARCH_TICKERS:
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

    print("\n" + "═" * 64)
    print("  WEALTH MANAGEMENT RESEARCH DESK  —  powered by Claude")
    print("═" * 64)

    for ticker in RESEARCH_TICKERS:
        print(f"\n{'─' * 60}")
        print(f"  RESEARCH BRIEF: {ticker}")
        print(f"{'─' * 60}")
        brief = ai_analyst.research_ticker(
            ticker=ticker,
            bars=ticker_bars[ticker],
            news_articles=ticker_news[ticker],
        )
        print(brief)

    backtest_end   = datetime.now(timezone.utc)
    backtest_start = backtest_end - timedelta(days=90)
    optimizer.run(
        tickers=RESEARCH_TICKERS,
        start_date=backtest_start,
        end_date=backtest_end,
        min_win_rate=40.0,
        max_iterations=4,
        training_days=60,
    )


# ════════════════════════════════════════════════════════════════════════════
# Dispatch
# ════════════════════════════════════════════════════════════════════════════

if MODE == "live":
    run_live_trading_cycle()
elif MODE == "research":
    run_research_cycle()
else:
    print(f"Unknown MODE '{MODE}'. Set MODE to 'live' or 'research'.")

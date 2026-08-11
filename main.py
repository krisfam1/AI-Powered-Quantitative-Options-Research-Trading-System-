"""Main entry point.

MODE controls what runs when you click Run in the workspace:

  "live"     – single pass of the live signal check (~10 s, good for manual testing)
  "research" – full research briefs + Claude optimisation loop (~10 min)

The deployed VM always runs in loop mode regardless of MODE, controlled by the
TRADING_LOOP environment variable (set to "1" in the deployment secrets).
"""

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from alpaca.data import StockBarsRequest, StockHistoricalDataClient
from alpaca.data.enums import DataFeed
from alpaca.data.historical.news import NewsClient, NewsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient

import trade_log
import ai_analyst
import optimizer
import live_trader
import kill_server

# ── Settings ──────────────────────────────────────────────────────────────────
# In the workspace: set MODE to "live" or "research", leave LOOP = False.
# In the deployed VM: TRADING_LOOP=1 is set as an environment secret, which
#   overrides MODE and always runs the continuous loop.
MODE = "live"   # "live" | "research"  (workspace only)
LOOP = os.getenv("TRADING_LOOP", "0") == "1"

LIVE_TICKERS       = ["AAPL", "TSLA", "NVDA"]
RESEARCH_TICKERS   = ["AAPL", "TSLA", "NVDA", "KO", "JPM"]
CYCLE_INTERVAL_SEC = 5 * 60     # 5 minutes between signal checks
ET                 = ZoneInfo("America/New_York")

# ── Alpaca connection ─────────────────────────────────────────────────────────
api_key    = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")

trading_client = TradingClient(api_key, secret_key, paper=True)
account        = trading_client.get_account()

print("\nConnection successful!")
print(f"Account status:    {account.status}")
print(f"Cash:              ${float(account.cash):,.2f}")
print(f"Buying power:      ${float(account.buying_power):,.2f}")
print(f"Portfolio value:   ${float(account.portfolio_value):,.2f}")


# ── Market-hours helpers ───────────────────────────────────────────────────────
def is_market_open() -> bool:
    """Return True if US equities market is currently open (9:30–16:00 ET, M–F)."""
    now_et = datetime.now(ET)
    if now_et.weekday() >= 5:           # Saturday = 5, Sunday = 6
        return False
    t = now_et.time()
    from datetime import time as dtime
    return dtime(9, 30) <= t < dtime(16, 0)


def market_closed_for_day() -> bool:
    """Return True after 4:05 PM ET on a weekday — signal to stop the loop today."""
    now_et = datetime.now(ET)
    if now_et.weekday() >= 5:
        return False
    from datetime import time as dtime
    return now_et.time() >= dtime(16, 5)


def minutes_to_open() -> int:
    """Return whole minutes until 9:30 AM ET today, or 0 if already past open."""
    now_et = datetime.now(ET)
    open_today = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    if now_et >= open_today:
        return 0
    return int((open_today - now_et).total_seconds() // 60)


# ════════════════════════════════════════════════════════════════════════════
# LIVE MODE — single-pass signal check  (used by both loop and manual runs)
# ════════════════════════════════════════════════════════════════════════════

def run_live_trading_cycle() -> list[dict]:
    """Check each ticker once and return the list of result dicts.

    Also prints a human-readable cycle summary.  Every check is logged to
    signal_log.db regardless of outcome.
    """
    ts_str = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
    print("\n" + "═" * 68)
    print(f"  SIGNAL CHECK  —  {ts_str}  —  paper account")
    print("═" * 68)

    results: list[dict] = []
    for ticker in LIVE_TICKERS:
        print(f"\n  Checking {ticker}...")
        result = live_trader.check_signal_and_trade(ticker)
        results.append(result)

        if result["signal_fired"]:
            print(f"    ✓  ORDER PLACED — {result['note']}")
            print(f"       Order ID: {result['order_id']}")
        else:
            reason = (
                "; ".join(result["blocks"]) if result["blocks"]
                else result.get("note") or "—"
            )
            print(f"    –  No trade  →  {reason}")

    fired   = [r for r in results if r["signal_fired"]]
    skipped = [r for r in results if not r["signal_fired"]]

    print("\n" + "─" * 68)
    print(f"  Tickers checked: {len(results)}  |  "
          f"Orders placed: {len(fired)}  |  No signal: {len(skipped)}")
    if fired:
        for r in fired:
            print(f"    ✓ {r['ticker']}: {r['position_size']} sh "
                  f"@ ~${r['entry_price']:.2f}  id={r['order_id']}")
    if skipped:
        for r in skipped:
            reason = "; ".join(r["blocks"]) if r["blocks"] else r.get("note") or "—"
            print(f"    – {r['ticker']}: {reason}")
    print("─" * 68)

    return results


# ════════════════════════════════════════════════════════════════════════════
# LOOP MODE — continuous execution during market hours  (used by the VM)
# ════════════════════════════════════════════════════════════════════════════

def run_live_trading_loop() -> None:
    """Run signal checks every 5 minutes during market hours.

    This is the entry point for the deployed VM.  It runs until 4:05 PM ET,
    then exits so the VM process is clean.  The deployed VM automatically
    restarts the process — but market-hours logic here ensures no trades are
    attempted outside 9:30 AM – 4:00 PM ET on weekdays.

    On every iteration (whether market is open or not):
    - The STOP_TRADING kill switch is checked first.
    - Outside market hours: logs the status and sleeps 60 s before rechecking.
    - Inside market hours: runs one full signal cycle, then sleeps 5 min.
    - After 4:05 PM ET on a weekday: logs end-of-day and exits cleanly.
    """
    print("\n" + "█" * 68)
    print("  LIVE TRADING LOOP  —  paper VM  —  starting up")
    print(f"  Tickers : {', '.join(LIVE_TICKERS)}")
    print(f"  Interval: every {CYCLE_INTERVAL_SEC // 60} minutes during market hours")
    print(f"  Hours   : 9:30 AM – 4:00 PM ET, Mon – Fri")
    print(f"  Kill sw : visit /stop?token=… on the deployed URL, or create STOP_TRADING file")
    print("█" * 68 + "\n")

    # Start control panel — runs in a background thread on port 8080
    # From your phone: https://YOUR-APP.replit.app/status?token=YOUR_TOKEN
    kill_server.start(port=8080)

    total_cycles   = 0
    total_orders   = 0
    today_date_et  = datetime.now(ET).date()

    while True:
        now_et  = datetime.now(ET)
        now_str = now_et.strftime("%Y-%m-%d %H:%M ET")

        # ── New day bookkeeping ───────────────────────────────────────────────
        if now_et.date() != today_date_et:
            today_date_et  = now_et.date()
            print(f"\n  ── New trading day: {today_date_et} ──\n")

        # ── Kill switch — checked every single iteration ──────────────────────
        if Path("STOP_TRADING").exists():
            print(f"  [{now_str}]  ⛔  STOP_TRADING file present — trading paused. "
                  f"Rechecking in 60 s.")
            _log_loop_event("PAUSED", "STOP_TRADING file present")
            time.sleep(60)
            continue

        # ── End-of-day exit — clean shutdown after market close ───────────────
        if market_closed_for_day():
            print(f"\n  [{now_str}]  Market closed for today ({today_date_et}).")
            print(f"  Loop ran {total_cycles} cycles, placed {total_orders} orders today.")
            print("  Exiting — VM will restart; market-hours check guards next session.\n")
            _log_loop_event("EOD", f"Exiting after {total_cycles} cycles, {total_orders} orders")
            sys.exit(0)

        # ── Pre-market / weekend wait ─────────────────────────────────────────
        if not is_market_open():
            mins = minutes_to_open()
            if mins > 0:
                print(f"  [{now_str}]  Pre-market — opens in {mins} min. "
                      f"Sleeping 60 s.")
            elif now_et.weekday() >= 5:
                day = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][now_et.weekday()]
                print(f"  [{now_str}]  Weekend ({day}). Sleeping 60 s.")
            else:
                print(f"  [{now_str}]  Market closed. Sleeping 60 s.")
            time.sleep(60)
            continue

        # ── Market is open — run signal check cycle ───────────────────────────
        results      = run_live_trading_cycle()
        total_cycles += 1
        total_orders += sum(1 for r in results if r["signal_fired"])

        next_check_str = (
            datetime.now(ET) + timedelta(seconds=CYCLE_INTERVAL_SEC)
        ).strftime("%H:%M ET")
        print(f"  Sleeping {CYCLE_INTERVAL_SEC // 60} min — "
              f"next check at {next_check_str}")
        time.sleep(CYCLE_INTERVAL_SEC)


def _log_loop_event(event_type: str, note: str) -> None:
    """Write a loop lifecycle event to signal_log.db for the audit trail."""
    import sqlite3
    live_trader._init_signal_log()
    with sqlite3.connect(live_trader.SIGNAL_LOG_DB) as con:
        con.execute(
            """
            INSERT INTO signal_log (checked_at, ticker, signal_fired, blocks, note)
            VALUES (?, ?, 0, '', ?)
            """,
            (datetime.now(timezone.utc).isoformat(), f"[{event_type}]", note),
        )


# ════════════════════════════════════════════════════════════════════════════
# RESEARCH MODE — full research briefs + Claude optimisation loop
# ════════════════════════════════════════════════════════════════════════════

NEWS_PER_TICKER          = 8
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
            print(f"  {len(news)} articles  |  latest: {news[0].headline[:60]}…")

    print("\n" + "═" * 64)
    print("  WEALTH MANAGEMENT RESEARCH DESK  —  powered by Claude")
    print("═" * 64)

    for ticker in RESEARCH_TICKERS:
        print(f"\n{'─' * 60}\n  RESEARCH BRIEF: {ticker}\n{'─' * 60}")
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

if LOOP:
    # Deployed VM: always run the continuous loop
    run_live_trading_loop()
elif MODE == "live":
    # Workspace: single-pass for quick manual testing
    run_live_trading_cycle()
elif MODE == "research":
    run_research_cycle()
else:
    print(f"Unknown MODE '{MODE}'. Set MODE to 'live' or 'research'.")

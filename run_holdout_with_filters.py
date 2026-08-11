"""60-day training / 30-day holdout comparison with MA-trend + news-sentiment filters.

Pre-fetches bars and news once for all 5 tickers, then runs the same config
against the training window (first 60 days) and the holdout window (last 30 days)
so the two periods are directly comparable.
"""

from datetime import datetime, timedelta, timezone

import trade_log
from backtest_engine import (
    get_historical_bars,
    get_news_for_ticker,
    run_multi_ticker_backtest,
)

# ── Universe & date range ─────────────────────────────────────────────────────
TICKERS  = ["AAPL", "TSLA", "NVDA"]
ACCOUNT_EQUITY = 100_000.0

end_date      = datetime.now(timezone.utc)
start_date    = end_date - timedelta(days=90)
cutoff_date   = start_date + timedelta(days=60)   # training / holdout boundary

TRAINING_DAYS = (cutoff_date - start_date).days   # 60
HOLDOUT_DAYS  = (end_date - cutoff_date).days      # ~30

# ── Strategy config ───────────────────────────────────────────────────────────
# atr_loose baseline + MA-trend filter + news-sentiment filter
CONFIG = {
    "mode":                   "atr",
    "name":                   "ma_news",
    # Exit parameters (atr_loose baseline)
    "atr_stop_multiplier":    1.5,
    "atr_target_multiplier":  2.5,
    "atr_trail_trigger":      2.0,
    "atr_trail_distance":     2.0,
    # Core entry filters
    "relative_volume_threshold": 1.5,
    "rv_confirmation_bars":   1,
    "breakout_lookback":      20,
    # Existing optional filters (disabled to isolate the new ones)
    "use_time_window":        False,
    "use_vwap_trend":         False,
    "use_atr_percentile":     False,
    # ── New filters ───────────────────────────────────────────────────────────
    "use_ma_trend":           True,
    "ma_trend_period":        50,
    "use_news_sentiment":     True,
    "news_sentiment_lookback_hours": 24,
}

# ── Helper: print a per-ticker + overall results block ───────────────────────
def print_results(
    label: str,
    period_str: str,
    overall: dict,
    per_ticker: dict,
) -> None:
    width = 80
    print(f"\n{'█' * width}")
    print(f"  {label}")
    print(f"  Period: {period_str}")
    print(f"{'█' * width}")
    print(
        f"\n  {'Ticker':<8} {'Trades':>7} {'Win%':>8} "
        f"{'AvgWin%':>9} {'AvgLoss%':>10} {'NetP&L%':>9} {'Net$':>10}"
    )
    print(f"  {'-'*8} {'-'*7} {'-'*8} {'-'*9} {'-'*10} {'-'*9} {'-'*10}")
    for ticker, s in per_ticker.items():
        print(
            f"  {ticker:<8} {int(s['total_trades']):>7} "
            f"{s['win_rate']:>7.1f}% "
            f"{s['average_win_pct']:>8.2f}% "
            f"{s['average_loss_pct']:>9.2f}% "
            f"{s['net_pnl_pct']:>8.2f}% "
            f"${s['net_pnl_dollars']:>9,.0f}"
        )
    o = overall
    net_ret_pct = o['net_pnl_dollars'] / ACCOUNT_EQUITY * 100
    print(
        f"\n  {'OVERALL':<8} {int(o['total_trades']):>7} "
        f"{o['win_rate']:>7.1f}% "
        f"{o['average_win_pct']:>8.2f}% "
        f"{o['average_loss_pct']:>9.2f}% "
        f"{net_ret_pct:>8.2f}% "
        f"${o['net_pnl_dollars']:>9,.0f}"
    )
    print(f"{'█' * width}")


# ── Bootstrap ─────────────────────────────────────────────────────────────────
trade_log.init_db()

print(f"\n{'═' * 72}")
print("  MA-TREND + NEWS-SENTIMENT FILTER RUN")
print(f"  Full window:  {start_date.date()} → {end_date.date()} (90 days)")
print(f"  Training:     {start_date.date()} → {cutoff_date.date()} ({TRAINING_DAYS} days)")
print(f"  Holdout:      {cutoff_date.date()} → {end_date.date()} ({HOLDOUT_DAYS} days)")
print(f"  Tickers:      {', '.join(TICKERS)}")
print(f"  use_ma_trend:       {CONFIG['use_ma_trend']}  (period={CONFIG['ma_trend_period']})")
print(f"  use_news_sentiment: {CONFIG['use_news_sentiment']}  (lookback={CONFIG['news_sentiment_lookback_hours']}h)")
print(f"{'═' * 72}")

# ── Pre-fetch bars (full 90-day window, split in memory) ───────────────────────
print("\n  Pre-fetching 5-min IEX bars for full 90-day window...")
all_bars:   dict[str, list] = {}
train_bars: dict[str, list] = {}
hold_bars:  dict[str, list] = {}

for ticker in TICKERS:
    bars = get_historical_bars(ticker, start_date, end_date)
    all_bars[ticker] = bars
    cutoff_utc = cutoff_date.astimezone(timezone.utc)
    train_bars[ticker] = [b for b in bars if b.timestamp.astimezone(timezone.utc) < cutoff_utc]
    hold_bars[ticker]  = [b for b in bars if b.timestamp.astimezone(timezone.utc) >= cutoff_utc]
    print(
        f"    {ticker}: {len(bars):,} total  →  "
        f"{len(train_bars[ticker]):,} training / {len(hold_bars[ticker]):,} holdout"
    )

# ── Pre-fetch news (full 90-day window) ───────────────────────────────────────
print("\n  Pre-fetching news for full 90-day window...")
all_news: dict[str, list] = {}
for ticker in TICKERS:
    articles = get_news_for_ticker(ticker, start_date, end_date)
    all_news[ticker] = articles
    print(f"    {ticker}: {len(articles)} articles")

# The backtest's news sentiment check filters by bar timestamp inside the loop,
# so passing the full 90-day news list is correct — it only uses articles that
# precede each signal bar by at most news_sentiment_lookback_hours.

# ── TRAINING RUN ──────────────────────────────────────────────────────────────
print("\n  Running training backtest (60 days)...")
trade_log.clear_trades()
train_overall, train_per_ticker = run_multi_ticker_backtest(
    TICKERS,
    start_date,
    cutoff_date,
    CONFIG,
    prefetched_bars=train_bars,
    prefetched_news=all_news,
    account_equity=ACCOUNT_EQUITY,
)

print_results(
    "TRAINING RESULTS  [in-sample, used for config selection]",
    f"{start_date.date()} → {cutoff_date.date()} ({TRAINING_DAYS} days)",
    train_overall,
    train_per_ticker,
)

# ── HOLDOUT RUN ───────────────────────────────────────────────────────────────
print("\n  Running holdout backtest (30 days)...")
trade_log.clear_trades()
hold_overall, hold_per_ticker = run_multi_ticker_backtest(
    TICKERS,
    cutoff_date,
    end_date,
    CONFIG,
    prefetched_bars=hold_bars,
    prefetched_news=all_news,
    account_equity=ACCOUNT_EQUITY,
)

print_results(
    "OUT-OF-SAMPLE HOLDOUT RESULTS  [never seen during training]",
    f"{cutoff_date.date()} → {end_date.date()} ({HOLDOUT_DAYS} days)",
    hold_overall,
    hold_per_ticker,
)

# ── Side-by-side summary ──────────────────────────────────────────────────────
print(f"\n{'═' * 72}")
print("  TRAIN vs HOLDOUT SUMMARY")
print(f"{'═' * 72}")
print(
    f"\n  {'Period':<14} {'Trades':>7} {'Win%':>8} "
    f"{'AvgWin%':>9} {'AvgLoss%':>10} {'Net%':>8} {'Net$':>10}"
)
print(f"  {'-'*14} {'-'*7} {'-'*8} {'-'*9} {'-'*10} {'-'*8} {'-'*10}")
for label, s in [("Training", train_overall), ("Holdout", hold_overall)]:
    net_ret = s['net_pnl_dollars'] / ACCOUNT_EQUITY * 100
    print(
        f"  {label:<14} {int(s['total_trades']):>7} {s['win_rate']:>7.1f}% "
        f"{s['average_win_pct']:>8.2f}% {s['average_loss_pct']:>9.2f}% "
        f"{net_ret:>7.2f}% ${s['net_pnl_dollars']:>9,.0f}"
    )

generalises = hold_overall["win_rate"] >= 40.0 and hold_overall["net_pnl_pct"] > 0
verdict = (
    "✓  Strategy generalises  (holdout win rate ≥ 40% and net P&L positive)"
    if generalises else
    "✗  Strategy does NOT generalise out-of-sample"
)
print(f"\n  {verdict}")
print(f"{'═' * 72}\n")

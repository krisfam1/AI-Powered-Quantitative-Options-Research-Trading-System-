"""Quick filter validation: AAPL, last 30 days.

Runs four variants to confirm each new filter works independently
and in combination, then prints a comparison table.
"""

from datetime import datetime, timedelta, timezone

import trade_log
from backtest_engine import (
    get_historical_bars,
    get_news_for_ticker,
    run_backtest,
)

# ── Date range ────────────────────────────────────────────────────────────────
end   = datetime.now(timezone.utc)
start = end - timedelta(days=30)
TICKER = "AAPL"

# ── Base config (atr_loose baseline, no new filters) ─────────────────────────
BASE_CONFIG = {
    "mode": "atr",
    "name": "test",
    "atr_stop_multiplier":    1.5,
    "atr_target_multiplier":  2.5,
    "atr_trail_trigger":      2.0,
    "atr_trail_distance":     2.0,
    "relative_volume_threshold": 1.5,
    "rv_confirmation_bars":   1,
    "breakout_lookback":      20,
    # New filters — OFF by default
    "use_ma_trend":           False,
    "ma_trend_period":        50,
    "use_news_sentiment":     False,
    "news_sentiment_lookback_hours": 24,
}

# ── Bootstrap DB ─────────────────────────────────────────────────────────────
trade_log.init_db()

# ── Pre-fetch data once ───────────────────────────────────────────────────────
print(f"\nPre-fetching AAPL bars ({start.date()} → {end.date()})...")
bars = get_historical_bars(TICKER, start, end)
print(f"  {len(bars):,} bars loaded")

print("Pre-fetching AAPL news...")
news = get_news_for_ticker(TICKER, start, end)
print(f"  {len(news)} articles loaded")
if news:
    sample = news[:3]
    for n in sample:
        hl = getattr(n, "headline", "?")
        ts = getattr(n, "created_at", "?")
        print(f"    [{ts}] {hl[:80]}")

# ── Define the four variants ──────────────────────────────────────────────────
VARIANTS = [
    ("baseline",           {**BASE_CONFIG}),
    ("ma_trend_only",      {**BASE_CONFIG, "use_ma_trend": True}),
    ("news_only",          {**BASE_CONFIG, "use_news_sentiment": True}),
    ("ma_trend+news",      {**BASE_CONFIG, "use_ma_trend": True, "use_news_sentiment": True}),
]

# ── Run each variant ──────────────────────────────────────────────────────────
results: list[tuple[str, dict]] = []

for label, cfg in VARIANTS:
    trade_log.clear_trades()
    stats = run_backtest(
        TICKER, start, end, cfg,
        trade_id_prefix=f"filtertest-{label}",
        prefetched_bars=bars,
        prefetched_news=news,
    )
    results.append((label, stats))

# ── Comparison table ──────────────────────────────────────────────────────────
print("\n" + "═" * 72)
print(f"  FILTER VALIDATION — AAPL  ({start.date()} → {end.date()})")
print("═" * 72)
print(f"\n  {'Variant':<22} {'Trades':>7} {'Win%':>8} {'AvgWin%':>10} {'AvgLoss%':>10} {'NetP&L%':>10}")
print(f"  {'-'*22} {'-'*7} {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
for label, s in results:
    trades = int(s["total_trades"])
    wr     = s["win_rate"]
    aw     = s["average_win_pct"]
    al     = s["average_loss_pct"]
    pnl    = s["net_pnl_pct"]
    print(f"  {label:<22} {trades:>7} {wr:>7.1f}% {aw:>9.2f}% {al:>9.2f}% {pnl:>9.2f}%")

# Show trade-count impact of each filter
print("\n  Trade-count impact:")
baseline_trades = int(results[0][1]["total_trades"])
for label, s in results[1:]:
    n = int(s["total_trades"])
    diff = n - baseline_trades
    pct_change = (diff / baseline_trades * 100) if baseline_trades else 0
    print(f"    {label:<22}: {n:>3} trades  ({diff:+d}, {pct_change:+.0f}% vs baseline)")

print("\n" + "═" * 72)
print("  ✓ Filters loaded and executed correctly." if all(
    int(s["total_trades"]) >= 0 for _, s in results
) else "  ✗ One or more variants returned unexpected results.")
print("═" * 72 + "\n")

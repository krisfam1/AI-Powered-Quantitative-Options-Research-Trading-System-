"""90-day multi-ticker comparison: fixed_pct vs atr_tight vs atr_loose."""

import os
from datetime import datetime, timedelta, timezone

import trade_log
from backtest_engine import get_historical_bars, run_multi_ticker_backtest

TICKERS = ["AAPL", "TSLA", "NVDA", "KO", "JPM"]

end = datetime.now(timezone.utc)
start = end - timedelta(days=90)

STRATEGIES = {
    "fixed_pct": {
        "mode": "fixed_pct",
        "name": "fixed_pct",
        "stop_loss_pct": 0.01,
        "take_profit_pct": 0.02,
        "relative_volume_threshold": 1.5,
        "rv_confirmation_bars": 1,
        "breakout_lookback": 20,
    },
    "atr_tight": {
        "mode": "atr",
        "name": "atr_tight",
        "atr_stop_multiplier": 1.5,
        "atr_target_multiplier": 2.5,
        "atr_trail_trigger": 1.0,
        "atr_trail_distance": 1.5,
        "relative_volume_threshold": 1.5,
        "rv_confirmation_bars": 1,
        "breakout_lookback": 20,
    },
    "atr_loose": {
        "mode": "atr",
        "name": "atr_loose",
        "atr_stop_multiplier": 1.5,
        "atr_target_multiplier": 2.5,
        "atr_trail_trigger": 2.0,
        "atr_trail_distance": 2.0,
        "relative_volume_threshold": 1.5,
        "rv_confirmation_bars": 1,
        "breakout_lookback": 20,
    },
}

# ── Bootstrap ─────────────────────────────────────────────────────────────────
trade_log.init_db()

# ── Pre-fetch bars once ───────────────────────────────────────────────────────
print(f"\nPre-fetching 5-min IEX bars ({start.date()} → {end.date()})...")
prefetched: dict[str, list] = {}
for ticker in TICKERS:
    bars = get_historical_bars(ticker, start, end)
    prefetched[ticker] = bars
    print(f"  {ticker}: {len(bars):,} bars")

# ── Run each strategy ─────────────────────────────────────────────────────────
results: dict[str, tuple] = {}   # name → (overall, per_ticker)

for name, config in STRATEGIES.items():
    print(f"\nRunning {name}...")
    trade_log.clear_trades()
    overall, per_ticker = run_multi_ticker_backtest(
        TICKERS, start, end, config, prefetched_bars=prefetched
    )
    results[name] = (overall, per_ticker)

# ── Comparison table ──────────────────────────────────────────────────────────
print("\n" + "═" * 72)
print("  90-DAY STRATEGY COMPARISON  —  AAPL / TSLA / NVDA / KO / JPM")
print("═" * 72)
print(f"\n  {'Strategy':<12} {'Trades':>7} {'Win%':>8} {'AvgWin%':>10} {'AvgLoss%':>10} {'NetP&L%':>10}")
print(f"  {'-'*12} {'-'*7} {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
for name, (overall, _) in results.items():
    print(
        f"  {name:<12} {int(overall['total_trades']):>7} "
        f"{overall['win_rate']:>7.1f}% "
        f"{overall['average_win_pct']:>9.2f}% "
        f"{overall['average_loss_pct']:>9.2f}% "
        f"{overall['net_pnl_pct']:>9.2f}%"
    )

# ── Per-ticker breakdown ──────────────────────────────────────────────────────
for name, (_, per_ticker) in results.items():
    print(f"\n  ── {name} per-ticker ──")
    print(f"  {'Ticker':<8} {'Trades':>7} {'Win%':>8} {'AvgWin%':>10} {'AvgLoss%':>10} {'NetP&L%':>10}")
    print(f"  {'-'*8} {'-'*7} {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
    for ticker, s in per_ticker.items():
        print(
            f"  {ticker:<8} {int(s['total_trades']):>7} "
            f"{s['win_rate']:>7.1f}% "
            f"{s['average_win_pct']:>9.2f}% "
            f"{s['average_loss_pct']:>9.2f}% "
            f"{s['net_pnl_pct']:>9.2f}%"
        )

print("\n" + "═" * 72)

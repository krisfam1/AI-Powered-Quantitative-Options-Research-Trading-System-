"""Claude-driven iterative backtest optimization loop."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import ai_analyst
import trade_log
from backtest_engine import get_historical_bars, run_multi_ticker_backtest


DEFAULT_CONFIG: dict[str, Any] = {
    # Exit strategy (atr_loose baseline)
    "mode": "atr",
    "name": "optimizer",
    "atr_stop_multiplier": 1.5,
    "atr_target_multiplier": 2.5,
    "atr_trail_trigger": 2.0,
    "atr_trail_distance": 2.0,
    # Entry filters (all disabled by default)
    "use_time_window": False,
    "time_windows": [("09:30", "10:30"), ("14:00", "15:00")],
    "use_vwap_trend": False,
    "vwap_lookback": 20,
    "use_atr_percentile": False,
    "atr_percentile_min": 40.0,
    "atr_percentile_lookback": 40,
    "relative_volume_threshold": 1.5,
    "rv_confirmation_bars": 1,
    "breakout_lookback": 20,
}


def _print_header(iteration: int, config: dict[str, Any]) -> None:
    print(f"\n{'═' * 70}")
    print(f"  ITERATION {iteration}")
    print(f"{'═' * 70}")
    print(f"  Config: mode={config['mode']}")
    if config["mode"] == "atr":
        print(
            f"    stop={config['atr_stop_multiplier']}×ATR  "
            f"target={config['atr_target_multiplier']}×ATR  "
            f"trail_trigger={config['atr_trail_trigger']}×ATR  "
            f"trail_dist={config['atr_trail_distance']}×ATR"
        )
    elif config["mode"] == "fixed_pct":
        print(
            f"    stop={config.get('stop_loss_pct', 0)*100:.1f}%  "
            f"target={config.get('take_profit_pct', 0)*100:.1f}%"
        )
    print(
        f"    rv_threshold={config['relative_volume_threshold']}  "
        f"rv_confirmation_bars={config['rv_confirmation_bars']}  "
        f"breakout_lookback={config['breakout_lookback']}"
    )
    print(
        f"    time_window={'ON' if config['use_time_window'] else 'OFF'}  "
        f"vwap_trend={'ON' if config['use_vwap_trend'] else 'OFF'}  "
        f"atr_percentile={'ON' if config['use_atr_percentile'] else 'OFF'}"
    )
    if config["use_atr_percentile"]:
        print(
            f"    atr_pct_min={config['atr_percentile_min']}  "
            f"atr_pct_lookback={config['atr_percentile_lookback']}"
        )


def _print_per_ticker_table(per_ticker: dict[str, dict[str, float]]) -> None:
    print(f"\n  {'Ticker':<8} {'Trades':>7} {'Win%':>8} {'AvgWin%':>10} {'AvgLoss%':>10} {'NetP&L%':>10}")
    print(f"  {'-'*8} {'-'*7} {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
    for ticker, stats in per_ticker.items():
        trades = int(stats.get("total_trades", 0))
        win_rate = stats.get("win_rate", 0.0)
        avg_win = stats.get("average_win_pct", 0.0)
        avg_loss = stats.get("average_loss_pct", 0.0)
        net_pnl = stats.get("net_pnl_pct", 0.0)
        print(
            f"  {ticker:<8} {trades:>7} {win_rate:>7.1f}% {avg_win:>9.2f}% "
            f"{avg_loss:>9.2f}% {net_pnl:>9.2f}%"
        )


def _print_overall(overall: dict[str, float]) -> None:
    print(f"\n  OVERALL: trades={int(overall['total_trades'])}  "
          f"win_rate={overall['win_rate']:.1f}%  "
          f"avg_win={overall['average_win_pct']:.2f}%  "
          f"avg_loss={overall['average_loss_pct']:.2f}%  "
          f"net_pnl={overall['net_pnl_pct']:.2f}%")


def _apply_config_changes(
    current: dict[str, Any], changes: dict[str, Any]
) -> dict[str, Any]:
    """Merge Claude's suggested changes into the current config."""
    updated = dict(current)
    for key, value in changes.items():
        if key in updated or key in DEFAULT_CONFIG:
            updated[key] = value
        else:
            print(f"  [optimizer] Ignoring unknown config key from Claude: {key!r}")
    return updated


def run(
    tickers: list[str],
    start_date: date | datetime | str,
    end_date: date | datetime | str,
    target_win_rate: float = 80.0,
    max_iterations: int = 10,
) -> None:
    """Run the Claude-driven optimization loop."""
    config = dict(DEFAULT_CONFIG)
    history: list[dict[str, Any]] = []

    print(f"\n{'█' * 70}")
    print(f"  CLAUDE-DRIVEN OPTIMIZATION LOOP")
    print(f"  Target: {target_win_rate:.0f}% win rate  |  Max iterations: {max_iterations}")
    print(f"  Tickers: {', '.join(tickers)}")
    print(f"{'█' * 70}")

    # Pre-fetch 5-min bars once — reused across every iteration to avoid
    # redundant Alpaca API calls.
    print("\n  Pre-fetching 5-min bars (one-time)...")
    prefetched: dict[str, list] = {}
    for ticker in tickers:
        bars = get_historical_bars(ticker, start_date, end_date)
        prefetched[ticker] = bars
        print(f"    {ticker}: {len(bars):,} bars")

    for iteration in range(1, max_iterations + 1):
        _print_header(iteration, config)

        # Clear DB so each iteration is independent
        trade_log.clear_trades()

        overall_stats, per_ticker_stats = run_multi_ticker_backtest(
            tickers, start_date, end_date, config,
            prefetched_bars=prefetched,
        )

        _print_per_ticker_table(per_ticker_stats)
        _print_overall(overall_stats)

        # Record this iteration
        history.append(
            {
                "iteration": iteration,
                "config": dict(config),
                "overall_stats": overall_stats,
                "per_ticker_stats": per_ticker_stats,
            }
        )

        # Check target
        if overall_stats["win_rate"] >= target_win_rate:
            print(f"\n  ✓ TARGET REACHED: {overall_stats['win_rate']:.1f}% ≥ {target_win_rate:.0f}%")
            break

        if iteration == max_iterations:
            print(f"\n  ✗ Max iterations reached without hitting target.")
            break

        # Claude diagnosis
        print(f"\n  ── Claude's Diagnosis ──────────────────────────────────────")
        diagnosis = ai_analyst.diagnose_and_suggest(history)
        print(f"  Theme: {diagnosis.get('iteration_theme', 'N/A')}")
        print(f"\n  {diagnosis.get('diagnosis', 'No diagnosis provided.')}")
        print(f"\n  Expected impact: {diagnosis.get('expected_impact', 'N/A')}")

        changes = diagnosis.get("config_changes", {})
        if changes:
            print(f"\n  Changes for next iteration:")
            for k, v in changes.items():
                print(f"    {k}: {config.get(k, '?')} → {v}")
            config = _apply_config_changes(config, changes)
        else:
            print("\n  No config changes suggested — using same config.")

    # Final summary
    print(f"\n{'█' * 70}")
    print(f"  OPTIMIZATION SUMMARY")
    print(f"{'█' * 70}")
    print(f"\n  {'Iter':>5} {'WinRate':>9} {'NetP&L':>9} {'Trades':>7}  Theme")
    print(f"  {'-'*5} {'-'*9} {'-'*9} {'-'*7}  {'-'*30}")
    for entry in history:
        s = entry["overall_stats"]
        theme = entry.get("theme", "—")
        print(
            f"  {entry['iteration']:>5} {s['win_rate']:>8.1f}% "
            f"{s['net_pnl_pct']:>8.2f}% {int(s['total_trades']):>7}  {theme}"
        )

    best = max(history, key=lambda e: e["overall_stats"]["win_rate"])
    print(f"\n  Best iteration: #{best['iteration']} "
          f"({best['overall_stats']['win_rate']:.1f}% win rate, "
          f"{best['overall_stats']['net_pnl_pct']:.2f}% net P&L)")
    print(f"{'█' * 70}\n")

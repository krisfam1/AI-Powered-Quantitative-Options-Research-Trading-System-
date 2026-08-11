"""Claude-driven iterative backtest optimization loop.

Training / holdout split
------------------------
The caller passes a 90-day window.  Internally the first 60 days are used as
the *training* period for the iterative loop; the final 30 days are kept as a
*holdout* set that is touched only once — after the best config is selected —
to give an unbiased out-of-sample estimate.

Optimization objective
----------------------
Maximise net P&L across the training window while keeping win rate ≥ min_win_rate
(default 40 %).  The 80 % win-rate stopping condition has been removed; the
loop always runs to max_iterations (default 4) and then picks the best config.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


def _split_bars(
    bars: list[Any],
    cutoff: datetime,
) -> tuple[list[Any], list[Any]]:
    """Split a bar list into (training, holdout) around a UTC cutoff datetime."""
    cutoff_utc = cutoff.astimezone(timezone.utc)
    training = [b for b in bars if b.timestamp.astimezone(timezone.utc) < cutoff_utc]
    holdout  = [b for b in bars if b.timestamp.astimezone(timezone.utc) >= cutoff_utc]
    return training, holdout


def _print_header(iteration: int, config: dict[str, Any], label: str = "") -> None:
    tag = f"  {label}" if label else ""
    print(f"\n{'═' * 70}")
    print(f"  ITERATION {iteration}{tag}")
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
        trades   = int(stats.get("total_trades", 0))
        win_rate = stats.get("win_rate", 0.0)
        avg_win  = stats.get("average_win_pct", 0.0)
        avg_loss = stats.get("average_loss_pct", 0.0)
        net_pnl  = stats.get("net_pnl_pct", 0.0)
        print(
            f"  {ticker:<8} {trades:>7} {win_rate:>7.1f}% {avg_win:>9.2f}% "
            f"{avg_loss:>9.2f}% {net_pnl:>9.2f}%"
        )


def _print_overall(overall: dict[str, float]) -> None:
    print(
        f"\n  OVERALL: trades={int(overall['total_trades'])}  "
        f"win_rate={overall['win_rate']:.1f}%  "
        f"avg_win={overall['average_win_pct']:.2f}%  "
        f"avg_loss={overall['average_loss_pct']:.2f}%  "
        f"net_pnl={overall['net_pnl_pct']:.2f}%"
    )


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


def _score(overall: dict[str, float], min_win_rate: float) -> float:
    """Return net P&L if win rate qualifies, else a large negative penalty."""
    if overall["win_rate"] >= min_win_rate and overall["total_trades"] >= 10:
        return overall["net_pnl_pct"]
    # Penalised: still comparable so we can fall back if nothing qualifies
    return overall["net_pnl_pct"] - 1000.0


def run(
    tickers: list[str],
    start_date: datetime | str,
    end_date: datetime | str,
    min_win_rate: float = 40.0,
    max_iterations: int = 4,
    training_days: int = 60,
) -> None:
    """Run the Claude-driven optimization loop with a held-out test period.

    Parameters
    ----------
    tickers:
        Universe of tickers to trade.
    start_date / end_date:
        Full date range (e.g. 90 days).  The first *training_days* are used for
        optimization; the remainder form the holdout set.
    min_win_rate:
        Win-rate floor (%) enforced when selecting the best config.  Iterations
        below this threshold are still recorded but penalised in scoring.
    max_iterations:
        Number of training iterations to run.
    training_days:
        Number of calendar days reserved for training (default 60).
    """
    # ── Date arithmetic ───────────────────────────────────────────────────────
    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
    if isinstance(end_date, str):
        end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)

    cutoff = start_date + timedelta(days=training_days)
    holdout_days = (end_date - cutoff).days

    config = dict(DEFAULT_CONFIG)
    history: list[dict[str, Any]] = []

    print(f"\n{'█' * 70}")
    print(f"  CLAUDE-DRIVEN OPTIMIZATION LOOP")
    print(f"  Training: {start_date.date()} → {cutoff.date()} ({training_days} days)")
    print(f"  Holdout:  {cutoff.date()} → {end_date.date()} ({holdout_days} days)")
    print(f"  Objective: maximise net P&L  |  min win rate: {min_win_rate:.0f}%")
    print(f"  Max iterations: {max_iterations}  |  Tickers: {', '.join(tickers)}")
    print(f"{'█' * 70}")

    # ── Pre-fetch full bars once, then split ──────────────────────────────────
    print("\n  Pre-fetching bars for full period (one-time)...")
    train_bars: dict[str, list] = {}
    hold_bars:  dict[str, list] = {}
    for ticker in tickers:
        all_bars = get_historical_bars(ticker, start_date, end_date)
        t, h = _split_bars(all_bars, cutoff)
        train_bars[ticker] = t
        hold_bars[ticker]  = h
        print(f"    {ticker}: {len(all_bars):,} total  →  {len(t):,} training / {len(h):,} holdout")

    # ── Optimization loop (training data only) ────────────────────────────────
    for iteration in range(1, max_iterations + 1):
        _print_header(iteration, config, label="[TRAINING]")

        trade_log.clear_trades()
        overall_stats, per_ticker_stats = run_multi_ticker_backtest(
            tickers, start_date, cutoff, config,
            prefetched_bars=train_bars,
        )

        _print_per_ticker_table(per_ticker_stats)
        _print_overall(overall_stats)

        qualifies = (
            overall_stats["win_rate"] >= min_win_rate
            and overall_stats["total_trades"] >= 10
        )
        flag = "✓" if qualifies else f"✗ (win rate {overall_stats['win_rate']:.1f}% < {min_win_rate:.0f}% floor)"
        print(f"\n  Qualifies for selection: {flag}")

        history.append({
            "iteration": iteration,
            "config": dict(config),
            "overall_stats": overall_stats,
            "per_ticker_stats": per_ticker_stats,
            "score": _score(overall_stats, min_win_rate),
        })

        if iteration == max_iterations:
            print(f"\n  Max iterations reached — selecting best config.")
            break

        # ── Claude diagnosis ──────────────────────────────────────────────────
        print(f"\n  ── Claude's Diagnosis ──────────────────────────────────────")
        diagnosis = ai_analyst.diagnose_and_suggest(history, min_win_rate=min_win_rate)
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

    # ── Select best config ────────────────────────────────────────────────────
    best_entry = max(history, key=lambda e: e["score"])
    best_iter  = best_entry["iteration"]
    best_config = best_entry["config"]
    best_train  = best_entry["overall_stats"]

    # ── Training summary table ────────────────────────────────────────────────
    print(f"\n{'█' * 70}")
    print(f"  TRAINING SUMMARY")
    print(f"{'█' * 70}")
    print(f"\n  {'Iter':>5} {'WinRate':>9} {'NetP&L':>9} {'Trades':>7}  {'Qual':>5}  Theme")
    print(f"  {'-'*5} {'-'*9} {'-'*9} {'-'*7}  {'-'*5}  {'-'*28}")
    for entry in history:
        s     = entry["overall_stats"]
        qual  = "YES" if s["win_rate"] >= min_win_rate and s["total_trades"] >= 10 else "no"
        mark  = " ◀ best" if entry["iteration"] == best_iter else ""
        theme = entry.get("theme", "—")
        print(
            f"  {entry['iteration']:>5} {s['win_rate']:>8.1f}% "
            f"{s['net_pnl_pct']:>8.2f}% {int(s['total_trades']):>7}  {qual:>5}  {theme}{mark}"
        )

    print(f"\n  Best config: iteration #{best_iter}  "
          f"(train win rate {best_train['win_rate']:.1f}%,  "
          f"train net P&L {best_train['net_pnl_pct']:.2f}%)")

    # ── Holdout evaluation (out-of-sample) ────────────────────────────────────
    print(f"\n{'█' * 70}")
    print(f"  OUT-OF-SAMPLE HOLDOUT RESULTS")
    print(f"  Period: {cutoff.date()} → {end_date.date()} ({holdout_days} days)")
    print(f"  Config: iteration #{best_iter} — NEVER seen during optimization")
    print(f"{'█' * 70}")

    trade_log.clear_trades()
    hold_overall, hold_per_ticker = run_multi_ticker_backtest(
        tickers, cutoff, end_date, best_config,
        prefetched_bars=hold_bars,
    )

    _print_per_ticker_table(hold_per_ticker)
    _print_overall(hold_overall)

    # Side-by-side train vs holdout
    print(f"\n  ── Train vs Holdout comparison ──────────────────────────────────")
    print(f"  {'Period':<12} {'Trades':>7} {'Win%':>8} {'AvgWin%':>10} {'AvgLoss%':>10} {'NetP&L%':>10}")
    print(f"  {'-'*12} {'-'*7} {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
    for label, s in [("Training", best_train), ("Holdout", hold_overall)]:
        print(
            f"  {label:<12} {int(s['total_trades']):>7} {s['win_rate']:>7.1f}% "
            f"{s['average_win_pct']:>9.2f}% {s['average_loss_pct']:>9.2f}% "
            f"{s['net_pnl_pct']:>9.2f}%"
        )

    generalises = (
        hold_overall["win_rate"] >= min_win_rate
        and hold_overall["net_pnl_pct"] > 0
    )
    verdict = "✓ Strategy generalises (positive P&L + win rate above floor)" \
              if generalises else \
              "✗ Strategy does NOT generalise out-of-sample"
    print(f"\n  {verdict}")
    print(f"{'█' * 70}\n")

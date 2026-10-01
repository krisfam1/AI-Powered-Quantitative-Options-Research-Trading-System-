from dotenv import load_dotenv
load_dotenv()

"""
Real, reusable performance metrics: Sharpe ratio, Sortino ratio, maximum
drawdown, and profit factor. Works on any list of trades (dicts with at
least pnl_pct, pnl_dollars, entry_date, exit_date) -- applicable to
backtest results, real live trade history, or SPY gamma bot trades alike.

HONEST METHODOLOGY NOTE: Sharpe/Sortino here are computed on PER-TRADE
returns (not daily portfolio returns), then annualized based on the
real, observed trade frequency over the actual date range. This is a
standard, practical approximation for irregular-interval trading
strategies, but is NOT identical to the classic daily-return Sharpe
ratio used for continuously-held portfolios -- worth knowing when
comparing to published Sharpe ratios from other sources.
"""

import math
from datetime import date


def _parse_date(d):
    if isinstance(d, str):
        return date.fromisoformat(d)
    return d


def calculate_max_drawdown(trades: list[dict]) -> dict:
    """Reconstructs a running cumulative P&L curve (chronological by exit_date), tracks the largest peak-to-trough decline."""
    sorted_trades = sorted(trades, key=lambda t: _parse_date(t["exit_date"]))

    cumulative = 0.0
    peak = 0.0
    ever_positive = False
    max_dd_dollars = 0.0
    max_dd_pct = 0.0

    for t in sorted_trades:
        cumulative += t["pnl_dollars"]
        if cumulative > peak:
            peak = cumulative
            ever_positive = True
        drawdown_dollars = peak - cumulative
        if drawdown_dollars > max_dd_dollars:
            max_dd_dollars = drawdown_dollars
            max_dd_pct = (drawdown_dollars / peak * 100) if peak > 0 else None

    # HONEST FIX: if cumulative trade P&L never rose above $0, "peak" stays
    # at 0 and a percentage is genuinely undefined (dividing by a $0
    # reference point is meaningless) -- report None with a clear note,
    # rather than misleadingly showing 0% (which implies no drawdown when
    # a real, substantial dollar drawdown may have occurred).
    if not ever_positive:
        return {
            "max_drawdown_dollars": round(max_dd_dollars, 2),
            "max_drawdown_pct": None,
            "max_drawdown_note": "cumulative trade P&L never rose above $0, so a percentage from a positive peak is undefined -- see dollar figure instead",
        }

    return {"max_drawdown_dollars": round(max_dd_dollars, 2), "max_drawdown_pct": round(max_dd_pct, 2) if max_dd_pct is not None else None}


def calculate_profit_factor(trades: list[dict]) -> float | None:
    """Gross wins / gross losses. None if there are no losses (undefined/infinite)."""
    gross_wins = sum(t["pnl_dollars"] for t in trades if t["pnl_dollars"] > 0)
    gross_losses = abs(sum(t["pnl_dollars"] for t in trades if t["pnl_dollars"] < 0))
    if gross_losses == 0:
        return None
    return round(gross_wins / gross_losses, 2)


def _annualization_factor(trades: list[dict]) -> float:
    """Estimates trades-per-year from the real, observed date range, for annualizing per-trade Sharpe/Sortino."""
    if len(trades) < 2:
        return 1.0
    dates = sorted(_parse_date(t["exit_date"]) for t in trades)
    span_days = (dates[-1] - dates[0]).days
    if span_days <= 0:
        return 1.0
    trades_per_day = len(trades) / span_days
    return math.sqrt(trades_per_day * 252)  # sqrt(N) scaling, N = estimated trades per year


def calculate_sharpe_ratio(trades: list[dict]) -> float | None:
    """Per-trade Sharpe, annualized by observed trade frequency. See module docstring for methodology caveat."""
    if len(trades) < 2:
        return None
    returns = [t["pnl_pct"] / 100 for t in trades]
    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance)
    if std_dev == 0:
        return None
    return round((mean_return / std_dev) * _annualization_factor(trades), 3)


def calculate_sortino_ratio(trades: list[dict]) -> float | None:
    """Same as Sharpe, but only penalizes downside deviation (returns below 0)."""
    if len(trades) < 2:
        return None
    returns = [t["pnl_pct"] / 100 for t in trades]
    mean_return = sum(returns) / len(returns)
    downside_returns = [r for r in returns if r < 0]
    if not downside_returns:
        return None
    downside_variance = sum(r ** 2 for r in downside_returns) / len(returns)
    downside_std = math.sqrt(downside_variance)
    if downside_std == 0:
        return None
    return round((mean_return / downside_std) * _annualization_factor(trades), 3)


def compute_all_metrics(trades: list[dict]) -> dict:
    """Convenience function: computes every metric at once."""
    wins = [t for t in trades if t["pnl_dollars"] > 0]
    losses = [t for t in trades if t["pnl_dollars"] < 0]

    return {
        "total_trades": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1) if trades else None,
        "avg_win_dollars": round(sum(t["pnl_dollars"] for t in wins) / len(wins), 2) if wins else None,
        "avg_loss_dollars": round(sum(t["pnl_dollars"] for t in losses) / len(losses), 2) if losses else None,
        "profit_factor": calculate_profit_factor(trades),
        "sharpe_ratio": calculate_sharpe_ratio(trades),
        "sortino_ratio": calculate_sortino_ratio(trades),
        **calculate_max_drawdown(trades),
    }


if __name__ == "__main__":
    import sqlite3
    with sqlite3.connect("options_trades.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM options_trades WHERE exit_date IS NOT NULL AND trade_id NOT LIKE 'spy-gamma-%'").fetchall()
        trades = [dict(r) for r in rows]

    print("Testing on your real, current main-bot trade history (" + str(len(trades)) + " trades):\n")
    metrics = compute_all_metrics(trades)
    for key, value in metrics.items():
        print("  " + key + ": " + str(value))
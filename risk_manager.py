"""Account-level risk controls for backtesting and live trading.

All functions are pure (no side effects) so they can be tested independently
and called from any context — backtest loop, live order handler, or CLI.

Conventions
-----------
- Monetary fractions (risk_pct, max_daily_loss_pct, max_drawdown_pct) are
  expressed as **decimals**: 0.01 = 1%, 0.03 = 3%, 0.08 = 8%.
- P&L fractions passed *in* are also decimals and are **signed**:
  negative values represent losses / drawdown.
- Functions returning bool use the convention: True = action is allowed,
  False = action is blocked.
"""


def calculate_position_size(
    account_equity: float,
    entry_price: float,
    stop_loss_price: float,
    risk_pct: float = 0.01,
) -> int:
    """Return the whole-share position size that risks exactly risk_pct of equity.

    The position is sized so that a fill at ``stop_loss_price`` produces a
    loss no greater than ``account_equity * risk_pct``.

    Parameters
    ----------
    account_equity:
        Current total account value in dollars.
    entry_price:
        Anticipated fill price per share.
    stop_loss_price:
        Stop-loss price per share.  Must be below ``entry_price`` for a long.
    risk_pct:
        Fraction of equity to risk per trade (default 0.01 = 1 %).

    Returns
    -------
    int
        Number of whole shares to buy.  Returns 0 when the risk-per-share is
        zero or negative (stop above entry), or when the equity budget is too
        small to afford even one share.
    """
    risk_per_share = entry_price - stop_loss_price
    if risk_per_share <= 0:
        return 0
    max_risk_dollars = account_equity * risk_pct
    shares = max_risk_dollars / risk_per_share
    return int(shares)  # floor: never risk more than the budget


def check_max_positions(
    open_positions_count: int,
    max_positions: int = 3,
) -> bool:
    """Return True when a new position may be opened (count is below cap).

    Parameters
    ----------
    open_positions_count:
        Number of positions currently open across the account.
    max_positions:
        Hard cap on concurrent open positions (default 3).
    """
    return open_positions_count < max_positions


def check_daily_loss_limit(
    daily_pnl_pct: float,
    max_daily_loss_pct: float = 0.03,
) -> bool:
    """Return True when today's loss is still within the acceptable limit.

    Parameters
    ----------
    daily_pnl_pct:
        Today's realised P&L as a fraction of starting equity (signed,
        e.g. -0.025 means down 2.5 % today).
    max_daily_loss_pct:
        Maximum tolerated intraday loss as a positive fraction (default
        0.03 = 3 %).  New trades are blocked once this is breached.
    """
    return daily_pnl_pct > -max_daily_loss_pct


def check_drawdown_pause(
    rolling_pnl_pct: float,
    max_drawdown_pct: float = 0.08,
) -> bool:
    """Return True when the rolling drawdown is within acceptable bounds.

    Parameters
    ----------
    rolling_pnl_pct:
        Current equity as a fraction *below the equity peak* (signed,
        e.g. -0.09 means the account is 9 % below its high-water mark).
    max_drawdown_pct:
        Maximum tolerated drawdown from peak as a positive fraction
        (default 0.08 = 8 %).  The whole system is paused when breached.
    """
    return rolling_pnl_pct > -max_drawdown_pct

"""Paper-trading execution for the breakout/volume/sentiment strategy.

Safety guarantees
-----------------
paper=True is hardcoded in TradingClient and is never configurable.
Place a file named STOP_TRADING in the project directory to immediately
pause all trading logic without changing any code.

Signal log
----------
Every call to check_signal_and_trade() writes one row to signal_log.db
recording what was checked, what fired, and why any checks failed.
"""

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import (
    MarketOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)

from backtest_engine import (
    calculate_atr,
    calculate_relative_volume,
    check_breakout,
    check_ma_trend,
    check_news_sentiment,
    get_historical_bars,
    get_news_for_ticker,
)
from risk_manager import (
    calculate_position_size,
    check_daily_loss_limit,
    check_drawdown_pause,
    check_max_positions,
)

# ── Configuration ─────────────────────────────────────────────────────────────
KILL_SWITCH_PATH = Path("STOP_TRADING")
SIGNAL_LOG_DB    = "signal_log.db"
PEAK_EQUITY_FILE = Path(".peak_equity")

# Strategy parameters — mirror the backtested setup exactly.
LIVE_CONFIG: dict[str, Any] = {
    "atr_stop_multiplier":     1.5,
    "atr_target_multiplier":   2.5,
    "rv_threshold":            1.5,
    "rv_confirmation_bars":    1,
    "breakout_lookback":       20,
    "ma_trend_period":         50,
    "news_lookback_hours":     24,
    "position_risk_pct":       0.01,
    "max_position_value_pct":  0.20,
}

# ── Trading client — paper=True is intentionally hardcoded ────────────────────
_api_key    = os.environ.get("ALPACA_API_KEY", "")
_secret_key = os.environ.get("ALPACA_SECRET_KEY", "")

# This line must never be changed to paper=False.
_trading_client = TradingClient(_api_key, _secret_key, paper=True)


# ── Signal log ────────────────────────────────────────────────────────────────
def _init_signal_log() -> None:
    """Create the signal_log table if it doesn't exist."""
    with sqlite3.connect(SIGNAL_LOG_DB) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS signal_log (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                checked_at     TEXT    NOT NULL,
                ticker         TEXT    NOT NULL,
                signal_fired   INTEGER NOT NULL DEFAULT 0,
                blocks         TEXT    NOT NULL DEFAULT '',
                entry_price    REAL,
                atr            REAL,
                relative_vol   REAL,
                position_size  INTEGER,
                order_id       TEXT,
                note           TEXT
            )
        """)


def _log_signal(
    ticker: str,
    signal_fired: bool,
    blocks: list[str],
    *,
    entry_price: float | None = None,
    atr: float | None = None,
    relative_vol: float | None = None,
    position_size: int | None = None,
    order_id: str | None = None,
    note: str | None = None,
) -> None:
    """Append one row to the signal log."""
    _init_signal_log()
    with sqlite3.connect(SIGNAL_LOG_DB) as con:
        con.execute(
            """
            INSERT INTO signal_log
                (checked_at, ticker, signal_fired, blocks,
                 entry_price, atr, relative_vol, position_size, order_id, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                ticker,
                int(signal_fired),
                "; ".join(blocks) if blocks else "",
                entry_price,
                atr,
                relative_vol,
                position_size,
                order_id,
                note,
            ),
        )


# ── Account state helpers ─────────────────────────────────────────────────────
def _load_peak_equity(current_equity: float) -> float:
    """Return the stored high-water mark, updating it if current is higher."""
    if PEAK_EQUITY_FILE.exists():
        try:
            stored = float(PEAK_EQUITY_FILE.read_text().strip())
            peak = max(stored, current_equity)
        except ValueError:
            peak = current_equity
    else:
        peak = current_equity
    PEAK_EQUITY_FILE.write_text(str(peak))
    return peak


def _account_risk_state() -> dict[str, Any]:
    """Fetch live account metrics needed for the risk-manager checks.

    Returns
    -------
    dict with keys:
        equity            – current portfolio value (float)
        daily_pnl_frac    – today's P&L as a fraction of last-close equity
        rolling_pnl_frac  – current equity vs high-water mark (negative = drawdown)
        open_count        – number of currently open positions
    """
    acct = _trading_client.get_account()
    equity      = float(acct.equity)
    last_equity = float(acct.last_equity) if acct.last_equity else equity
    daily_pnl_frac = (equity - last_equity) / last_equity if last_equity else 0.0

    peak = _load_peak_equity(equity)
    rolling_pnl_frac = (equity - peak) / peak if peak else 0.0

    positions = _trading_client.get_all_positions()
    open_tickers = {p.symbol for p in positions}

    return {
        "equity":           equity,
        "daily_pnl_frac":   daily_pnl_frac,
        "rolling_pnl_frac": rolling_pnl_frac,
        "open_count":       len(positions),
        "open_tickers":     open_tickers,
    }


# ── Core function ─────────────────────────────────────────────────────────────
def check_signal_and_trade(ticker: str) -> dict[str, Any]:
    """Check entry signals for ``ticker`` and submit a bracket order if all pass.

    Every invocation — regardless of outcome — writes a row to signal_log.db.

    Parameters
    ----------
    ticker:
        Symbol to evaluate (e.g. "AAPL").

    Returns
    -------
    dict with keys:
        ticker         – the symbol checked
        signal_fired   – True when an order was submitted
        blocks         – list of strings explaining why trading was blocked
        order_id       – Alpaca order UUID (str) if an order was placed
        position_size  – whole shares ordered (int) if an order was placed
        entry_price    – close price at signal bar (float)
        note           – human-readable outcome summary
    """
    blocks: list[str] = []
    result: dict[str, Any] = {
        "ticker":        ticker,
        "signal_fired":  False,
        "blocks":        blocks,
        "order_id":      None,
        "position_size": None,
        "entry_price":   None,
        "note":          None,
    }

    # ── Kill switch ───────────────────────────────────────────────────────────
    if KILL_SWITCH_PATH.exists():
        note = "PAUSED — STOP_TRADING file exists; remove it to resume"
        result["note"] = note
        _log_signal(ticker, False, [], note=note)
        return result

    # ── Fetch 5-min bars (5 calendar days → ~3-4 trading days, ~250 bars) ────
    now   = datetime.now(timezone.utc)
    start = now - timedelta(days=5)
    try:
        bars = get_historical_bars(ticker, start, now)
    except Exception as exc:  # noqa: BLE001
        note = f"bar fetch failed: {exc}"
        _log_signal(ticker, False, ["bar fetch error"], note=note)
        result["blocks"] = ["bar fetch error"]
        result["note"]   = note
        return result

    # Need at least MA-period + a few extras to evaluate the last bar
    min_bars = LIVE_CONFIG["ma_trend_period"] + 10
    if len(bars) < min_bars:
        note = f"only {len(bars)} bars available (need {min_bars})"
        blocks.append("insufficient bars")
        _log_signal(ticker, False, blocks, note=note)
        result["blocks"] = blocks
        result["note"]   = note
        return result

    index       = len(bars) - 1
    entry_price = float(bars[index].close)

    # ── Fetch recent news (48 h window is sufficient for sentiment check) ─────
    news_start = now - timedelta(hours=48)
    try:
        news_items = get_news_for_ticker(ticker, news_start, now)
    except Exception:  # noqa: BLE001
        news_items = []  # degrade gracefully: no news → neutral sentiment

    # ── Compute signal indicators ─────────────────────────────────────────────
    cfg = LIVE_CONFIG
    rv  = calculate_relative_volume(
        bars, index, confirmation_bars=cfg["rv_confirmation_bars"]
    )
    atr = calculate_atr(bars, index)

    # ── Entry filter checks (collect ALL failures for the log) ────────────────
    if rv < cfg["rv_threshold"]:
        blocks.append(
            f"low relative volume ({rv:.2f} < {cfg['rv_threshold']:.2f})"
        )
    if not check_breakout(bars, index, lookback=cfg["breakout_lookback"]):
        blocks.append("no breakout")
    if not check_ma_trend(bars, index, period=cfg["ma_trend_period"]):
        blocks.append(f"below MA{cfg['ma_trend_period']}")
    if not check_news_sentiment(
        news_items, bars[index].timestamp,
        lookback_hours=cfg["news_lookback_hours"],
    ):
        blocks.append("negative news sentiment")
    if atr <= 0:
        blocks.append("ATR is zero — cannot size position")

    if blocks:
        _log_signal(
            ticker, False, blocks,
            entry_price=entry_price, atr=atr, relative_vol=rv,
        )
        result["blocks"] = blocks
        return result

    # ── Risk-manager gate ─────────────────────────────────────────────────────
    try:
        acct_state = _account_risk_state()
    except Exception as exc:  # noqa: BLE001
        note = f"account fetch failed: {exc}"
        blocks.append("account fetch error")
        _log_signal(ticker, False, blocks, entry_price=entry_price, atr=atr, relative_vol=rv, note=note)
        result["blocks"] = blocks
        result["note"]   = note
        return result

    equity           = acct_state["equity"]
    daily_pnl_frac   = acct_state["daily_pnl_frac"]
    rolling_pnl_frac = acct_state["rolling_pnl_frac"]
    open_count       = acct_state["open_count"]
    open_tickers     = acct_state["open_tickers"]

    # Skip if we already hold this ticker
    if ticker in open_tickers:
        blocks.append(f"already holding {ticker}")

    if not check_max_positions(open_count):
        blocks.append(
            f"max positions reached ({open_count} open, limit {3})"
        )
    if not check_daily_loss_limit(daily_pnl_frac):
        blocks.append(
            f"daily loss limit hit ({daily_pnl_frac*100:.2f}% today)"
        )
    if not check_drawdown_pause(rolling_pnl_frac):
        blocks.append(
            f"drawdown pause triggered ({rolling_pnl_frac*100:.2f}% from peak)"
        )

    if blocks:
        _log_signal(
            ticker, False, blocks,
            entry_price=entry_price, atr=atr, relative_vol=rv,
        )
        result["blocks"] = blocks
        return result

    # ── Position sizing ───────────────────────────────────────────────────────
    stop_price   = round(entry_price - cfg["atr_stop_multiplier"]   * atr, 2)
    target_price = round(entry_price + cfg["atr_target_multiplier"] * atr, 2)
    shares = calculate_position_size(
        equity, entry_price, stop_price,
        risk_pct=cfg["position_risk_pct"],
        max_position_value_pct=cfg["max_position_value_pct"],
    )

    if shares < 1:
        blocks.append(
            f"position size < 1 share "
            f"(equity={equity:.0f}, entry={entry_price:.2f}, stop={stop_price:.2f})"
        )
        _log_signal(
            ticker, False, blocks,
            entry_price=entry_price, atr=atr, relative_vol=rv,
        )
        result["blocks"] = blocks
        return result

    # ── Submit bracket order ──────────────────────────────────────────────────
    order_request = MarketOrderRequest(
        symbol=ticker,
        qty=shares,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.BRACKET,
        take_profit=TakeProfitRequest(limit_price=target_price),
        stop_loss=StopLossRequest(stop_price=stop_price),
    )
    try:
        order = _trading_client.submit_order(order_request)
        order_id = str(order.id)
    except Exception as exc:  # noqa: BLE001
        note = f"order submission failed: {exc}"
        blocks.append("order rejected by broker")
        _log_signal(
            ticker, False, blocks,
            entry_price=entry_price, atr=atr, relative_vol=rv,
            position_size=shares, note=note,
        )
        result["blocks"] = blocks
        result["note"]   = note
        return result

    note = (
        f"bracket order submitted — "
        f"{shares} shares @ ~${entry_price:.2f}  "
        f"stop=${stop_price:.2f}  target=${target_price:.2f}"
    )
    _log_signal(
        ticker, True, [],
        entry_price=entry_price, atr=atr, relative_vol=rv,
        position_size=shares, order_id=order_id, note=note,
    )
    result.update(
        signal_fired=True,
        order_id=order_id,
        position_size=shares,
        entry_price=entry_price,
        note=note,
    )
    return result


# ── Recent signal log reader (used by main.py summary) ───────────────────────
def recent_signal_log(limit: int = 20) -> list[dict[str, Any]]:
    """Return the most recent ``limit`` rows from the signal log as dicts."""
    _init_signal_log()
    with sqlite3.connect(SIGNAL_LOG_DB) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT * FROM signal_log
            ORDER BY checked_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]

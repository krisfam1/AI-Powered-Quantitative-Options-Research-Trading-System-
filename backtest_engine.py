"""Intraday breakout and relative-volume backtesting utilities."""

import os
import sqlite3
from datetime import date, datetime, time, timezone
from typing import Any

from alpaca.data import StockBarsRequest, StockHistoricalDataClient
from alpaca.data.enums import DataFeed
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

import trade_log


def _as_utc_datetime(value: date | datetime | str) -> datetime:
    """Convert supported date inputs to timezone-aware UTC datetimes."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def get_historical_bars(
    ticker: str,
    start_date: date | datetime | str,
    end_date: date | datetime | str,
) -> list[Any]:
    """Fetch 5-minute IEX bars for a ticker and date range."""
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise RuntimeError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")

    request = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame(5, TimeFrameUnit.Minute),
        start=_as_utc_datetime(start_date),
        end=_as_utc_datetime(end_date),
        feed=DataFeed.IEX,
    )
    client = StockHistoricalDataClient(api_key, secret_key)
    bars = client.get_stock_bars(request)
    return list(bars[ticker])


def calculate_relative_volume(
    bars: list[Any], current_index: int, lookback: int = 20
) -> float:
    """Return current volume divided by the average prior-bar volume."""
    if current_index < lookback:
        return 0.0

    prior_bars = bars[current_index - lookback : current_index]
    average_volume = sum(float(bar.volume) for bar in prior_bars) / lookback
    if average_volume == 0:
        return 0.0
    return float(bars[current_index].volume) / average_volume


def check_breakout(
    bars: list[Any], current_index: int, lookback: int = 20
) -> bool:
    """Return whether the current close exceeds the prior lookback high."""
    if current_index < lookback:
        return False

    prior_high = max(
        float(bar.high)
        for bar in bars[current_index - lookback : current_index]
    )
    return float(bars[current_index].close) > prior_high


def calculate_atr(
    bars: list[Any], current_index: int, period: int = 14
) -> float:
    """Calculate the simple Average True Range over prior bars."""
    if period <= 0 or current_index < period:
        return 0.0

    true_ranges: list[float] = []
    start_index = current_index - period
    for index in range(start_index, current_index):
        bar = bars[index]
        high = float(bar.high)
        low = float(bar.low)
        if index == 0:
            previous_close = float(bar.close)
        else:
            previous_close = float(bars[index - 1].close)
        true_ranges.append(
            max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            )
        )

    return sum(true_ranges) / len(true_ranges)


def _is_last_bar_of_day(bars: list[Any], index: int) -> bool:
    """Return whether a bar is the final bar for its trading date."""
    if index == len(bars) - 1:
        return True
    return bars[index + 1].timestamp.date() != bars[index].timestamp.date()


def _trade_id(ticker: str, timestamp: datetime) -> str:
    """Create a stable ID so repeated backtests do not duplicate entries."""
    timestamp_key = timestamp.astimezone(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    return f"backtest-{ticker.upper()}-{timestamp_key}"


def run_backtest(
    ticker: str,
    start_date: date | datetime | str,
    end_date: date | datetime | str,
    relative_volume_threshold: float = 1.5,
    atr_stop_multiplier: float = 1.5,
    atr_target_multiplier: float = 2.5,
    atr_trail_trigger: float = 1.0,
) -> None:
    """Run a long-only ATR-adjusted breakout/volume backtest."""
    trade_log.init_db()
    bars = get_historical_bars(ticker, start_date, end_date)
    if not bars:
        print(f"\nNo historical bars returned for {ticker}.")
        return

    open_position: dict[str, Any] | None = None
    completed_trades = 0

    for index, bar in enumerate(bars):
        timestamp = bar.timestamp
        close_price = float(bar.close)

        if open_position is not None:
            stop_price = float(open_position["stop_loss_price"])
            target_price = float(open_position["target_price"])
            exit_price: float | None = None
            exit_reason: str | None = None
            current_atr = calculate_atr(bars, index)

            if current_atr > 0:
                entry_price = float(open_position["entry_price"])
                trail_trigger_price = entry_price + (
                    atr_trail_trigger * current_atr
                )
                if float(bar.high) >= trail_trigger_price:
                    proposed_stop = float(bar.close) - (
                        atr_stop_multiplier * current_atr
                    )
                    if proposed_stop > stop_price:
                        open_position["stop_loss_price"] = proposed_stop
                        open_position["stop_is_trailing"] = True
                        stop_price = proposed_stop

            if float(bar.low) <= stop_price:
                exit_price = stop_price
                exit_reason = (
                    "trailing_stop"
                    if open_position["stop_is_trailing"]
                    else "stop_loss"
                )
            elif float(bar.high) >= target_price:
                exit_price = target_price
                exit_reason = "take_profit"
            elif _is_last_bar_of_day(bars, index):
                exit_price = close_price
                exit_reason = "eod_close"

            if exit_price is not None and exit_reason is not None:
                entry_price = float(open_position["entry_price"])
                position_size = float(open_position["position_size"])
                pnl_dollars = (exit_price - entry_price) * position_size
                pnl_percent = ((exit_price - entry_price) / entry_price) * 100
                if pnl_percent > 0:
                    outcome_class = "win"
                elif pnl_percent < 0:
                    outcome_class = "loss"
                else:
                    outcome_class = "breakeven"

                trade_log.log_trade_exit(
                    open_position["trade_id"],
                    {
                        "timestamp_exit": timestamp.isoformat(),
                        "exit_price": exit_price,
                        "exit_reason": exit_reason,
                        "pnl_dollars": pnl_dollars,
                        "pnl_percent": pnl_percent,
                        "outcome_class": outcome_class,
                        "root_cause": exit_reason,
                        "was_process_correct": 1,
                        "rule_change_made": 0,
                        "rule_change_description": "",
                    },
                )
                completed_trades += 1
                open_position = None
                continue

        if open_position is None and not _is_last_bar_of_day(bars, index):
            relative_volume = calculate_relative_volume(bars, index)
            if (
                relative_volume >= relative_volume_threshold
                and check_breakout(bars, index)
            ):
                entry_price = close_price
                position_size = 1.0
                atr = calculate_atr(bars, index)
                if atr <= 0:
                    continue
                stop_loss_price = entry_price - (
                    atr_stop_multiplier * atr
                )
                target_price = entry_price + (
                    atr_target_multiplier * atr
                )
                trade_id = _trade_id(ticker, timestamp)

                trade_log.log_trade_entry(
                    {
                        "trade_id": trade_id,
                        "timestamp_entry": timestamp.isoformat(),
                        "ticker": ticker,
                        "signal_type": "breakout_volume_confluence",
                        "volume_at_entry": float(bar.volume),
                        "relative_volume": relative_volume,
                        "price_action_pattern": "breakout",
                        "news_present": 0,
                        "entry_price": entry_price,
                        "position_size": position_size,
                        "stop_loss_price": stop_loss_price,
                        "target_price": target_price,
                        "risk_amount": entry_price - stop_loss_price,
                    }
                )
                open_position = {
                    "trade_id": trade_id,
                    "entry_price": entry_price,
                    "position_size": position_size,
                    "stop_loss_price": stop_loss_price,
                    "target_price": target_price,
                    "stop_is_trailing": False,
                }

    print(f"\nBacktest complete for {ticker}: {completed_trades} trades closed.")


def print_backtest_summary() -> None:
    """Print performance metrics for completed trades in the SQLite log."""
    with sqlite3.connect(trade_log.DATABASE_PATH) as connection:
        rows = connection.execute(
            """
            SELECT pnl_dollars, pnl_percent, outcome_class
            FROM trades
            WHERE pnl_percent IS NOT NULL
            """
        ).fetchall()

    total_trades = len(rows)
    wins = [float(row[1]) for row in rows if row[2] == "win"]
    losses = [float(row[1]) for row in rows if row[2] == "loss"]
    net_pnl_percent = sum(float(row[1]) for row in rows)
    win_rate = (len(wins) / total_trades * 100) if total_trades else 0.0
    average_win = sum(wins) / len(wins) if wins else 0.0
    average_loss = sum(losses) / len(losses) if losses else 0.0

    print("\nBacktest summary:")
    print(f"Total trades: {total_trades}")
    print(f"Win rate: {win_rate:.2f}%")
    print(f"Average win %: {average_win:.2f}%")
    print(f"Average loss %: {average_loss:.2f}%")
    print(f"Net P&L %: {net_pnl_percent:.2f}%")
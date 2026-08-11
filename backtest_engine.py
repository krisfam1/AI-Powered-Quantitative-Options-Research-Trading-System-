"""Intraday breakout and relative-volume backtesting utilities."""

import os
import sqlite3
from datetime import date, datetime, time, timezone
from typing import Any, Mapping

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
    for index in range(current_index - period, current_index):
        bar = bars[index]
        high = float(bar.high)
        low = float(bar.low)
        previous_close = (
            float(bar.close)
            if index == 0
            else float(bars[index - 1].close)
        )
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


def _trade_id(prefix: str, timestamp: datetime) -> str:
    """Create a stable ID for a ticker and strategy variant."""
    timestamp_key = timestamp.astimezone(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    return f"{prefix}-{timestamp_key}"


def _completed_rows(prefixes: list[str] | None = None) -> list[tuple[Any, ...]]:
    """Read completed trades, optionally filtered by ID prefixes."""
    with sqlite3.connect(trade_log.DATABASE_PATH) as connection:
        if not prefixes:
            return connection.execute(
                """
                SELECT pnl_dollars, pnl_percent, outcome_class
                FROM trades
                WHERE pnl_percent IS NOT NULL
                """
            ).fetchall()

        clauses = " OR ".join("trade_id LIKE ?" for _ in prefixes)
        values = tuple(f"{prefix}-%" for prefix in prefixes)
        return connection.execute(
            f"""
            SELECT pnl_dollars, pnl_percent, outcome_class
            FROM trades
            WHERE pnl_percent IS NOT NULL AND ({clauses})
            """,
            values,
        ).fetchall()


def _stats(rows: list[tuple[Any, ...]]) -> dict[str, float]:
    """Calculate aggregate performance statistics from completed trades."""
    total_trades = len(rows)
    wins = [float(row[1]) for row in rows if row[2] == "win"]
    losses = [float(row[1]) for row in rows if row[2] == "loss"]
    return {
        "total_trades": float(total_trades),
        "win_rate": len(wins) / total_trades * 100 if total_trades else 0.0,
        "average_win_pct": sum(wins) / len(wins) if wins else 0.0,
        "average_loss_pct": sum(losses) / len(losses) if losses else 0.0,
        "net_pnl_pct": sum(float(row[1]) for row in rows),
    }


def run_backtest(
    ticker: str,
    start_date: date | datetime | str,
    end_date: date | datetime | str,
    exit_strategy: Mapping[str, Any],
    relative_volume_threshold: float = 1.5,
    trade_id_prefix: str | None = None,
) -> dict[str, float]:
    """Run a long-only breakout/volume backtest with a configured exit mode."""
    mode = exit_strategy.get("mode")
    if mode not in {"fixed_pct", "atr"}:
        raise ValueError("exit_strategy mode must be 'fixed_pct' or 'atr'")

    if mode == "fixed_pct":
        stop_loss_pct = float(exit_strategy["stop_loss_pct"])
        take_profit_pct = float(exit_strategy["take_profit_pct"])
    else:
        atr_stop_multiplier = float(exit_strategy["atr_stop_multiplier"])
        atr_target_multiplier = float(exit_strategy["atr_target_multiplier"])
        atr_trail_trigger = float(exit_strategy["atr_trail_trigger"])
        atr_trail_distance = float(exit_strategy["atr_trail_distance"])

    trade_log.init_db()
    bars = get_historical_bars(ticker, start_date, end_date)
    prefix = trade_id_prefix or f"backtest-{ticker.upper()}"
    if not bars:
        print(f"\nNo historical bars returned for {ticker}.")
        return _stats([])

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

            if mode == "atr":
                current_atr = calculate_atr(bars, index)
                if current_atr > 0:
                    entry_price = float(open_position["entry_price"])
                    trigger_price = entry_price + (
                        atr_trail_trigger * current_atr
                    )
                    if float(bar.high) >= trigger_price:
                        proposed_stop = float(bar.close) - (
                            atr_trail_distance * current_atr
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
            elif (
                (mode == "fixed_pct" or not open_position["stop_is_trailing"])
                and float(bar.high) >= target_price
            ):
                exit_price = target_price
                exit_reason = "take_profit"
            elif _is_last_bar_of_day(bars, index):
                exit_price = close_price
                exit_reason = "eod_close"

            if exit_price is not None and exit_reason is not None:
                entry_price = float(open_position["entry_price"])
                position_size = float(open_position["position_size"])
                pnl_dollars = (exit_price - entry_price) * position_size
                pnl_percent = (exit_price - entry_price) / entry_price * 100
                outcome_class = (
                    "win"
                    if pnl_percent > 0
                    else "loss"
                    if pnl_percent < 0
                    else "breakeven"
                )
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

                if mode == "fixed_pct":
                    stop_loss_price = entry_price * (1 - stop_loss_pct)
                    target_price = entry_price * (1 + take_profit_pct)
                else:
                    atr = calculate_atr(bars, index)
                    if atr <= 0:
                        continue
                    stop_loss_price = entry_price - (
                        atr_stop_multiplier * atr
                    )
                    target_price = entry_price + (
                        atr_target_multiplier * atr
                    )

                trade_id = _trade_id(prefix, timestamp)
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
    return _stats(_completed_rows([prefix]))


def run_multi_ticker_backtest(
    tickers: list[str],
    start_date: date | datetime | str,
    end_date: date | datetime | str,
    exit_strategy: Mapping[str, Any],
) -> dict[str, float]:
    """Run one strategy across tickers and return combined statistics."""
    strategy_name = str(exit_strategy.get("name", exit_strategy["mode"]))
    prefixes: list[str] = []
    for ticker in tickers:
        prefix = f"{strategy_name}-{ticker.upper()}"
        prefixes.append(prefix)
        run_backtest(
            ticker,
            start_date,
            end_date,
            exit_strategy,
            trade_id_prefix=prefix,
        )
    return _stats(_completed_rows(prefixes))
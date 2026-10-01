"""Intraday breakout and relative-volume backtesting utilities."""

import os
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from alpaca.data import StockBarsRequest, StockHistoricalDataClient
from alpaca.data.enums import DataFeed
from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import NewsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

import trade_log
from risk_manager import (
    calculate_position_size,
    check_daily_loss_limit,
    check_drawdown_pause,
    check_max_positions,
)

_ET = ZoneInfo("America/New_York")
_bar_cache: dict = {}

# ── Sentiment keyword sets ────────────────────────────────────────────────────
_POSITIVE_WORDS = frozenset({
    "beat", "beats", "upgrade", "upgraded", "breakout", "surge", "surges",
    "rally", "rallies", "strong", "strength", "growth", "profit", "profits",
    "record", "high", "buy", "bullish", "gain", "gains", "jump", "jumps",
    "rise", "rises", "rising", "outperform", "outperforms", "boost", "boosts",
    "soar", "soars", "expand", "expands", "win", "wins", "success", "exceed",
    "exceeds", "accelerate", "positive", "recover", "recovers", "rebound",
    "rebounding",
})
_NEGATIVE_WORDS = frozenset({
    "miss", "misses", "downgrade", "downgraded", "crash", "crashes", "fall",
    "falls", "falling", "loss", "losses", "weak", "weakness", "decline",
    "declines", "drop", "drops", "sell", "bearish", "plunge", "plunges",
    "cut", "cuts", "warning", "warns", "fail", "fails", "failure", "debt",
    "lawsuit", "layoff", "layoffs", "recall", "recalls", "disappoint",
    "disappoints", "negative", "restructure", "restructuring", "concern",
    "concerns", "short", "default", "investigation", "fine", "penalty",
})


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
    """Fetch 5-minute IEX bars for a ticker and date range.

    Results are cached in memory for the lifetime of the process, keyed by
    (ticker, start_utc, end_utc).  Subsequent calls with the same arguments
    return the cached list immediately without hitting the Alpaca API again.
    The cache is never written to disk, so it is automatically invalidated on
    process restart.
    """
    start_utc = _as_utc_datetime(start_date)
    end_utc = _as_utc_datetime(end_date)
    cache_key = (ticker.upper(), start_utc.isoformat(), end_utc.isoformat())

    if cache_key in _bar_cache:
        return _bar_cache[cache_key]

    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise RuntimeError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")

    request = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame(5, TimeFrameUnit.Minute),
        start=start_utc,
        end=end_utc,
        feed=DataFeed.IEX,
    )
    client = StockHistoricalDataClient(api_key, secret_key)
    bars = client.get_stock_bars(request)
    result = list(bars[ticker])
    _bar_cache[cache_key] = result
    return result


def calculate_relative_volume(
    bars: list[Any],
    current_index: int,
    lookback: int = 20,
    confirmation_bars: int = 1,
) -> float:
    """Return current volume divided by the average prior-bar volume.

    When confirmation_bars > 1 the average of the last N bars' relative volumes
    is returned, providing a multi-bar confirmation window.
    """
    if current_index < lookback:
        return 0.0

    prior_bars = bars[current_index - lookback : current_index]
    average_volume = sum(float(bar.volume) for bar in prior_bars) / lookback
    if average_volume == 0:
        return 0.0

    if confirmation_bars <= 1:
        return float(bars[current_index].volume) / average_volume

    # Multi-bar confirmation: average rv over last confirmation_bars bars
    start = max(current_index - confirmation_bars + 1, lookback)
    rv_values = [
        float(bars[i].volume) / average_volume
        for i in range(start, current_index + 1)
    ]
    return sum(rv_values) / len(rv_values) if rv_values else 0.0


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


def check_breakdown(
    bars: list[Any], current_index: int, lookback: int = 20
) -> bool:
    """Return whether the current close is below the prior lookback low."""
    if current_index < lookback:
        return False

    prior_low = min(
        float(bar.low)
        for bar in bars[current_index - lookback : current_index]
    )
    return float(bars[current_index].close) < prior_low
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


def is_valid_time_window(
    bar_timestamp: datetime,
    windows: list[tuple[str, str]],
) -> bool:
    """Return True if the bar's ET time falls within any configured window.

    Parameters
    ----------
    bar_timestamp:
        The bar's timestamp (timezone-aware).
    windows:
        List of (start, end) string pairs in "HH:MM" 24-hour ET format,
        e.g. [("09:30", "10:30"), ("14:00", "15:00")].
    """
    et_time = bar_timestamp.astimezone(_ET).time()
    for start_str, end_str in windows:
        h_s, m_s = (int(x) for x in start_str.split(":"))
        h_e, m_e = (int(x) for x in end_str.split(":"))
        window_start = time(h_s, m_s)
        window_end = time(h_e, m_e)
        if window_start <= et_time <= window_end:
            return True
    return False


def check_vwap_uptrend(
    bars: list[Any], current_index: int, lookback: int = 20
) -> bool:
    """Return True if the current close is above the rolling VWAP.

    Uses a simple volume-weighted average price over the prior ``lookback``
    bars as a trend proxy.
    """
    if current_index < lookback:
        return False

    prior = bars[current_index - lookback : current_index]
    total_volume = sum(float(b.volume) for b in prior)
    if total_volume == 0:
        return False

    vwap = sum(float(b.close) * float(b.volume) for b in prior) / total_volume
    return float(bars[current_index].close) > vwap


def calculate_atr_percentile(
    bars: list[Any], current_index: int, lookback: int = 40
) -> float:
    """Return the percentile rank (0–100) of the current ATR vs prior bars.

    Computes a single-bar ATR (true range) for the current bar and ranks it
    against the true ranges of the prior ``lookback`` bars.
    """
    if current_index < lookback + 1:
        return 0.0

    def _true_range(index: int) -> float:
        bar = bars[index]
        high = float(bar.high)
        low = float(bar.low)
        prev_close = float(bars[index - 1].close)
        return max(high - low, abs(high - prev_close), abs(low - prev_close))

    current_tr = _true_range(current_index)
    prior_trs = [_true_range(i) for i in range(current_index - lookback, current_index)]
    count_below = sum(1 for tr in prior_trs if tr < current_tr)
    return count_below / lookback * 100.0


def get_news_for_ticker(
    ticker: str,
    start_date: date | datetime | str,
    end_date: date | datetime | str,
    limit: int = 200,
) -> list[Any]:
    """Fetch up to ``limit`` news articles for a ticker over the date range.

    Returns an empty list (rather than raising) if the request fails, so the
    news sentiment filter degrades gracefully to "allow all".
    """
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        return []
    try:
        client = NewsClient(api_key, secret_key)
        request = NewsRequest(
            symbols=ticker.upper(),
            start=_as_utc_datetime(start_date),
            end=_as_utc_datetime(end_date),
            limit=limit,
        )
        response = client.get_news(request)
        # NewsSet.data is a dict with key "news" holding a list of News objects
        return list(response.data.get("news", []))
    except Exception as exc:  # noqa: BLE001
        print(f"  [news] Warning: could not fetch news for {ticker}: {exc}")
        return []


def _classify_sentiment(text: str) -> float:
    """Score a headline: +1 per positive word, -1 per negative word."""
    score = 0.0
    for raw in text.lower().split():
        word = raw.strip(".,!?;:()'\"")
        if word in _POSITIVE_WORDS:
            score += 1.0
        elif word in _NEGATIVE_WORDS:
            score -= 1.0
    return score


def check_news_sentiment(
    news_items: list[Any],
    bar_timestamp: datetime,
    lookback_hours: int = 24,
    min_avg_score: float = 0.0,
) -> bool:
    """Return True if recent news sentiment is neutral-or-better.

    Articles published within ``lookback_hours`` before the bar are scored
    via keyword matching.  When there are no recent articles the result is
    True (no news → neutral, allow entry).
    """
    bar_utc = bar_timestamp.astimezone(timezone.utc)
    cutoff = bar_utc - timedelta(hours=lookback_hours)
    recent: list[Any] = []
    for item in news_items:
        # Alpaca News objects expose created_at; fall back to updated_at
        ts = getattr(item, "created_at", None) or getattr(item, "updated_at", None)
        if ts is None:
            continue
        ts_utc = ts.astimezone(timezone.utc)
        if cutoff <= ts_utc <= bar_utc:
            recent.append(item)

    if not recent:
        return True  # No news in window → neutral, allow entry

    scores = [_classify_sentiment(getattr(item, "headline", "")) for item in recent]
    avg = sum(scores) / len(scores)
    return avg >= min_avg_score


def calculate_ma(bars: list[Any], current_index: int, period: int = 50) -> float:
    """Return the simple moving average of close prices over the prior ``period`` bars."""
    if current_index < period:
        return 0.0
    window = bars[current_index - period : current_index]
    return sum(float(b.close) for b in window) / period


def check_ma_trend(bars: list[Any], current_index: int, period: int = 50) -> bool:
    """Return True if the current close is above the ``period``-bar MA.

    Uses prior bars only (no look-ahead) so the result is valid for backtesting.
    """
    ma = calculate_ma(bars, current_index, period)
    if ma == 0.0:
        return False
    return float(bars[current_index].close) > ma


def get_daily_regime(ticker: str, as_of_timestamp, period: int = 50) -> str:
    """Return 'bullish' or 'bearish' based on daily-close vs daily-period MA.

    Uses a separate daily-bar pull (not the intraday bars used elsewhere) so the
    regime read reflects the bigger-picture trend, not short-term intraday noise.
    """
    end = as_of_timestamp
    start = end - timedelta(days=period * 2 + 30)
    cache_key = ("REGIME", ticker.upper(), end.date().isoformat())
    if cache_key in _bar_cache:
        daily_bars = _bar_cache[cache_key]
    else:
        api_key = os.environ.get("ALPACA_API_KEY")
        secret_key = os.environ.get("ALPACA_SECRET_KEY")
        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame(1, TimeFrameUnit.Day),
            start=start,
            end=end,
            feed=DataFeed.IEX,
        )
        client = StockHistoricalDataClient(api_key, secret_key)
        daily_bars = list(client.get_stock_bars(request)[ticker])
        _bar_cache[cache_key] = daily_bars

    if len(daily_bars) < period:
        return "neutral"

    recent = daily_bars[-period:]
    ma = sum(float(b.close) for b in recent) / period
    current_close = float(daily_bars[-1].close)
    return "bullish" if current_close > ma else "bearish"


def check_ma_downtrend(bars: list[Any], current_index: int, period: int = 50) -> bool:
    """Return True if the current close is below the ``period``-bar MA.

    Uses prior bars only (no look-ahead) so the result is valid for backtesting.
    """
    ma = calculate_ma(bars, current_index, period)
    if ma == 0.0:
        return False
    return float(bars[current_index].close) < ma
def _is_last_bar_of_day(bars: list[Any], index: int) -> bool:
    """Return whether a bar is the final bar for its trading date."""
    if index == len(bars) - 1:
        return True
    return bars[index + 1].timestamp.date() != bars[index].timestamp.date()


def _days_held(position: dict, current_timestamp) -> int:
    """Return the number of calendar days a position has been open."""
    entry_timestamp = position["entry_timestamp"]
    entry_date = entry_timestamp.astimezone(_ET).date()
    current_date = current_timestamp.astimezone(_ET).date()
    return (current_date - entry_date).days
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
        "net_pnl_dollars": sum(
            float(row[0]) for row in rows if row[0] is not None
        ),
    }


def run_backtest(
    ticker: str,
    start_date: date | datetime | str,
    end_date: date | datetime | str,
    config: Mapping[str, Any],
    trade_id_prefix: str | None = None,
    prefetched_bars: list[Any] | None = None,
    prefetched_news: list[Any] | None = None,
    account_equity: float = 100_000.0,
) -> dict[str, float]:
    """Run a long-only breakout/volume backtest with a unified config dict.

    The ``config`` dict replaces the old ``exit_strategy`` + separate
    ``relative_volume_threshold`` parameters.  All entry-filter toggles
    default to disabled so callers that pass only exit keys are unaffected.

    Exit keys
    ---------
    mode : "fixed_pct" | "atr"
    For fixed_pct: stop_loss_pct, take_profit_pct
    For atr: atr_stop_multiplier, atr_target_multiplier,
             atr_trail_trigger, atr_trail_distance

    Entry / filter keys (all optional with safe defaults)
    ------------------------------------------------------
    relative_volume_threshold  : float  (default 1.5)
    rv_confirmation_bars       : int    (default 1)
    breakout_lookback          : int    (default 20)
    use_time_window            : bool   (default False)
    time_windows               : list[tuple[str,str]]  ET "HH:MM" pairs
    use_vwap_trend             : bool   (default False)
    vwap_lookback              : int    (default 20)
    use_atr_percentile         : bool   (default False)
    atr_percentile_min         : float  (default 40.0)
    atr_percentile_lookback    : int    (default 40)
    use_ma_trend               : bool   (default False)
      Only enter when close > MA(ma_trend_period).
    ma_trend_period            : int    (default 50)
    use_news_sentiment         : bool   (default False)
      Only enter when avg headline sentiment over the lookback window >= 0.
      Requires ``prefetched_news`` or live news fetch at the call site.
    news_sentiment_lookback_hours : int (default 24)
    """
    mode = config.get("mode")
    if mode not in {"fixed_pct", "atr"}:
        raise ValueError("config 'mode' must be 'fixed_pct' or 'atr'")

    if mode == "fixed_pct":
        stop_loss_pct = float(config["stop_loss_pct"])
        take_profit_pct = float(config["take_profit_pct"])
    else:
        atr_stop_multiplier = float(config["atr_stop_multiplier"])
        atr_target_multiplier = float(config["atr_target_multiplier"])
        atr_trail_trigger = float(config["atr_trail_trigger"])
        atr_trail_distance = float(config["atr_trail_distance"])

    # Entry filter config
    rv_threshold = float(config.get("relative_volume_threshold", 1.5))
    rv_confirmation = int(config.get("rv_confirmation_bars", 1))
    breakout_lookback = int(config.get("breakout_lookback", 20))

    use_time_window = bool(config.get("use_time_window", False))
    time_windows: list[tuple[str, str]] = list(
        config.get("time_windows", [("09:30", "10:30"), ("14:00", "15:00")])
    )

    use_vwap_trend = bool(config.get("use_vwap_trend", False))
    vwap_lookback = int(config.get("vwap_lookback", 20))

    use_atr_percentile = bool(config.get("use_atr_percentile", False))
    atr_percentile_min = float(config.get("atr_percentile_min", 40.0))
    atr_percentile_lookback = int(config.get("atr_percentile_lookback", 40))

    use_ma_trend = bool(config.get("use_ma_trend", False))
    ma_trend_period = int(config.get("ma_trend_period", 50))

    use_news_sentiment = bool(config.get("use_news_sentiment", False))
    news_sentiment_lookback_hours = int(config.get("news_sentiment_lookback_hours", 24))

    position_risk_pct = float(config.get("position_risk_pct", 0.01))
    allow_overnight_hold = bool(config.get("allow_overnight_hold", False))
    max_hold_days = int(config.get("max_hold_days", 10))
    direction = str(config.get("direction", "long"))
    use_regime_filter = bool(config.get("use_regime_filter", False))
    regime_period = int(config.get("regime_period", 50))

    trade_log.init_db()
    bars = prefetched_bars if prefetched_bars is not None else get_historical_bars(ticker, start_date, end_date)
    prefix = trade_id_prefix or f"backtest-{ticker.upper()}"
    if not bars:
        print(f"\nNo historical bars returned for {ticker}.")
        return _stats([])

    # Resolve news items once for this ticker (fetch only when needed)
    news_items: list[Any] = []
    if use_news_sentiment:
        if prefetched_news is not None:
            news_items = prefetched_news
        else:
            news_items = get_news_for_ticker(ticker, start_date, end_date)

    open_position: dict[str, Any] | None = None
    completed_trades = 0

    # ── Risk-manager state ────────────────────────────────────────────────────
    current_equity: float = account_equity
    peak_equity: float = account_equity
    daily_start_equity: float = account_equity
    current_day: date | None = None
    open_pos_count: int = 0

    for index, bar in enumerate(bars):
        timestamp = bar.timestamp
        close_price = float(bar.close)

        # Reset daily P&L tracker at the start of each new trading day
        bar_day = timestamp.astimezone(_ET).date()
        if bar_day != current_day:
            current_day = bar_day
            daily_start_equity = current_equity

        if open_position is not None:
            stop_price = float(open_position["stop_loss_price"])
            target_price = float(open_position["target_price"])
            exit_price: float | None = None
            exit_reason: str | None = None

            if mode == "atr":
                current_atr = calculate_atr(bars, index)
                if current_atr > 0:
                    entry_price = float(open_position["entry_price"])
                    if direction == "long":
                        trigger_price = entry_price + (atr_trail_trigger * current_atr)
                        triggered = float(bar.high) >= trigger_price
                    else:
                        trigger_price = entry_price - (atr_trail_trigger * current_atr)
                        triggered = float(bar.low) <= trigger_price
                    if triggered:
                        if direction == "long":
                            proposed_stop = float(bar.close) - (atr_trail_distance * current_atr)
                            improved = proposed_stop > stop_price
                        else:
                            proposed_stop = float(bar.close) + (atr_trail_distance * current_atr)
                            improved = proposed_stop < stop_price
                        if improved:
                            open_position["stop_loss_price"] = proposed_stop
                            open_position["stop_is_trailing"] = True
                            stop_price = proposed_stop

            if direction == "long":
                stop_hit = float(bar.low) <= stop_price
                target_hit = float(bar.high) >= target_price
            else:
                stop_hit = float(bar.high) >= stop_price
                target_hit = float(bar.low) <= target_price

            if stop_hit:
                exit_price = stop_price
                exit_reason = (
                    "trailing_stop"
                    if open_position["stop_is_trailing"]
                    else "stop_loss"
                )
            elif (
                (mode == "fixed_pct" or not open_position["stop_is_trailing"])
                and target_hit
            ):
                exit_price = target_price
                exit_reason = "take_profit"
            elif allow_overnight_hold and open_position.get("stop_is_trailing") and _days_held(open_position, timestamp) >= max_hold_days:
                exit_price = close_price
                exit_reason = "max_hold_days"
            elif not (allow_overnight_hold and open_position.get("stop_is_trailing")) and _is_last_bar_of_day(bars, index):
                exit_price = close_price
                exit_reason = "eod_close"

            if exit_price is not None and exit_reason is not None:
                entry_price = float(open_position["entry_price"])
                position_size = float(open_position["position_size"])
                if direction == "long":
                    pnl_dollars = (exit_price - entry_price) * position_size
                    pnl_percent = (exit_price - entry_price) / entry_price * 100
                else:
                    pnl_dollars = (entry_price - exit_price) * position_size
                    pnl_percent = (entry_price - exit_price) / entry_price * 100
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
                current_equity += pnl_dollars
                peak_equity = max(peak_equity, current_equity)
                open_pos_count -= 1
                completed_trades += 1
                open_position = None
                continue

        if open_position is None and not _is_last_bar_of_day(bars, index):
            # ── Entry filter checks ────────────────────────────────────────
            if use_time_window and not is_valid_time_window(timestamp, time_windows):
                continue

            relative_volume = calculate_relative_volume(
                bars, index, confirmation_bars=rv_confirmation
            )
            if relative_volume < rv_threshold:
                continue

            if use_regime_filter:
                regime = get_daily_regime(ticker, timestamp, period=regime_period)
                if direction == "long" and regime == "bearish":
                    continue
                if direction == "short" and regime == "bullish":
                    continue

            if direction == "long" and not check_breakout(bars, index, lookback=breakout_lookback):
                continue
            if direction == "short" and not check_breakdown(bars, index, lookback=breakout_lookback):
                continue

            if use_vwap_trend and not check_vwap_uptrend(bars, index, lookback=vwap_lookback):
                continue

            if use_atr_percentile:
                pct = calculate_atr_percentile(bars, index, lookback=atr_percentile_lookback)
                if pct < atr_percentile_min:
                    continue

            if use_ma_trend and direction == "long" and not check_ma_trend(bars, index, period=ma_trend_period):
                continue
            if use_ma_trend and direction == "short" and not check_ma_downtrend(bars, index, period=ma_trend_period):
                continue

            if use_news_sentiment and not check_news_sentiment(
                news_items, timestamp,
                lookback_hours=news_sentiment_lookback_hours,
            ):
                continue

            # ── Risk-manager gate ──────────────────────────────────────────
            if not check_max_positions(open_pos_count):
                continue
            daily_pnl_frac = (current_equity - daily_start_equity) / account_equity
            if not check_daily_loss_limit(daily_pnl_frac):
                continue
            rolling_pnl_frac = (current_equity - peak_equity) / account_equity
            if not check_drawdown_pause(rolling_pnl_frac):
                continue

            # ── Open position ──────────────────────────────────────────────
            entry_price = close_price

            if mode == "fixed_pct":
                if direction == "long":
                    stop_loss_price = entry_price * (1 - stop_loss_pct)
                    target_price = entry_price * (1 + take_profit_pct)
                else:
                    stop_loss_price = entry_price * (1 + stop_loss_pct)
                    target_price = entry_price * (1 - take_profit_pct)
            else:
                atr = calculate_atr(bars, index)
                if atr <= 0:
                    continue
                if direction == "long":
                    stop_loss_price = entry_price - (atr_stop_multiplier * atr)
                    target_price = entry_price + (atr_target_multiplier * atr)
                else:
                    stop_loss_price = entry_price + (atr_stop_multiplier * atr)
                    target_price = entry_price - (atr_target_multiplier * atr)

            position_size = float(calculate_position_size(
                current_equity, entry_price, stop_loss_price,
                risk_pct=position_risk_pct,
            ))
            if position_size < 1:
                continue

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
                    "risk_amount": abs(entry_price - stop_loss_price),
                }
            )
            open_position = {
                "trade_id": trade_id,
                "entry_timestamp": timestamp,
                "entry_price": entry_price,
                "position_size": position_size,
                "stop_loss_price": stop_loss_price,
                "target_price": target_price,
                "stop_is_trailing": False,
            }
            open_pos_count += 1

    print(f"\nBacktest complete for {ticker}: {completed_trades} trades closed.")
    return _stats(_completed_rows([prefix]))


def run_multi_ticker_backtest(
    tickers: list[str],
    start_date: date | datetime | str,
    end_date: date | datetime | str,
    config: Mapping[str, Any],
    prefetched_bars: dict[str, list[Any]] | None = None,
    prefetched_news: dict[str, list[Any]] | None = None,
    account_equity: float = 100_000.0,
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """Run one strategy across tickers; return (overall_stats, per_ticker_stats).

    Parameters
    ----------
    prefetched_bars:
        Optional pre-fetched 5-min bar lists keyed by ticker symbol.
    prefetched_news:
        Optional pre-fetched news lists keyed by ticker symbol.  When
        ``use_news_sentiment`` is True and this is provided, no live
        news fetch is made during the backtest.

    Returns
    -------
    overall_stats : dict[str, float]
        Aggregate statistics across all tickers.
    per_ticker_stats : dict[str, dict[str, float]]
        Per-ticker statistics keyed by ticker symbol.
    """
    strategy_name = str(config.get("name", config.get("mode", "backtest")))
    prefixes: list[str] = []
    per_ticker_stats: dict[str, dict[str, float]] = {}

    for ticker in tickers:
        prefix = f"{strategy_name}-{ticker.upper()}"
        prefixes.append(prefix)
        stats = run_backtest(
            ticker,
            start_date,
            end_date,
            config,
            trade_id_prefix=prefix,
            prefetched_bars=(prefetched_bars or {}).get(ticker),
            prefetched_news=(prefetched_news or {}).get(ticker),
            account_equity=account_equity,
        )
        per_ticker_stats[ticker] = stats

    overall = _stats(_completed_rows(prefixes))
    return overall, per_ticker_stats

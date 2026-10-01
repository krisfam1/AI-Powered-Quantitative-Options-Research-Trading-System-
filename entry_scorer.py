from dotenv import load_dotenv
from datetime import timedelta
load_dotenv()

"""
Weighted entry scoring system.

Replaces the binary all-or-nothing entry gate with a continuous score
(0-100), rewarding the MAGNITUDE of each signal, not just whether it
crosses a threshold. A strong reading on one factor can compensate for a
merely-adequate reading on another.

Factors (max points):
  1. Relative volume magnitude       (0-25)
  2. Breakout/breakdown magnitude    (0-20)
  3. Trend strength (distance to MA) (0-20)
  4. Momentum / rate of change       (0-15)
  5. Volatility regime               (0-10)
  6. News sentiment                  (0-5)
  7. Market regime alignment (SPY)   (0-5)

HONEST NOTE: gamma/charm are deliberately NOT included here -- they
remain a separate, post-entry sizing modifier, since they cannot be
backtested (no historical open-interest data) and including them in the
core score would make the score itself partially unvalidatable.
"""

import math
import backtest_engine as be


def score_relative_volume(bars: list, index: int) -> float:
    """0-25 points, scaled by how far above the 1.5x baseline the reading is."""
    rv = be.calculate_relative_volume(bars, index)
    if rv < 1.5:
        return 0.0
    score = 5 + (rv - 1.5) / (4.0 - 1.5) * 20
    return min(max(score, 0.0), 25.0)


def score_breakout_magnitude(bars: list, index: int, direction: str, lookback: int = 20) -> float:
    """0-20 points, scaled by how far price has moved past the recent high/low."""
    if index < lookback:
        return 0.0
    window = bars[index - lookback:index]
    current_price = float(bars[index].close)

    if direction == "call":
        recent_high = max(float(b.high) for b in window)
        if current_price <= recent_high:
            return 0.0
        pct_beyond = (current_price - recent_high) / recent_high * 100
    else:
        recent_low = min(float(b.low) for b in window)
        if current_price >= recent_low:
            return 0.0
        pct_beyond = (recent_low - current_price) / recent_low * 100

    score = 5 + (pct_beyond - 0.1) / (1.0 - 0.1) * 15
    return min(max(score, 0.0), 20.0)


def score_trend_strength(bars: list, index: int, direction: str, ma_period: int = 50) -> float:
    """0-20 points, scaled by how far price is from the 50-period MA."""
    if index < ma_period:
        return 0.0
    window = bars[index - ma_period:index]
    ma = sum(float(b.close) for b in window) / ma_period
    current_price = float(bars[index].close)

    if direction == "call":
        if current_price <= ma:
            return 0.0
        pct_above = (current_price - ma) / ma * 100
    else:
        if current_price >= ma:
            return 0.0
        pct_above = (ma - current_price) / ma * 100

    score = 5 + (pct_above - 0.5) / (5.0 - 0.5) * 15
    return min(max(score, 0.0), 20.0)


def score_momentum(bars: list, index: int, direction: str, lookback: int = 12) -> float:
    """0-15 points -- genuine rate-of-change over the recent lookback window."""
    if index < lookback:
        return 0.0
    past_price = float(bars[index - lookback].close)
    current_price = float(bars[index].close)
    if past_price <= 0:
        return 0.0

    pct_change = (current_price - past_price) / past_price * 100

    if direction == "call" and pct_change <= 0:
        return 0.0
    if direction == "put" and pct_change >= 0:
        return 0.0

    magnitude = abs(pct_change)
    score = 5 + (magnitude - 0.2) / (2.0 - 0.2) * 10
    return min(max(score, 0.0), 15.0)


def score_volatility_regime(bars: list, index: int, lookback: int = 60) -> float:
    """0-10 points -- rewards elevated realized volatility vs recent history."""
    if index < lookback:
        return 5.0
    try:
        from options_backtest_engine import calculate_historical_volatility
        current_vol = calculate_historical_volatility(bars, index)
        recent_vols = [calculate_historical_volatility(bars, i) for i in range(index - lookback, index)]
        recent_vols = [v for v in recent_vols if v > 0]
        if not recent_vols:
            return 5.0
        below = len([v for v in recent_vols if v < current_vol])
        percentile = below / len(recent_vols) * 100
        score = (percentile / 90) * 10
        return min(max(score, 0.0), 10.0)
    except Exception:
        return 5.0


_news_cache = {}  # keyed by (ticker, date) -- avoids redundant API calls within the same day


def score_news_sentiment(ticker: str, bars: list, index: int) -> float:
    """0-5 points -- binary for now (non-negative news), cached per ticker per day."""
    try:
        timestamp = bars[index].timestamp
        cache_key = (ticker, timestamp.date())

        if cache_key not in _news_cache:
            news_items = be.get_news_for_ticker(ticker, timestamp - timedelta(hours=24), timestamp)
            _news_cache[cache_key] = news_items
        else:
            news_items = _news_cache[cache_key]

        if be.check_news_sentiment(news_items, timestamp, lookback_hours=24):
            return 5.0
        return 0.0
    except Exception:
        return 2.5


def score_market_regime_alignment(direction: str, spy_regime: str) -> float:
    """0-5 points -- full points if SPY's own regime agrees with this trade's direction."""
    if spy_regime == "bullish" and direction == "call":
        return 5.0
    if spy_regime == "bearish" and direction == "put":
        return 5.0
    if spy_regime == "neutral":
        return 2.5
    return 0.0


def calculate_entry_score(ticker: str, bars: list, index: int, direction: str, spy_regime: str = "neutral") -> dict:
    """Combine all factors into a total 0-100 score with a breakdown."""
    rv_score = score_relative_volume(bars, index)
    breakout_score = score_breakout_magnitude(bars, index, direction)

    if rv_score + breakout_score < 5:
        return {
            "total_score": round(rv_score + breakout_score, 1),
            "breakdown": {
                "relative_volume": rv_score, "breakout_magnitude": breakout_score,
                "trend_strength": 0.0, "momentum": 0.0, "volatility_regime": 0.0,
                "news_sentiment": 0.0, "market_regime_alignment": 0.0,
            },
        }

    scores = {
        "relative_volume": rv_score,
        "breakout_magnitude": breakout_score,
        "trend_strength": score_trend_strength(bars, index, direction),
        "momentum": score_momentum(bars, index, direction),
        "volatility_regime": score_volatility_regime(bars, index),
        "news_sentiment": score_news_sentiment(ticker, bars, index),
        "market_regime_alignment": score_market_regime_alignment(direction, spy_regime),
    }
    total = sum(scores.values())
    return {"total_score": round(total, 1), "breakdown": scores}
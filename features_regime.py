"""
Feature Factory -- market/regime features. Module: regime.
Registered in feature_registry (research_database.db), version 1.0.

These functions compute values ONLY -- no claim of predictive value.
No feature here fetches external data itself (spy_trend_state wraps
an existing, already-validated function; relative_strength_vs_spy
requires the caller to supply SPY bars, matching the "no feature
fetches its own data" rule). No feature alters V1 or any live strategy.
"""

from backtest_engine import get_daily_regime
from features_underlying import past_return_n


def spy_trend_state(as_of_timestamp):
    """
    Computes: wraps the existing, already-validated get_daily_regime()
    for SPY. This wrapper adds no new logic beyond the call itself --
    all no-lookahead guarantees are inherited directly from that
    already-proven implementation.
    Returns: "bullish", "bearish", or "neutral", or None if the
    underlying call fails.
    """
    try:
        return get_daily_regime("SPY", as_of_timestamp, period=50)
    except Exception:
        return None


def vix_regime(vix_level, low_threshold=15, high_threshold=25):
    """
    Computes: categorical volatility-regime bucket from a supplied VIX level.
    STATUS: NOT RUNNABLE in current deployment -- no VIX data source is
    currently connected anywhere in this project (see feature_registry,
    runnable=0). This function is implemented and registered for when
    VIX data becomes available, but should not be called in production
    experiments yet.
    Returns: "low", "normal", or "high", or None if vix_level is None.
    """
    if vix_level is None:
        return None
    if vix_level < low_threshold:
        return "low"
    elif vix_level > high_threshold:
        return "high"
    return "normal"


def relative_strength_vs_spy(ticker_bars, spy_bars, index, n=20):
    """
    Computes: ticker's own past_return_n minus SPY's past_return_n over
    the SAME REAL TIME PERIOD -- matched by TIMESTAMP, not by index
    number. This is critical: ticker_bars and spy_bars can have
    different bar counts, different gaps (e.g., different halts,
    different data availability), so index N in one series does NOT
    necessarily correspond to the same real moment as index N in the
    other. Matching by index number would silently compare returns
    from different, misaligned time periods.

    Returns: decimal (difference of two returns), or None if no
    matching SPY timestamp is found or either series has insufficient
    lookback.
    """
    if index < 0 or index >= len(ticker_bars):
        return None
    target_timestamp = ticker_bars[index].timestamp

    spy_index = None
    for i, b in enumerate(spy_bars):
        if b.timestamp == target_timestamp:
            spy_index = i
            break
    if spy_index is None:
        return None

    ticker_return = past_return_n(ticker_bars, index, n=n)
    spy_return = past_return_n(spy_bars, spy_index, n=n)
    if ticker_return is None or spy_return is None:
        return None
    return ticker_return - spy_return


def vwap_distance(bars, index):
    """
    Computes: (close[index] - session_VWAP[index]) / session_VWAP[index].
    Session VWAP resets at the start of each real calendar day and
    accumulates cumulative(price*volume)/cumulative(volume) from that
    day's first bar through index -- NOT a fixed rolling bar count.
    Returns: decimal, or None if index is the first bar of its day
    (no prior volume within the session to weight) or volume data is
    missing/zero throughout the session so far.
    """
    if index < 0 or index >= len(bars):
        return None
    current_date = bars[index].timestamp.date()

    # Find the start of the current session (first bar with the same date)
    session_start = index
    while session_start > 0 and bars[session_start - 1].timestamp.date() == current_date:
        session_start -= 1

    cum_pv = 0.0
    cum_vol = 0.0
    for i in range(session_start, index + 1):
        price = float(bars[i].close)
        vol = float(getattr(bars[i], "volume", 0) or 0)
        cum_pv += price * vol
        cum_vol += vol

    if cum_vol == 0:
        return None
    vwap = cum_pv / cum_vol
    if vwap == 0:
        return None
    current_close = float(bars[index].close)
    return (current_close - vwap) / vwap

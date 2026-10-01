"""
Feature Factory -- underlying-price features. Module: underlying.
Registered in feature_registry (research_database.db), version 1.0.

These functions compute values ONLY. No feature makes any claim about
predictive value. Predictive value, if any, is determined only by
formal testing through the (future) Experiment Framework. No feature
here alters V1 or any live strategy in any way.
"""


def past_return_n(bars, index, n=20):
    """
    Computes: simple return over the prior n bars, using only data at
    or before index.
    Requires: bars[index-n] through bars[index] to exist.
    Returns: decimal return (e.g. 0.05 = +5%), or None if insufficient history.
    Lookahead-safe: uses only bars[index-n : index+1].
    """
    if index < n:
        return None
    p_then = float(bars[index - n].close)
    p_now = float(bars[index].close)
    if p_then == 0:
        return None
    return (p_now - p_then) / p_then


def breakout_strength(bars, index, lookback=20):
    """
    Computes: magnitude by which the current close exceeds the highest
    high of the prior `lookback` bars (NOT including the current bar).
    Zero or negative = no breakout; positive = breakout, with magnitude.
    Distinct from the existing binary check_breakout() gate -- this is
    a continuous measure, not pass/fail.
    Requires: bars[index-lookback] through bars[index-1] to exist.
    Returns: decimal (can be negative), or None if insufficient history.
    Lookahead-safe: the max() window is [index-lookback, index), strictly
    excluding the current bar itself.
    """
    if index < lookback:
        return None
    window_highs = [float(bars[i].high) for i in range(index - lookback, index)]
    prior_high = max(window_highs)
    if prior_high == 0:
        return None
    current_close = float(bars[index].close)
    return (current_close - prior_high) / prior_high


def atr_normalized(bars, index, period=14):
    """
    Computes: standard `period`-length Average True Range, normalized
    by the current close (so it's comparable across differently-priced
    securities).
    Requires: bars[index-period] through bars[index] to exist (needs
    one extra prior bar for the first true-range calculation).
    Returns: decimal (ATR as a fraction of price), or None if insufficient history.
    Lookahead-safe: uses only bars[index-period : index+1].
    """
    if index < period:
        return None
    true_ranges = []
    for i in range(index - period + 1, index + 1):
        high = float(bars[i].high)
        low = float(bars[i].low)
        prev_close = float(bars[i - 1].close)
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
    atr = sum(true_ranges) / len(true_ranges)
    current_close = float(bars[index].close)
    if current_close == 0:
        return None
    return atr / current_close
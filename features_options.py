"""
Feature Factory -- options-structure features. Module: options.
Registered in feature_registry (research_database.db), version 1.0.

These functions compute values ONLY -- no claim of predictive value.
No feature here fetches external data itself; historical IV inputs
are supplied by the caller, with timestamp/provenance safety being a
DATA-LAYER responsibility (see data_layer_iv_helper.py), not enforced
by these functions. No feature alters V1 or any live strategy.
"""

from options_pricing import calculate_delta
from options_backtest_engine import calculate_historical_volatility


def dte_at_index(bars, index, expiration_date):
    """
    Computes: days to expiration as of bars[index]'s own date.
    Convention: calendar days (not trading days), matching dte_target
    usage throughout the rest of this project. The current bar's date
    counts as day 0. If expiration_date is already before bars[index]'s
    date, returns the true (negative) value rather than clamping --
    the caller decides how to handle an already-expired contract.
    Returns: integer, or None if index is out of range or expiration_date invalid.
    """
    if index < 0 or index >= len(bars):
        return None
    try:
        bar_date = bars[index].timestamp.date()
        return (expiration_date - bar_date).days
    except (AttributeError, TypeError):
        return None


def delta_at_index(bars, index, strike, dte, vol, vol_source):
    """
    Computes: option delta via the existing, validated calculate_delta().
    vol_source is REQUIRED, no default -- must be exactly "historical_iv"
    or "realized_vol". This function does not decide or verify which
    volatility assumption is correct; it only requires the caller to be
    explicit, and this label must be recorded alongside the result in
    any dataset row that consumes this feature.
    Returns: float (delta, -1 to 1), or None if inputs are invalid.
    """
    if vol_source not in ("historical_iv", "realized_vol"):
        raise ValueError("vol_source must be exactly 'historical_iv' or 'realized_vol', got: " + repr(vol_source))
    if index < 0 or index >= len(bars):
        return None
    if dte is None or dte < 0:
        return None
    if vol is None or vol <= 0:
        return None
    spot = float(bars[index].close)
    return calculate_delta(spot, strike, dte, vol, option_type="call")


def iv_vs_realized_vol(bars, index, historical_iv):
    """
    Computes: (historical_iv - realized_vol) / realized_vol.
    realized_vol is computed via calculate_historical_volatility(),
    already validated lookahead-safe (uses only bars[0:index+1]
    internally). historical_iv's timestamp safety is a DATA-LAYER
    contract -- this function trusts, but does not verify, that the
    caller supplied a value fetched via the validated T-1 real-trading-
    day snapshot rule. Uses a dedicated cache namespace ("feature_factory")
    to avoid any shared-state interaction with the live backtest engines.
    Returns: decimal ratio, or None if inputs are invalid.
    """
    if index < 0 or index >= len(bars):
        return None
    if historical_iv is None:
        return None
    try:
        realized_vol = calculate_historical_volatility(bars, index, cache_namespace="feature_factory")
    except Exception:
        return None
    if not realized_vol or realized_vol == 0:
        return None
    return (historical_iv - realized_vol) / realized_vol


def iv_percentile(historical_iv_series, current_iv, lookback=252):
    """
    Computes: percentile rank of current_iv within the trailing
    `lookback` entries of historical_iv_series, WITH current_iv
    included in the ranking (locked formula, corrected):

        rank = (count(x <= current_iv for x in window) + 1) / (len(window) + 1)

    If current_iv exceeds every historical observation, rank = 1.0 exactly.

    CONTRACT: historical_iv_series must already contain ONLY observations
    strictly before the feature's own timestamp -- this is a DATA-LAYER
    responsibility (see data_layer_iv_helper.py), not verified here.

    Returns: float in [0, 1], or None if fewer than 20 historical
    observations are available or current_iv is None.
    """
    if current_iv is None:
        return None
    if not historical_iv_series or len(historical_iv_series) < 20:
        return None
    window = historical_iv_series[-lookback:]
    count_le = sum(1 for x in window if x <= current_iv)
    return (count_le + 1) / (len(window) + 1)
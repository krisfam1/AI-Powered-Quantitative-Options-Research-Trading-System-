from dotenv import load_dotenv
load_dotenv()

"""
iv_percentile batch pass. Supplies a historical IV series to the
ALREADY-DEFINED features_options.iv_percentile() function -- does NOT
reimplement its formula. Builds ONE cached, per-ticker daily IV series
(one real fetch per real trading day in the window), reused across
every observation for that ticker -- avoiding redundant, per-row
re-fetching of the same historical data.
"""

from datetime import date
from data_layer_iv_helper import get_timestamp_safe_historical_iv
from features_options import iv_percentile as feature_factory_iv_percentile


def build_ticker_iv_series(ticker, trading_days, price_lookup):
    """
    trading_days: sorted list of real trading dates (date objects) in
        the experiment window.
    price_lookup: dict {date: closing_price} for this ticker, used to
        pick a consistent ATM-ish reference strike for each day's IV
        fetch (same convention as compute_feature_row's strike proxy).

    Returns: sorted list of {"date": date, "iv": float} dicts -- one
    real T-1 IV fetch per trading day, cached for reuse. A day with no
    available IV is simply OMITTED from the series (never fabricated).
    """
    series = []
    for d in trading_days:
        price = price_lookup.get(d)
        if price is None:
            continue
        strike = round(price / 5) * 5
        try:
            result = get_timestamp_safe_historical_iv(ticker, d, strike, target_dte=14)
        except Exception:
            result = None
        if result is not None:
            series.append({"date": d, "iv": result["iv"], "snapshot_date": result["snapshot_date"]})
    return series


def compute_iv_percentile_for_observation(obs_date, current_iv, ticker_iv_series, lookback=252):
    """
    obs_date: the observation's own signal date (date object).
    current_iv: the observation's own T-1 IV value (already computed
        by compute_feature_row's iv_vs_realized_vol step -- reused
        here, not re-fetched, avoiding a second, possibly-inconsistent
        IV lookup for the same observation).
    ticker_iv_series: the FULL cached series for this ticker (built
        once via build_ticker_iv_series).

    STRICT filtering: only series entries with date < obs_date are
    used -- no future observation can ever enter the calculation.
    Delegates the actual percentile FORMULA to the existing, tested
    features_options.iv_percentile() -- this function only prepares
    the correctly-filtered input series.
    """
    if current_iv is None:
        return None
    historical_values = [e["iv"] for e in ticker_iv_series if e["date"] < obs_date]
    return feature_factory_iv_percentile(historical_values, current_iv, lookback=lookback)
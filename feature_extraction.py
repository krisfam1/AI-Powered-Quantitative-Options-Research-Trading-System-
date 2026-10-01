from dotenv import load_dotenv
load_dotenv()

"""
Consolidated feature extraction for the future ML decision engine.

Designed to work IDENTICALLY for backtest training data and live
inference: the core function takes pre-fetched bars + an index, so the
exact same calculation logic runs whether the bars came from a historical
backtest loop or a fresh live API call moments ago. This is the real,
concrete requirement from the ML roadmap -- no drift between how
training data and live data are computed.

HONEST LABELING: several fields use REALIZED volatility as an estimate,
since real market-implied volatility isn't available (no paid IV feed).
These are clearly named to avoid confusion with true IV.
"""

import backtest_engine as be
from options_backtest_engine import calculate_historical_volatility
from options_pricing import calculate_delta, calculate_gamma, calculate_theta, calculate_charm, calculate_vega
from entry_scorer import score_breakout_magnitude, score_trend_strength, score_momentum
from gamma_regime import calculate_net_gamma_regime


def extract_features(ticker: str, bars: list, index: int, option_type: str, strike: float, dte: int) -> dict:
    """
    Core feature extraction. Works on pre-fetched bars -- callers (both
    backtest and live) are responsible for supplying bars, keeping the
    calculation logic itself perfectly identical either way.
    """
    current_price = float(bars[index].close)
    vol = calculate_historical_volatility(bars, index)  # realized-vol ESTIMATE, not true market IV

    features = {}

    # Greeks (all computed using the estimated volatility above, since
    # real market-implied volatility is not currently available)
    features["delta"] = calculate_delta(current_price, strike, dte, vol, option_type=option_type)
    features["gamma"] = calculate_gamma(current_price, strike, dte, vol)
    features["theta"] = calculate_theta(current_price, strike, dte, vol, option_type=option_type)
    features["charm"] = calculate_charm(current_price, strike, dte, vol, option_type=option_type)
    features["vega_per_1pct_iv"] = calculate_vega(current_price, strike, dte, vol) / 100

    # Volatility (explicitly labeled as realized, not true IV)
    features["realized_volatility"] = vol
    if index >= 60:
        recent_vols = [calculate_historical_volatility(bars, i) for i in range(index - 60, index)]
        recent_vols = [v for v in recent_vols if v > 0]
        if recent_vols:
            below = len([v for v in recent_vols if v < vol])
            features["realized_vol_percentile"] = round(below / len(recent_vols) * 100, 1)
        else:
            features["realized_vol_percentile"] = None
    else:
        features["realized_vol_percentile"] = None

    # Price/volume action (reusing already-validated entry_scorer functions)
    features["relative_volume"] = be.calculate_relative_volume(bars, index)
    features["breakout_magnitude_score"] = score_breakout_magnitude(bars, index, option_type)
    features["trend_strength_score"] = score_trend_strength(bars, index, option_type)
    features["momentum_score"] = score_momentum(bars, index, option_type)

    # Moneyness and time
    features["moneyness"] = round(current_price / strike, 4)
    features["dte"] = dte
    features["stock_price"] = current_price
    features["strike"] = strike

    # Gamma regime (real-time only -- requires live options chain data,
    # so this will be None in backtest contexts where that data isn't
    # available; live callers should populate this via the wrapper below)
    features["gamma_regime"] = None

    return features


def extract_features_live(ticker: str, option_type: str, strike: float, dte: int) -> dict:
    """
    Live wrapper: fetches fresh bars, then calls the SAME core extraction
    function used by backtests -- guaranteeing identical calculation
    logic. Additionally populates gamma_regime, which requires a live
    options chain fetch not available during backtesting.
    """
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    bars = be.get_historical_bars(ticker, now - timedelta(days=10), now)
    index = len(bars) - 1

    features = extract_features(ticker, bars, index, option_type, strike, dte)

    try:
        regime_result = calculate_net_gamma_regime(ticker, features["stock_price"])
        features["gamma_regime"] = regime_result["regime"]
    except Exception:
        features["gamma_regime"] = None

    return features


if __name__ == "__main__":
    print("Testing live feature extraction on AAPL...\n")
    result = extract_features_live("AAPL", "call", 320.0, 14)
    for key, value in result.items():
        print("  " + key + ": " + str(value))
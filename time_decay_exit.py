from dotenv import load_dotenv
load_dotenv()

"""
Time-based decay exit.

Genuinely different from the existing expiry_safety_net (which only
force-closes 2 calendar days before expiration regardless of anything
else). This detects when a position's real EDGE has decayed with time --
combining theta burn rate (how much value is being lost to time decay
each day) with the ML model's re-evaluated win probability using CURRENT
features, not just the entry-time estimate.

Logic: if theta is burning a meaningful percentage of the position's
value each day, AND the model's current win-probability estimate (using
updated DTE, price, and momentum) has fallen below a real threshold,
the trade's edge has genuinely decayed -- exit rather than waiting for
expiration or a stop-loss to eventually trigger.
"""

import joblib
from feature_extraction import extract_features

MODEL_PATH = "baseline_model.joblib"
THETA_BURN_THRESHOLD_PCT = 0.03  # losing 3%+ of value per day to time decay alone
WIN_PROBABILITY_THRESHOLD = 0.40  # model's current estimate must be at least this to keep holding

_model_data = None


def _load_model():
    global _model_data
    if _model_data is None:
        _model_data = joblib.load(MODEL_PATH)
    return _model_data


def check_time_decay_exit(ticker: str, bars: list, index: int, option_type: str, strike: float, dte: int, current_option_value: float) -> dict:
    """
    Returns {"should_exit": bool, "reason": str, "theta_pct_per_day": float, "current_win_probability": float}
    """
    try:
        features = extract_features(ticker, bars, index, option_type, strike, dte)
    except Exception as exc:
        return {"should_exit": False, "reason": "feature extraction failed: " + str(exc)}

    theta = features.get("theta", 0)
    if current_option_value <= 0:
        return {"should_exit": False, "reason": "invalid current option value"}

    theta_pct_per_day = abs(theta) / current_option_value

    model_data = _load_model()
    model = model_data["model"]
    feature_keys = model_data["feature_keys"]

    try:
        feature_vector = [[features.get(key, 0) for key in feature_keys]]
        win_probability = model.predict_proba(feature_vector)[0][1]
    except Exception as exc:
        return {"should_exit": False, "reason": "model prediction failed: " + str(exc)}

    should_exit = theta_pct_per_day >= THETA_BURN_THRESHOLD_PCT and win_probability < WIN_PROBABILITY_THRESHOLD

    reason = (
        "theta burning " + str(round(theta_pct_per_day * 100, 2)) + "%/day, "
        "current model win probability " + str(round(win_probability * 100, 1)) + "%"
    )
    if should_exit:
        reason += " -- edge has decayed, time decay now outpaces realistic remaining upside"

    return {
        "should_exit": should_exit,
        "reason": reason,
        "theta_pct_per_day": round(theta_pct_per_day, 4),
        "current_win_probability": round(win_probability, 4),
    }


if __name__ == "__main__":
    import backtest_engine as be
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    bars = be.get_historical_bars("AAPL", now - timedelta(days=10), now)
    index = len(bars) - 1

    result = check_time_decay_exit("AAPL", bars, index, "call", 320.0, 10, 5.50)
    print(result)
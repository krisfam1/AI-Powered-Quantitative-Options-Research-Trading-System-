from dotenv import load_dotenv
load_dotenv()

"""
Net gamma regime indicator.

IMPORTANT HONEST CAVEAT: this estimates the aggregate market-maker gamma
exposure using standard industry conventions (calls = dealers net short,
contributing positive dealer gamma when hedging; puts = dealers net long,
contributing negative dealer gamma) -- NOT certain, verified positioning
data, since that isn't publicly available. Treat this as an informed
estimate, same as the gamma wall / charm landscape tools built earlier.

Positive regime: dealers are net long gamma -> they hedge AGAINST price
moves -> tends toward choppier, more mean-reverting conditions.

Negative regime: dealers are net short gamma -> they hedge WITH price
moves -> tends toward more trend-prone, squeeze-prone conditions.
"""

from options_data import get_options_chain
from options_pricing import calculate_gamma
from datetime import datetime, timezone


def calculate_net_gamma_regime(ticker: str, current_price: float, volatility: float = 0.30) -> dict:
    calls = get_options_chain(ticker, "call")
    puts = get_options_chain(ticker, "put")

    net_gamma_exposure = 0.0
    total_call_gamma = 0.0
    total_put_gamma = 0.0

    for contract in calls:
        strike = float(contract.strike_price)
        oi = getattr(contract, "open_interest", None)
        if oi is None or int(oi) == 0:
            continue
        days_to_expiry = (contract.expiration_date - datetime.now(timezone.utc).date()).days
        if days_to_expiry <= 0:
            continue
        gamma = calculate_gamma(current_price, strike, days_to_expiry, volatility)
        exposure = gamma * int(oi) * 100
        total_call_gamma += exposure
        net_gamma_exposure += exposure

    for contract in puts:
        strike = float(contract.strike_price)
        oi = getattr(contract, "open_interest", None)
        if oi is None or int(oi) == 0:
            continue
        days_to_expiry = (contract.expiration_date - datetime.now(timezone.utc).date()).days
        if days_to_expiry <= 0:
            continue
        gamma = calculate_gamma(current_price, strike, days_to_expiry, volatility)
        exposure = gamma * int(oi) * 100
        total_put_gamma += exposure
        net_gamma_exposure -= exposure

    if net_gamma_exposure > 0:
        regime = "positive"
        interpretation = "choppy / mean-reverting conditions more likely"
    elif net_gamma_exposure < 0:
        regime = "negative"
        interpretation = "trend-prone / squeeze-prone conditions more likely"
    else:
        regime = "neutral"
        interpretation = "no strong lean either way"

    return {
        "ticker": ticker,
        "regime": regime,
        "net_gamma_exposure": round(net_gamma_exposure, 2),
        "total_call_gamma": round(total_call_gamma, 2),
        "total_put_gamma": round(total_put_gamma, 2),
        "interpretation": interpretation,
    }


if __name__ == "__main__":
    ticker = "AAPL"
    current_price = 309.27

    print("Calculating net gamma regime for " + ticker + "...")
    result = calculate_net_gamma_regime(ticker, current_price)

    print("\nTicker: " + result["ticker"])
    print("Regime: " + result["regime"].upper())
    print("Net gamma exposure: " + str(result["net_gamma_exposure"]))
    print("  (Total call gamma: " + str(result["total_call_gamma"]) + ")")
    print("  (Total put gamma: " + str(result["total_put_gamma"]) + ")")
    print("Interpretation: " + result["interpretation"])
    print("\nNOTE: This is an ESTIMATE based on standard dealer-positioning")
    print("conventions, not verified positioning data.")
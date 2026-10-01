from dotenv import load_dotenv
load_dotenv()

import math
from scipy.stats import norm

def black_scholes_price(spot: float, strike: float, days_to_expiry: float, volatility: float, risk_free_rate: float = 0.04, option_type: str = "call") -> float:
    """
    Estimate an option's theoretical price using the Black-Scholes model.

    spot: current stock price
    strike: option strike price
    days_to_expiry: calendar days remaining until expiration
    volatility: annualized volatility (as a decimal, e.g. 0.30 for 30%)
    risk_free_rate: annualized risk-free rate (default ~4%, roughly current short-term rates)
    option_type: "call" or "put"
    """
    if days_to_expiry <= 0:
        if option_type == "call":
            return max(spot - strike, 0.0)
        else:
            return max(strike - spot, 0.0)

    t = days_to_expiry / 365.0
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * volatility ** 2) * t) / (volatility * math.sqrt(t))
    d2 = d1 - volatility * math.sqrt(t)

    if option_type == "call":
        price = spot * norm.cdf(d1) - strike * math.exp(-risk_free_rate * t) * norm.cdf(d2)
    else:
        price = strike * math.exp(-risk_free_rate * t) * norm.cdf(-d2) - spot * norm.cdf(-d1)

    return max(price, 0.0)


def calculate_delta(spot: float, strike: float, days_to_expiry: float, volatility: float, risk_free_rate: float = 0.04, option_type: str = "call") -> float:
    """Calculate an option's delta (price sensitivity to a $1 move in the underlying)."""
    if days_to_expiry <= 0:
        if option_type == "call":
            return 1.0 if spot > strike else 0.0
        else:
            return -1.0 if spot < strike else 0.0

    t = days_to_expiry / 365.0
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * volatility ** 2) * t) / (volatility * math.sqrt(t))

    if option_type == "call":
        return norm.cdf(d1)
    else:
        return norm.cdf(d1) - 1.0


def calculate_gamma(spot: float, strike: float, days_to_expiry: float, volatility: float, risk_free_rate: float = 0.04) -> float:
    """Calculate an option's gamma (rate of change of delta per $1 move in the underlying).

    Gamma is identical for calls and puts at the same strike/expiry.
    """
    if days_to_expiry <= 0 or volatility <= 0 or spot <= 0:
        return 0.0

    t = days_to_expiry / 365.0
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * volatility ** 2) * t) / (volatility * math.sqrt(t))
    pdf_d1 = norm.pdf(d1)
    gamma = pdf_d1 / (spot * volatility * math.sqrt(t))
    return gamma


def calculate_vega(spot: float, strike: float, days_to_expiry: float, volatility: float, risk_free_rate: float = 0.04) -> float:
    """
    Calculate an option's vega (price sensitivity to a 1% change in
    implied volatility). Same for calls and puts. Returned as the raw
    price change per 1.00 (100 percentage points) change in volatility,
    consistent with this file's existing convention -- divide by 100 if
    you want the more common "per 1% IV move" convention.
    """
    if days_to_expiry <= 0:
        return 0.0

    t = days_to_expiry / 365.0
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * volatility ** 2) * t) / (volatility * math.sqrt(t))

    return spot * norm.pdf(d1) * math.sqrt(t)


def calculate_charm(spot: float, strike: float, days_to_expiry: float, volatility: float, risk_free_rate: float = 0.04, option_type: str = "call") -> float:
    """Calculate an option's charm (rate of change of delta per day that passes).

    Returns the delta decay per calendar day (typically a small negative number for calls near expiry).
    """
    if days_to_expiry <= 0 or volatility <= 0 or spot <= 0:
        return 0.0

    t = days_to_expiry / 365.0
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * volatility ** 2) * t) / (volatility * math.sqrt(t))
    d2 = d1 - volatility * math.sqrt(t)
    pdf_d1 = norm.pdf(d1)

    term1 = pdf_d1 * ((risk_free_rate / (volatility * math.sqrt(t))) - (d2 / (2 * t)))

    if option_type == "call":
        charm = -term1 / 365.0
    else:
        charm = -term1 / 365.0

    return charm

def calculate_theta(spot: float, strike: float, days_to_expiry: float, volatility: float, risk_free_rate: float = 0.04, option_type: str = "call") -> float:
    """Calculate an option's theta (value lost per calendar day from time decay alone)."""
    if days_to_expiry <= 0 or volatility <= 0 or spot <= 0:
        return 0.0

    t = days_to_expiry / 365.0
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * volatility ** 2) * t) / (volatility * math.sqrt(t))
    d2 = d1 - volatility * math.sqrt(t)
    pdf_d1 = norm.pdf(d1)

    term1 = -(spot * pdf_d1 * volatility) / (2 * math.sqrt(t))

    if option_type == "call":
        term2 = risk_free_rate * strike * math.exp(-risk_free_rate * t) * norm.cdf(d2)
        theta_annual = term1 - term2
    else:
        term2 = risk_free_rate * strike * math.exp(-risk_free_rate * t) * norm.cdf(-d2)
        theta_annual = term1 + term2

    return theta_annual / 365.0  # convert to per-calendar-day decay


if __name__ == "__main__":
    price = black_scholes_price(spot=300, strike=305, days_to_expiry=10, volatility=0.30, option_type="call")
    print(f"Estimated call price: ${price:.2f}")
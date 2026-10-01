from dotenv import load_dotenv
load_dotenv()

"""
Delta-based strike selection.

Instead of a fixed percentage offset from the stock price (e.g., always
at-the-money), finds the actual strike whose calculated delta is closest
to a target value -- the way professional options traders actually select
strikes. Since delta moves monotonically with strike (for a fixed
expiration/vol), a straightforward search finds the right strike quickly.
"""

from options_pricing import calculate_delta


def find_strike_for_target_delta(
    stock_price: float,
    days_to_expiry: int,
    volatility: float,
    option_type: str,
    target_delta: float,
    search_range_pct: float = 0.15,
    step_pct: float = 0.005,
) -> float:
    """
    Search a range of strikes around the stock price and return the one
    whose delta is closest to target_delta.

    target_delta should be given as a positive magnitude (e.g., 0.30) for
    both calls and puts -- the function handles the sign internally.
    """
    best_strike = stock_price
    best_diff = float("inf")

    offset = -search_range_pct
    while offset <= search_range_pct:
        strike = round(stock_price * (1 + offset), 2)
        if strike <= 0:
            offset += step_pct
            continue

        delta = calculate_delta(stock_price, strike, days_to_expiry, volatility, option_type=option_type)
        diff = abs(abs(delta) - target_delta)

        if diff < best_diff:
            best_diff = diff
            best_strike = strike

        offset += step_pct

    return best_strike


if __name__ == "__main__":
    stock_price = 300.0
    dte = 14
    vol = 0.30

    for target in [0.30, 0.40, 0.50]:
        strike = find_strike_for_target_delta(stock_price, dte, vol, "call", target)
        actual_delta = calculate_delta(stock_price, strike, dte, vol, option_type="call")
        print("Target delta " + str(target) + ": strike=$" + str(strike) + " (actual delta=" + str(round(actual_delta, 3)) + ")")
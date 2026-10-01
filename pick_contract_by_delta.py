from dotenv import load_dotenv
load_dotenv()

"""
Live delta-based contract picker.

Unlike the backtest (which calculates a theoretical strike), live trading
must pick from ACTUAL listed contracts. This function evaluates every
real, available contract's true delta (using its actual strike and real
expiration date) and picks the one closest to the target.
"""

from datetime import date
from options_pricing import calculate_delta


def pick_contract_by_target_delta(contracts, current_price: float, option_type: str, target_delta: float, volatility: float = 0.30):
    """
    Among real, listed contracts (all the same option_type, since the
    caller already fetched calls or puts specifically), pick the one whose
    calculated delta is closest to target_delta (positive magnitude, e.g. 0.30).
    """
    if not contracts:
        return None

    best_contract = None
    best_diff = float("inf")

    for contract in contracts:
        try:
            strike = float(contract.strike_price)
            days_to_expiry = (contract.expiration_date - date.today()).days
            if days_to_expiry <= 0:
                continue

            delta = calculate_delta(current_price, strike, days_to_expiry, volatility, option_type=option_type)
            diff = abs(abs(delta) - target_delta)

            if diff < best_diff:
                best_diff = diff
                best_contract = contract
        except Exception:
            continue

    return best_contract
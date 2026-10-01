from dotenv import load_dotenv
load_dotenv()

from options_data import get_options_chain
from options_pricing import calculate_gamma
import backtest_engine as be
from datetime import datetime, timezone


def build_gamma_landscape(ticker: str, current_price: float, volatility: float = 0.30) -> list[dict]:
    """
    Build a per-strike gamma exposure estimate using open interest and calculated gamma.

    This is an ESTIMATE, not certain dealer positioning data — it combines real open
    interest with theoretical gamma to approximate where gamma concentration sits.
    """
    calls = get_options_chain(ticker, "call")
    puts = get_options_chain(ticker, "put")

    landscape = {}

    for contract in list(calls) + list(puts):
        strike = float(contract.strike_price)
        oi = getattr(contract, "open_interest", None)
        if oi is None:
            continue
        oi = int(oi)
        if oi == 0:
            continue

        days_to_expiry = (contract.expiration_date - datetime.now(timezone.utc).date()).days
        if days_to_expiry <= 0:
            continue

        gamma = calculate_gamma(current_price, strike, days_to_expiry, volatility)
        # Each contract controls 100 shares; gamma exposure scales with OI and contract size
        gamma_exposure = gamma * oi * 100

        if strike not in landscape:
            landscape[strike] = 0.0
        landscape[strike] += gamma_exposure

    result = [{"strike": k, "gamma_exposure": v} for k, v in sorted(landscape.items())]
    return result


def find_gamma_walls(landscape: list[dict], top_n: int = 3) -> list[dict]:
    """Return the strikes with the highest gamma concentration — potential 'walls'."""
    sorted_by_gamma = sorted(landscape, key=lambda x: x["gamma_exposure"], reverse=True)
    return sorted_by_gamma[:top_n]


if __name__ == "__main__":
    ticker = "AAPL"
    current_price = 301.50

    print(f"Building gamma landscape for {ticker}...")
    landscape = build_gamma_landscape(ticker, current_price)
    print(f"Found gamma data across {len(landscape)} strikes")

    walls = find_gamma_walls(landscape)
    print(f"\nTop gamma concentration strikes (potential walls):")
    for w in walls:
        print(f"  Strike ${w['strike']}: gamma_exposure={w['gamma_exposure']:.2f}")
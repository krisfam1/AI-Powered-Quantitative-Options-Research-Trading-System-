from dotenv import load_dotenv
load_dotenv()

from options_data import get_options_chain
from options_pricing import calculate_charm
from datetime import datetime, timezone


def build_charm_landscape(ticker: str, current_price: float, volatility: float = 0.30) -> list[dict]:
    """
    Build a per-strike charm exposure estimate using open interest and calculated charm.

    Charm concentration indicates where delta-hedging pressure may build as expiration
    approaches (pinning behavior near heavily-held strikes).
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

        charm = calculate_charm(current_price, strike, days_to_expiry, volatility, option_type="call")
        charm_exposure = abs(charm) * oi * 100

        if strike not in landscape:
            landscape[strike] = 0.0
        landscape[strike] += charm_exposure

    result = [{"strike": k, "charm_exposure": v} for k, v in sorted(landscape.items())]
    return result


def find_charm_pins(landscape: list[dict], top_n: int = 3) -> list[dict]:
    """Return the strikes with the highest charm concentration — potential pinning levels."""
    sorted_by_charm = sorted(landscape, key=lambda x: x["charm_exposure"], reverse=True)
    return sorted_by_charm[:top_n]


if __name__ == "__main__":
    ticker = "AAPL"
    current_price = 301.50

    print(f"Building charm landscape for {ticker}...")
    landscape = build_charm_landscape(ticker, current_price)
    print(f"Found charm data across {len(landscape)} strikes")

    pins = find_charm_pins(landscape)
    print(f"\nTop charm concentration strikes (potential pinning levels):")
    for p in pins:
        print(f"  Strike ${p['strike']}: charm_exposure={p['charm_exposure']:.4f}")
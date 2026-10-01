from dotenv import load_dotenv
load_dotenv()

import os
from datetime import date, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOptionContractsRequest
from alpaca.trading.enums import ContractType

api_key = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")

trading_client = TradingClient(api_key, secret_key, paper=True)

def get_options_chain(ticker: str, contract_type: str = "call"):
    """Fetch available options contracts for a ticker, filtered to 5-35 days out."""
    today = date.today()
    min_exp = today + timedelta(days=5)
    max_exp = today + timedelta(days=35)

    request = GetOptionContractsRequest(
        underlying_symbols=[ticker],
        type=ContractType.CALL if contract_type == "call" else ContractType.PUT,
        status="active",
        expiration_date_gte=min_exp,
        expiration_date_lte=max_exp,
    )
    contracts = trading_client.get_option_contracts(request)
    return contracts.option_contracts if hasattr(contracts, 'option_contracts') else contracts

def filter_near_the_money(contracts, current_price: float, pct_range: float = 0.05):
    """Keep only contracts within pct_range of the current stock price."""
    low = current_price * (1 - pct_range)
    high = current_price * (1 + pct_range)
    return [c for c in contracts if low <= float(c.strike_price) <= high]

def pick_best_contract(contracts):
    """Among candidates, pick the one with highest open interest (most liquid)."""
    with_oi = [c for c in contracts if getattr(c, 'open_interest', None) is not None]
    if not with_oi:
        return contracts[0] if contracts else None
    return max(with_oi, key=lambda c: int(c.open_interest))

if __name__ == "__main__":
    ticker = "AAPL"
    current_price = 301.50  # placeholder — we'll pull this live next

    print(f"Fetching {ticker} call options, 5-35 days out...")
    chain = get_options_chain(ticker, "call")
    print(f"Found {len(chain)} contracts in date range")

    near_money = filter_near_the_money(chain, current_price)
    print(f"{len(near_money)} contracts within 5% of current price (${current_price})")
    for c in near_money:
        print(f"  {c.symbol} | strike: ${c.strike_price} | expiration: {c.expiration_date} | open_interest: {getattr(c, 'open_interest', 'N/A')}")

    best = pick_best_contract(near_money)
    if best:
        print(f"\nBest pick (highest open interest): {best.symbol} | strike ${best.strike_price} | exp {best.expiration_date}")
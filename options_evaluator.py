from dotenv import load_dotenv
load_dotenv()

import os
from datetime import date, datetime, timezone
import math
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import DataFeed

api_key = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")
data_client = StockHistoricalDataClient(api_key, secret_key)

from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import OptionLatestQuoteRequest

option_data_client = OptionHistoricalDataClient(api_key, secret_key)


def get_live_premium(contract_symbol: str) -> float:
    """Fetch the current live ask price for an option contract (what you'd pay to buy it)."""
    request = OptionLatestQuoteRequest(symbol_or_symbols=contract_symbol)
    quote = option_data_client.get_option_latest_quote(request)
    latest = quote[contract_symbol]
    return float(latest.ask_price)


def get_live_bid_price(contract_symbol: str) -> float:
    """Fetch the current live bid price for an option contract (what you'd actually
    receive if you sold it right now -- use this for valuing an EXISTING position,
    not get_live_premium, which returns the ask price used for new entries."""
    request = OptionLatestQuoteRequest(symbol_or_symbols=contract_symbol)
    quote = option_data_client.get_option_latest_quote(request)
    latest = quote[contract_symbol]
    return float(latest.bid_price)


def get_recent_volatility(ticker: str, lookback_days: int = 20) -> float:
    """Return the average daily % price move over the lookback period (a simple volatility measure)."""
    end = datetime.now(timezone.utc)
    start = end - __import__('datetime').timedelta(days=lookback_days + 10)
    request = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame(1, TimeFrameUnit.Day),
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )
    bars = list(data_client.get_stock_bars(request)[ticker])
    if len(bars) < 2:
        return 0.0
    daily_moves = [
        abs(float(bars[i].close) - float(bars[i - 1].close)) / float(bars[i - 1].close)
        for i in range(1, len(bars))
    ]
    return sum(daily_moves[-lookback_days:]) / len(daily_moves[-lookback_days:])


def days_to_expiration(expiration_date) -> int:
    """Return calendar days remaining until expiration."""
    if isinstance(expiration_date, str):
        expiration_date = date.fromisoformat(expiration_date)
    return (expiration_date - date.today()).days


def classify_dte_bucket(dte: int) -> str:
    if dte <= 3:
        return "short"
    elif dte <= 10:
        return "medium"
    else:
        return "long"


def get_intraday_move(ticker: str) -> float:
    end = datetime.now(timezone.utc)
    start = end.replace(hour=0, minute=0, second=0, microsecond=0)
    request = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame(5, TimeFrameUnit.Minute),
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )
    bars = list(data_client.get_stock_bars(request)[ticker])
    if not bars:
        return 0.0
    day_open = float(bars[0].open)
    day_high = max(float(b.high) for b in bars)
    day_low = min(float(b.low) for b in bars)
    return (day_high - day_low) / day_open
def evaluate_contract(contract, current_stock_price: float, contract_premium: float, ticker: str) -> dict:
    """
    Evaluate a single options contract's risk/reward.
    Returns a dict with breakeven info, required move, and a basic viability flag.
    """
    strike = float(contract.strike_price)
    dte = days_to_expiration(contract.expiration_date)

    # Breakeven: how far the stock needs to move for this contract to be worth exactly what was paid
    breakeven_price = strike + contract_premium
    required_move_pct = (breakeven_price - current_stock_price) / current_stock_price

    # Historical daily volatility, scaled to the contract's timeframe
    daily_vol = get_recent_volatility(ticker)
    bucket = classify_dte_bucket(dte)

    if bucket == "short":
        intraday_move = get_intraday_move(ticker)
        expected_move_pct = intraday_move * 1.5
    else:
        expected_move_pct = daily_vol * math.sqrt(max(dte, 1))  # rough scaling: volatility grows with sqrt(time)

    # Simple viability check: is the required move realistic given typical stock movement in this timeframe?
    viable = required_move_pct <= expected_move_pct

    return {
        "symbol": contract.symbol,
        "strike": strike,
        "dte": dte,
	"dte_bucket": bucket,
        "premium": contract_premium,
        "breakeven_price": round(breakeven_price, 2),
        "required_move_pct": round(required_move_pct * 100, 2),
        "expected_move_pct": round(expected_move_pct * 100, 2),
        "viable": viable,
    }


if __name__ == "__main__":
    from options_data import get_options_chain, filter_near_the_money, pick_best_contract

    ticker = "AAPL"
    current_price = 301.50

    chain = get_options_chain(ticker, "call")
    near_money = filter_near_the_money(chain, current_price)
    best = pick_best_contract(near_money)

    if best:
        # Placeholder premium since we haven't pulled live option quotes yet
        estimated_premium = get_live_premium(best.symbol)
        print(f"Live premium fetched: ${estimated_premium}")
        result = evaluate_contract(best, current_price, estimated_premium, ticker)
        print("Contract evaluation:")
        for key, value in result.items():
            print(f"  {key}: {value}")
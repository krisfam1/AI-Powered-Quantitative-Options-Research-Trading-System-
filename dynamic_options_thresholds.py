from dotenv import load_dotenv
load_dotenv()

from options_pricing import black_scholes_price, calculate_delta, calculate_gamma
import backtest_engine as be


def calculate_dynamic_thresholds(
    ticker: str,
    bars: list,
    current_index: int,
    spot: float,
    strike: float,
    days_to_expiry: float,
    volatility: float,
    option_type: str = "call",
    stop_atr_multiplier: float = 1.75,
    target_atr_multiplier: float = 2.0,
) -> dict:
    """
    Calculate stop-loss/take-profit thresholds based on the underlying stock's actual
    ATR (real recent volatility), translated into option price terms via delta.

    Core idea: a stop should trigger when the STOCK has genuinely moved against the
    thesis by more than its normal daily range — not based on an arbitrary percentage
    of the option's premium. This avoids getting shaken out by ordinary noise while
    still cutting losses on genuine adverse moves.
    """
    premium = black_scholes_price(spot, strike, days_to_expiry, volatility, option_type=option_type)
    if premium <= 0:
        return {"stop_loss_pct": 0.40, "take_profit_pct": 0.75, "reasoning": "premium is zero, using defaults"}

    delta = calculate_delta(spot, strike, days_to_expiry, volatility, option_type=option_type)
    # Use DAILY bars for ATR here, not the 5-min bars — option risk should reflect
    # multi-day price movement, not a single 5-minute window.
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from alpaca.data.enums import DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    import os as _os
    from datetime import timedelta as _timedelta

    current_timestamp = bars[current_index].timestamp
    daily_start = current_timestamp - _timedelta(days=30)
    _api_key = _os.environ.get("ALPACA_API_KEY")
    _secret_key = _os.environ.get("ALPACA_SECRET_KEY")
    _client = StockHistoricalDataClient(_api_key, _secret_key)
    _request = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame(1, TimeFrameUnit.Day),
        start=daily_start,
        end=current_timestamp,
        feed=DataFeed.IEX,
    )
    daily_bars = list(_client.get_stock_bars(_request)[ticker])
    atr = be.calculate_atr(daily_bars, len(daily_bars) - 1) if len(daily_bars) > 15 else 0.0

    if atr <= 0 or abs(delta) <= 0:
        return {"stop_loss_pct": 0.40, "take_profit_pct": 0.75, "reasoning": "ATR or delta unavailable, using defaults"}

    # How much would the option's price move if the stock made a typical (1x ATR) move?
    expected_option_move = atr * abs(delta)
    expected_move_pct_of_premium = expected_option_move / premium

    stop_loss_pct = min(expected_move_pct_of_premium * stop_atr_multiplier, 0.40)  # hard ceiling at 40%
    stop_loss_pct = max(stop_loss_pct, 0.15)  # hard floor at 15% — never absurdly tight

    take_profit_pct = min(expected_move_pct_of_premium * target_atr_multiplier, 1.50)  # ceiling at 150%
    take_profit_pct = max(take_profit_pct, 0.30)  # floor at 30%

    reasoning = (
        f"stock ATR=${atr:.2f}, delta={delta:.2f} -> expected option move "
        f"${expected_option_move:.2f} ({expected_move_pct_of_premium*100:.1f}% of premium)"
    )

    return {
        "stop_loss_pct": round(stop_loss_pct, 2),
        "take_profit_pct": round(take_profit_pct, 2),
        "expected_move_pct_of_premium": round(expected_move_pct_of_premium * 100, 2),
        "reasoning": reasoning,
    }


if __name__ == "__main__":
    from datetime import datetime, timezone, timedelta

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    bars = be.get_historical_bars("AAPL", start, end)
    idx = len(bars) - 1
    spot = float(bars[idx].close)

    print("Short-dated (3 days), ATM:")
    result = calculate_dynamic_thresholds("AAPL", bars, idx, spot, spot, 3, 0.30, option_type="call")
    print(f"  {result}")

    print("\nMedium-dated (14 days), ATM:")
    result = calculate_dynamic_thresholds("AAPL", bars, idx, spot, spot, 14, 0.30, option_type="call")
    print(f"  {result}")

    print("\nLonger-dated (30 days), ATM:")
    result = calculate_dynamic_thresholds("AAPL", bars, idx, spot, spot, 30, 0.30, option_type="call")
    print(f"  {result}")
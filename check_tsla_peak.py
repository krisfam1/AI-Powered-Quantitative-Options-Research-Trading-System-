from dotenv import load_dotenv
load_dotenv()

from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import OptionBarsRequest
from alpaca.data.timeframe import TimeFrame
import os
from datetime import datetime, timezone

api_key = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")
option_client = OptionHistoricalDataClient(api_key, secret_key)

symbol = "TSLA260831P00345000"
entry_premium = 4.30

start = datetime(2026, 8, 25, 13, 0, 0, tzinfo=timezone.utc)
end = datetime.now(timezone.utc)

request = OptionBarsRequest(
    symbol_or_symbols=symbol,
    timeframe=TimeFrame.Minute,
    start=start,
    end=end,
)

try:
    bars = option_client.get_option_bars(request)
    contract_bars = bars[symbol]

    print("Checking intraday price history for " + symbol + ":\n")
    print("Entry premium: $" + str(entry_premium) + "\n")

    peak_price = 0.0
    peak_time = None

    for bar in contract_bars:
        if float(bar.close) > peak_price:
            peak_price = float(bar.close)
            peak_time = bar.timestamp

    if peak_price > 0:
        peak_pct = (peak_price - entry_premium) / entry_premium * 100
        print("PEAK price today: $" + str(round(peak_price, 2)) + " at " + str(peak_time))
        print("Peak gain: " + str(round(peak_pct, 1)) + "%")
    else:
        print("No bar data found.")

except Exception as exc:
    print("FAILED: " + str(exc))
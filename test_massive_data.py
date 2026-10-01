from dotenv import load_dotenv
load_dotenv()

import os
from massive import RESTClient

api_key = os.environ.get("MASSIVE_API_KEY")
client = RESTClient(api_key)

symbol = "O:TSLA260831P00345000"
entry_premium = 4.30

print("Fetching real historical minute data for " + symbol + " today...\n")

aggs = []
for a in client.list_aggs(
    ticker=symbol,
    multiplier=1,
    timespan="minute",
    from_="2026-08-25",
    to="2026-08-25",
    limit=50000,
):
    aggs.append(a)

print("Total bars found: " + str(len(aggs)))

if aggs:
    peak_price = 0.0
    peak_time = None

    for bar in aggs:
        if bar.close > peak_price:
            peak_price = bar.close
            peak_time = bar.timestamp

    peak_pct = (peak_price - entry_premium) / entry_premium * 100
    print("\nPEAK price today: $" + str(round(peak_price, 2)))
    print("Peak gain: " + str(round(peak_pct, 1)) + "%")
    print("Peak timestamp (ms): " + str(peak_time))
else:
    print("No data returned -- may need different symbol format or date range.")
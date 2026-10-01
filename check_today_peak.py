from dotenv import load_dotenv
load_dotenv()

import os
from massive import RESTClient
from datetime import datetime, timezone

api_key = os.environ.get("MASSIVE_API_KEY")
client = RESTClient(api_key)

symbol = "O:TSLA260831P00345000"
entry_premium = 4.30

print("Fetching TODAY's (2026-08-26) real minute data for " + symbol + "...\n")

aggs = []
for a in client.list_aggs(
    ticker=symbol,
    multiplier=1,
    timespan="minute",
    from_="2026-08-26",
    to="2026-08-26",
    limit=50000,
):
    aggs.append(a)

print("Total bars found today: " + str(len(aggs)) + "\n")

if aggs:
    peak_price = 0.0
    peak_time = None

    for bar in aggs:
        if bar.close > peak_price:
            peak_price = bar.close
            peak_time = bar.timestamp

    peak_pct = (peak_price - entry_premium) / entry_premium * 100
    peak_dt = datetime.fromtimestamp(peak_time / 1000, tz=timezone.utc)
    print("PEAK price TODAY: $" + str(round(peak_price, 2)))
    print("Peak gain: " + str(round(peak_pct, 1)) + "%")
    print("Peak time: " + str(peak_dt))

    print("\nAll bars from 9:30-10:00 AM ET today (13:30-14:00 UTC):")
    for bar in aggs:
        dt = datetime.fromtimestamp(bar.timestamp / 1000, tz=timezone.utc)
        if (dt.hour == 13 and dt.minute >= 30) or (dt.hour == 14 and dt.minute == 0):
            pct = (bar.close - entry_premium) / entry_premium * 100
            print(str(dt) + "  close=$" + str(round(bar.close, 2)) + "  (" + str(round(pct, 1)) + "%)")
else:
    print("No data returned for today.")
from dotenv import load_dotenv
load_dotenv()

import os
from massive import RESTClient
from datetime import datetime, timezone

api_key = os.environ.get("MASSIVE_API_KEY")
client = RESTClient(api_key)

symbol = "O:TSLA260831P00345000"
entry_premium = 4.30

print("Fetching real historical minute data for " + symbol + " on 2026-08-25...\n")

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

print("Total bars found: " + str(len(aggs)) + "\n")

print("Bars specifically between 9:30-10:00 AM ET (13:30-14:00 UTC):\n")

for bar in aggs:
    dt = datetime.fromtimestamp(bar.timestamp / 1000, tz=timezone.utc)
    if dt.hour == 13 and dt.minute >= 30 or dt.hour == 14 and dt.minute == 0:
        pct = (bar.close - entry_premium) / entry_premium * 100
        print(str(dt) + "  close=$" + str(round(bar.close, 2)) + "  (" + str(round(pct, 1)) + "%)")
from dotenv import load_dotenv
load_dotenv()

import os
import requests
from datetime import datetime, timedelta

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"

SAMPLE_TICKER = "AAPL"
SAMPLE_DATE = "2026-04-15"

obs_date = datetime.strptime(SAMPLE_DATE, "%Y-%m-%d").date()
params = {
    "filter[underlying_symbol]": SAMPLE_TICKER,
    "filter[tradetime_from]": SAMPLE_DATE,
    "filter[tradetime_to]": SAMPLE_DATE,
    "filter[exp_date_from]": obs_date.isoformat(),
    "filter[exp_date_to]": (obs_date + timedelta(days=45)).isoformat(),
    "api_token": EODHD_API_TOKEN,
    "page[limit]": 1000,
}

resp = requests.get(BASE_URL, params=params, timeout=30)
resp.raise_for_status()
records = resp.json().get("data", [])
print("Total records: " + str(len(records)))

matching = 0
stale = 0
gap_days = []
for r in records:
    record_id = r.get("id", "")
    parts = record_id.split("-", 1)
    if len(parts) != 2:
        continue
    try:
        id_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
    except ValueError:
        continue
    if id_date == obs_date:
        matching += 1
    else:
        stale += 1
        gap_days.append((id_date - obs_date).days)

print("Matching (correct date): " + str(matching))
print("Stale (different date): " + str(stale))
if gap_days:
    print("Gap distribution (days from requested date): min=" + str(min(gap_days)) + " max=" + str(max(gap_days)) + " avg=" + str(round(sum(gap_days)/len(gap_days), 1)))
    from collections import Counter
    print("Gap breakdown: " + str(sorted(Counter(gap_days).items())))
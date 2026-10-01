from dotenv import load_dotenv
load_dotenv()

"""
Data-availability check for a proposed call-wall-distance replication
window: 2026-03-13 to 2026-06-10 (90 calendar days immediately
PRECEDING the original Phase 4 study window, zero overlap).

Verifies, on ONE real sample day, that everything Phase 4 depended on
is genuinely available for this new period: record-ID snapshot-date
semantics, historical OI, historical gamma, and the real Alpaca
underlying price -- before proposing implementation.
"""

import os
import requests
from datetime import datetime, timedelta, timezone
import backtest_engine as be

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"

SAMPLE_TICKER = "AAPL"
SAMPLE_DATE = "2026-04-15"  # a real, representative day inside the proposed new window

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

print("Checking EODHD data availability for " + SAMPLE_TICKER + " on " + SAMPLE_DATE + " (proposed replication window)...")
resp = requests.get(BASE_URL, params=params, timeout=30)
resp.raise_for_status()
records = resp.json().get("data", [])
print("Records returned: " + str(len(records)))

if records:
    sample = records[0]
    a = sample["attributes"]
    print("\nSample record ID: " + str(sample.get("id")))
    print("Contract: " + str(a.get("contract")))
    print("Open interest present: " + str(a.get("open_interest") is not None))
    print("Gamma present: " + str(a.get("gamma") is not None))
    print("Expiration: " + str(a.get("exp_date")))

    id_suffix = sample.get("id", "").split("-", 1)
    print("\nRecord-ID date suffix: " + str(id_suffix[1] if len(id_suffix) == 2 else "PARSE FAILED"))
    print("(Should be a real date at or near " + SAMPLE_DATE + ")")
else:
    print("\nNO RECORDS RETURNED -- this proposed window may not be usable, needs investigation before proceeding.")

print("\n--- Checking real underlying price via Alpaca for the same date ---")
start = datetime.strptime(SAMPLE_DATE, "%Y-%m-%d").replace(tzinfo=timezone.utc)
end = start + timedelta(days=1)
bars = be.get_historical_bars(SAMPLE_TICKER, start, end)
if bars:
    print("Alpaca close for " + SAMPLE_DATE + ": $" + str(float(bars[-1].close)))
else:
    print("NO ALPACA BARS RETURNED for this date -- needs investigation.")
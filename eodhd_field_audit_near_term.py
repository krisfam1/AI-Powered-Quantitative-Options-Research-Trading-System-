from dotenv import load_dotenv
load_dotenv()

"""
EODHD Data Audit -- Step 2: NEAR-TERM field inventory, filtered to
contracts close to our actual 14-day DTE convention -- not just
whatever EODHD returns unfiltered (which skewed toward a 2.5-year LEAP
last time). This is the population that actually matters for the project.
"""

import os
import requests
import json
from datetime import datetime, timedelta

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"

TICKER = "AAPL"
DATE = "2026-07-15"
target_date = datetime.strptime(DATE, "%Y-%m-%d").date()
exp_from = (target_date + timedelta(days=7)).isoformat()
exp_to = (target_date + timedelta(days=21)).isoformat()

print("=" * 100)
print("EODHD NEAR-TERM FIELD AUDIT -- " + TICKER + " " + DATE + " (contracts expiring " + exp_from + " to " + exp_to + ")")
print("=" * 100)

params = {
    "filter[underlying_symbol]": TICKER,
    "filter[tradetime_from]": DATE,
    "filter[tradetime_to]": DATE,
    "filter[exp_date_from]": exp_from,
    "filter[exp_date_to]": exp_to,
    "api_token": EODHD_API_TOKEN,
    "page[limit]": 200,
}

resp = requests.get(BASE_URL, params=params, timeout=60)
resp.raise_for_status()
data = resp.json()

records = data.get("data", [])
print("Records returned (near-term contracts this day): " + str(len(records)))

if not records:
    print("NO NEAR-TERM RECORDS RETURNED for this date/DTE range.")
else:
    print("\nSample contract (first record):")
    print(json.dumps(records[0]["attributes"], indent=2))

    all_keys = set()
    for r in records:
        all_keys.update(r.get("attributes", {}).keys())

    print("\n" + "=" * 100)
    print("PER-KEY NULL RATE, NEAR-TERM CONTRACTS ONLY (n=" + str(len(records)) + ")")
    print("=" * 100)
    for k in sorted(all_keys):
        values = [r.get("attributes", {}).get(k) for r in records]
        non_null = [v for v in values if v is not None]
        null_rate = (len(values) - len(non_null)) / len(values) * 100
        zero_count = len([v for v in non_null if v == 0])
        print("  " + k + ": null_rate=" + str(round(null_rate,1)) + "% | zero_rate=" + str(round(zero_count/len(values)*100,1) if values else 0) + "%")

    print("\n" + "=" * 100)
    print("VOLUME / LIQUIDITY REALITY CHECK -- how many near-term contracts had REAL trading activity?")
    print("=" * 100)
    zero_volume = len([r for r in records if r["attributes"].get("volume") == 0])
    zero_oi = len([r for r in records if r["attributes"].get("open_interest") == 0])
    print("Contracts with volume=0: " + str(zero_volume) + " / " + str(len(records)) + " (" + str(round(zero_volume/len(records)*100,1)) + "%)")
    print("Contracts with open_interest=0: " + str(zero_oi) + " / " + str(len(records)) + " (" + str(round(zero_oi/len(records)*100,1)) + "%)")

    print("\n" + "=" * 100)
    print("DTE DISTRIBUTION IN THIS SAMPLE (confirming the filter worked as intended)")
    print("=" * 100)
    dtes = [r["attributes"].get("dte") for r in records if r["attributes"].get("dte") is not None]
    print("min=" + str(min(dtes)) + " max=" + str(max(dtes)) + " (target range was 7-21)")

print("\nNEAR-TERM FIELD AUDIT COMPLETE. No data purchased, no data modified.")
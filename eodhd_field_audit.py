from dotenv import load_dotenv
load_dotenv()

"""
EODHD Data Audit -- Step 1: Raw field inventory.
Pulls one real, complete raw response for a known-good ticker/date
(within the already-validated clean window) and inspects EVERY field
actually present -- not just the ones we've used so far (IV only).
Read-only, no data modified, no new purchases.
"""

import os
import requests
import json

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"

TICKER = "AAPL"
DATE = "2026-07-15"  # within the already-validated clean window

print("=" * 100)
print("EODHD RAW FIELD AUDIT -- " + TICKER + " " + DATE)
print("=" * 100)

params = {
    "filter[underlying_symbol]": TICKER,
    "filter[tradetime_from]": DATE,
    "filter[tradetime_to]": DATE,
    "api_token": EODHD_API_TOKEN,
    "page[limit]": 10,
}

resp = requests.get(BASE_URL, params=params, timeout=60)
resp.raise_for_status()
data = resp.json()

records = data.get("data", [])
print("Records returned (sample): " + str(len(records)))

if not records:
    print("NO RECORDS RETURNED -- cannot proceed with field audit for this date/ticker.")
else:
    print("\n" + "=" * 100)
    print("FULL RAW RECORD STRUCTURE (first record, unmodified)")
    print("=" * 100)
    print(json.dumps(records[0], indent=2))

    print("\n" + "=" * 100)
    print("ALL ATTRIBUTE KEYS PRESENT (across sample)")
    print("=" * 100)
    all_keys = set()
    for r in records:
        all_keys.update(r.get("attributes", {}).keys())
    for k in sorted(all_keys):
        print("  " + k)

    print("\n" + "=" * 100)
    print("PER-KEY: SAMPLE VALUE + NULL RATE (in this sample)")
    print("=" * 100)
    for k in sorted(all_keys):
        values = [r.get("attributes", {}).get(k) for r in records]
        non_null = [v for v in values if v is not None]
        sample_val = non_null[0] if non_null else None
        null_rate = (len(values) - len(non_null)) / len(values) * 100
        print("  " + k + ": sample=" + str(sample_val) + " | null_rate=" + str(round(null_rate,1)) + "%")

print("\n" + "=" * 100)
print("TOP-LEVEL RESPONSE KEYS (metadata, pagination, etc.)")
print("=" * 100)
for k in data.keys():
    print("  " + k + ": " + str(type(data[k])))

print("\nRAW FIELD AUDIT COMPLETE. No data purchased, no data modified.")
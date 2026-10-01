from dotenv import load_dotenv
load_dotenv()

import os
import requests
from datetime import datetime, timedelta
from collections import Counter

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"

SAMPLE_TICKER = "AAPL"
SAMPLE_DATE = "2026-03-18"

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

print("=" * 80)
print("SECOND SAMPLE DAY AUDIT -- " + SAMPLE_TICKER + " " + SAMPLE_DATE)
print("=" * 80)

resp = requests.get(BASE_URL, params=params, timeout=30)
resp.raise_for_status()
records = resp.json().get("data", [])
total = len(records)
print("1. Raw records: " + str(total))

matching = []
stale_gaps = []
missing_oi = 0
missing_gamma = 0
seen_contracts = {}
duplicates = 0

for r in records:
    a = r.get("attributes", {})
    record_id = r.get("id", "")
    parts = record_id.split("-", 1)
    id_date = None
    if len(parts) == 2:
        try:
            id_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
        except ValueError:
            pass

    if id_date == obs_date:
        matching.append(r)
    elif id_date is not None:
        stale_gaps.append((id_date - obs_date).days)

    if a.get("open_interest") is None:
        missing_oi += 1
    if a.get("gamma") is None:
        missing_gamma += 1

    contract = a.get("contract")
    if contract in seen_contracts:
        duplicates += 1
    seen_contracts[contract] = seen_contracts.get(contract, 0) + 1

retained = len(matching)
excluded = total - retained
retention_pct = round(retained / total * 100, 1) if total else 0
stale_pct = round(excluded / total * 100, 1) if total else 0

print("2. Retained records: " + str(retained))
print("3. Excluded records: " + str(excluded))
print("4. Retention percentage: " + str(retention_pct) + "%")
print("5. Stale-record percentage: " + str(stale_pct) + "%")

if stale_gaps:
    print("6. Staleness gap distribution: min=" + str(min(stale_gaps)) + " max=" + str(max(stale_gaps)) + " avg=" + str(round(sum(stale_gaps)/len(stale_gaps), 1)))
    print("7. Maximum staleness gap: " + str(max(stale_gaps)) + " days")
else:
    print("6-7. No stale records found.")

bucket_1_2 = len([g for g in stale_gaps if 1 <= g <= 2])
bucket_3_6 = len([g for g in stale_gaps if 3 <= g <= 6])
bucket_7_13 = len([g for g in stale_gaps if 7 <= g <= 13])
bucket_14_19 = len([g for g in stale_gaps if 14 <= g <= 19])
bucket_20plus = len([g for g in stale_gaps if g >= 20])
print("8. Gap buckets: 1-2d=" + str(bucket_1_2) + " 3-6d=" + str(bucket_3_6) + " 7-13d=" + str(bucket_7_13) + " 14-19d=" + str(bucket_14_19) + " 20+d=" + str(bucket_20plus))

print("9. Missing OI (across all raw records): " + str(missing_oi))
print("10. Missing gamma (across all raw records): " + str(missing_gamma))
print("11. Duplicate contract entries: " + str(duplicates))
print("12. Contract coverage: " + str(len(seen_contracts)) + " unique contracts, " + SAMPLE_TICKER + " only (single-ticker check)")

print("\n" + "=" * 80)
print("COMPARISON TO FIRST SAMPLE DAY (2026-04-15)")
print("=" * 80)
print("Day 1 (04-15): 801 raw, 581 retained (72.5%), 220 stale (27.5%), max gap=19 days")
print("Day 2 (" + SAMPLE_DATE + "): " + str(total) + " raw, " + str(retained) + " retained (" + str(retention_pct) + "%), " + str(excluded) + " stale (" + str(stale_pct) + "%), max gap=" + (str(max(stale_gaps)) if stale_gaps else "N/A") + " days")
from dotenv import load_dotenv
load_dotenv()

"""
Two additional data-quality audits within the Dec-Feb-Mar window,
selected BEFORE viewing any data:
- 2026-01-14 (ordinary mid-January day, clear of holidays)
- 2026-03-11 (ordinary mid-March day, clear of DST change and window edge)
"""

import os
import requests
from datetime import datetime, timedelta

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
SAMPLE_TICKER = "AAPL"
SAMPLE_DATES = ["2026-01-14", "2026-03-11"]


def audit_day(date_str):
    obs_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    params = {
        "filter[underlying_symbol]": SAMPLE_TICKER,
        "filter[tradetime_from]": date_str,
        "filter[tradetime_to]": date_str,
        "filter[exp_date_from]": obs_date.isoformat(),
        "filter[exp_date_to]": (obs_date + timedelta(days=45)).isoformat(),
        "api_token": EODHD_API_TOKEN,
        "page[limit]": 1000,
    }
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    records = resp.json().get("data", [])
    total = len(records)

    matching = 0
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
            matching += 1
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

    excluded = total - matching
    print("Date: " + date_str)
    print("  1. Raw records: " + str(total))
    print("  2. Retained: " + str(matching))
    print("  3. Excluded: " + str(excluded))
    print("  4. Retention %: " + (str(round(matching/total*100,1)) if total else "N/A"))
    print("  5. Stale %: " + (str(round(excluded/total*100,1)) if total else "N/A"))
    if stale_gaps:
        print("  6. Gap distribution: min=" + str(min(stale_gaps)) + " max=" + str(max(stale_gaps)) + " avg=" + str(round(sum(stale_gaps)/len(stale_gaps),1)))
        print("  7. Max gap: " + str(max(stale_gaps)) + " days")
    else:
        print("  6-7. No stale records.")
    print("  8. Duplicate contract entries: " + str(duplicates))
    print("  9. Missing OI: " + str(missing_oi))
    print("  10. Missing gamma: " + str(missing_gamma))
    print("  11. Unique contracts (AAPL): " + str(len(seen_contracts)))
    return {"date": date_str, "total": total, "retained": matching, "excluded": excluded, "stale_gaps": stale_gaps, "duplicates": duplicates}


print("=" * 80)
print("TWO ADDITIONAL AUDITS -- January and March 2026")
print("=" * 80)

results = []
for date_str in SAMPLE_DATES:
    results.append(audit_day(date_str))
    print()

print("=" * 80)
print("COMPLETE FOUR-DAY COMPARISON (Dec-Feb-Mar window)")
print("=" * 80)
print("2025-12-22: 37.9% stale, max_gap=14d, duplicates=199")
print("2026-02-20: 0.0% stale, max_gap=0d, duplicates=0")
for r in results:
    pct = round(r["excluded"]/r["total"]*100, 1) if r["total"] else 0
    max_gap = max(r["stale_gaps"]) if r["stale_gaps"] else 0
    print(r["date"] + ": " + str(pct) + "% stale, max_gap=" + str(max_gap) + "d, duplicates=" + str(r["duplicates"]))
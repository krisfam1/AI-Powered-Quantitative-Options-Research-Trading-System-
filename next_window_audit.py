from dotenv import load_dotenv
load_dotenv()

"""
Audit of the NEXT chronological, non-overlapping replication window,
per the pre-specified rule: the 90-day block immediately preceding the
rejected March-April window, with zero gap. 2025-12-13 to 2026-03-13.

Two sample days, chosen for separation, BEFORE viewing any data:
- 2025-12-22 (near window start)
- 2026-02-20 (near window end)
"""

import os
import requests
from datetime import datetime, timedelta

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
SAMPLE_TICKER = "AAPL"
SAMPLE_DATES = ["2025-12-22", "2026-02-20"]


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
    print("  Raw records: " + str(total))
    print("  Retained: " + str(matching) + " (" + (str(round(matching/total*100,1)) if total else "0") + "%)")
    print("  Excluded/stale: " + str(excluded) + " (" + (str(round(excluded/total*100,1)) if total else "0") + "%)")
    if stale_gaps:
        print("  Gap distribution: min=" + str(min(stale_gaps)) + " max=" + str(max(stale_gaps)) + " avg=" + str(round(sum(stale_gaps)/len(stale_gaps),1)))
    print("  Missing OI: " + str(missing_oi) + " | Missing gamma: " + str(missing_gamma))
    print("  Duplicate contract entries: " + str(duplicates))
    print("  Unique contracts: " + str(len(seen_contracts)))
    return {"date": date_str, "total": total, "retained": matching, "excluded": excluded, "stale_gaps": stale_gaps, "duplicates": duplicates}


print("=" * 80)
print("NEXT CHRONOLOGICAL WINDOW AUDIT: 2025-12-13 to 2026-03-13")
print("=" * 80)

results = []
for date_str in SAMPLE_DATES:
    results.append(audit_day(date_str))
    print()

print("=" * 80)
print("COMPARISON TABLE")
print("=" * 80)
print("Original study (June-Sept): ~12.6% avg exclusion (reference)")
print("March-April window (REJECTED): Day1=27.5% stale, Day2=20.4% stale")
for r in results:
    pct = round(r["excluded"]/r["total"]*100, 1) if r["total"] else 0
    max_gap = max(r["stale_gaps"]) if r["stale_gaps"] else 0
    print("Dec-Feb window " + r["date"] + ": " + str(pct) + "% stale, max_gap=" + str(max_gap) + "d, duplicates=" + str(r["duplicates"]))
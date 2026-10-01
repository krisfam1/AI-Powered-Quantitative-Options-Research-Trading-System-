from dotenv import load_dotenv
load_dotenv()

"""
Targeted investigation of the tradetime/bid_date/ask_date discrepancy,
using real, direct evidence rather than assumption.

Tests the working hypothesis: tradetime may echo the requested query
filter date for illiquid/no-trade contracts, while bid_date/ask_date
reflect the contract's actual last real observation. Tested by:

1. Re-querying the SAME specific contract across several different
   requested dates -- if bid_date/ask_date stay frozen regardless of
   what date is requested, that's real, direct evidence of stale
   carry-forward data. If they shift with genuine new activity, that
   supports a different explanation.

2. Comparing a genuinely LIQUID, high-volume contract (where a REAL
   trade very likely occurred on the exact requested date) against the
   same illiquid contract -- tests whether the discrepancy is specific
   to illiquid/no-trade contracts or systemic across the whole dataset.

3. Inspecting the 94 duplicate contract IDs directly to see what
   actually differs between them.

Also includes the corrected query (0-45 DTE) for the next real test,
NOT run automatically here -- printed for review first.
"""

import os
import requests
from datetime import datetime, timedelta

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"


def fetch_chain(ticker, date_str, extra_filters=None):
    params = {
        "filter[underlying_symbol]": ticker,
        "filter[tradetime_from]": date_str,
        "filter[tradetime_to]": date_str,
        "api_token": EODHD_API_TOKEN,
        "page[limit]": 1000,
    }
    if extra_filters:
        params.update(extra_filters)
    resp = requests.get(BASE_URL, params=params)
    resp.raise_for_status()
    return resp.json().get("data", [])


print("=" * 80)
print("TEST 1: Re-query the SAME illiquid contract across several nearby dates")
print("=" * 80)
target_contract = "AAPL281215C00010000"
for date_str in ["2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17"]:
    records = fetch_chain("AAPL", date_str)
    match = next((r for r in records if r["attributes"]["contract"] == target_contract), None)
    if match:
        a = match["attributes"]
        print("Requested date=" + date_str + " -> tradetime=" + str(a.get("tradetime")) + " bid_date=" + str(a.get("bid_date")) + " ask_date=" + str(a.get("ask_date")) + " volume=" + str(a.get("volume")) + " OI=" + str(a.get("open_interest")))
    else:
        print("Requested date=" + date_str + " -> contract not found in this day's response")

print("\n" + "=" * 80)
print("TEST 2: Compare against a LIQUID, high-volume contract for the same date")
print("=" * 80)
records = fetch_chain("AAPL", "2026-07-15")
liquid_candidates = sorted(records, key=lambda r: r["attributes"].get("volume", 0) or 0, reverse=True)[:5]
for r in liquid_candidates:
    a = r["attributes"]
    print("  " + str(a.get("contract")) + ": volume=" + str(a.get("volume")) + " tradetime=" + str(a.get("tradetime")) + " bid_date=" + str(a.get("bid_date")) + " ask_date=" + str(a.get("ask_date")) + " strike=" + str(a.get("strike")) + " exp=" + str(a.get("exp_date")))

print("\n" + "=" * 80)
print("TEST 3: Inspect the duplicate contract IDs directly")
print("=" * 80)
seen = {}
duplicates_detail = []
for r in records:
    c = r["attributes"].get("contract")
    if c in seen:
        duplicates_detail.append((seen[c], r))
    else:
        seen[c] = r

print("Found " + str(len(duplicates_detail)) + " duplicate pairs. Showing first 3, full comparison:")
for original, dup in duplicates_detail[:3]:
    oa, da = original["attributes"], dup["attributes"]
    print("\n  Contract: " + str(oa.get("contract")))
    for field in ["tradetime", "bid_date", "ask_date", "bid", "ask", "open_interest", "gamma", "volume"]:
        same = "SAME" if oa.get(field) == da.get(field) else "DIFFERENT"
        print("    " + field + ": " + str(oa.get(field)) + " vs " + str(da.get(field)) + " -- " + same)

print("\n" + "=" * 80)
print("CORRECTED QUERY for next real test (0-45 DTE) -- printed for review, NOT run here")
print("=" * 80)
print("filter[underlying_symbol]=AAPL")
print("filter[tradetime_from]=2026-07-15")
print("filter[tradetime_to]=2026-07-15")
print("filter[exp_date_from]=2026-07-15")
print("filter[exp_date_to]=2026-08-29  (45 calendar days out)")
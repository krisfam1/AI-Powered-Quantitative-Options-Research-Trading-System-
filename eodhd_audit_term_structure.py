from dotenv import load_dotenv
load_dotenv()

"""
EODHD Audit 1 -- TERM STRUCTURE COVERAGE. Pure data-capability check.
No trading signal, no threshold search, no significance test.
"""

import os
import requests
from datetime import datetime, timedelta
from collections import defaultdict

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"

TICKER = "AAPL"
DATE = "2026-07-15"
target_date = datetime.strptime(DATE, "%Y-%m-%d").date()

print("=" * 100)
print("AUDIT 1: TERM STRUCTURE COVERAGE -- " + TICKER + " " + DATE)
print("=" * 100)

params = {
    "filter[underlying_symbol]": TICKER,
    "filter[tradetime_from]": DATE,
    "filter[tradetime_to]": DATE,
    "filter[exp_date_from]": (target_date + timedelta(days=5)).isoformat(),
    "filter[exp_date_to]": (target_date + timedelta(days=65)).isoformat(),
    "api_token": EODHD_API_TOKEN,
    "page[limit]": 1000,
}
resp = requests.get(BASE_URL, params=params, timeout=60)
resp.raise_for_status()
data = resp.json()
records = [r["attributes"] for r in data.get("data", []) if r["attributes"].get("type") == "call"]
print("Total call records retrieved (5-65 DTE): " + str(len(records)))

buckets = {"7-16": (7,16), "17-30": (17,30), "31-60": (31,60)}
expirations_by_bucket = defaultdict(set)
records_by_exp = defaultdict(list)

for r in records:
    dte = r.get("dte")
    exp = r.get("exp_date")
    if dte is None or exp is None:
        continue
    records_by_exp[exp].append(r)
    for label, (lo, hi) in buckets.items():
        if lo <= dte <= hi:
            expirations_by_bucket[label].add(exp)

print("\n" + "=" * 100)
print("EXPIRATIONS AVAILABLE PER DTE BUCKET (this ticker/date)")
print("=" * 100)
for label in buckets:
    exps = sorted(expirations_by_bucket[label])
    print("  " + label + " DTE: " + str(len(exps)) + " expiration(s) -> " + str(exps))

print("\n" + "=" * 100)
print("PER-EXPIRATION: CONTRACT COUNT, STRIKE RANGE, IV AT ~ATM")
print("=" * 100)
for exp in sorted(records_by_exp.keys()):
    recs = records_by_exp[exp]
    strikes = sorted(set(r["strike"] for r in recs))
    ivs = [r["volatility"] for r in recs if r.get("volatility") is not None]
    dte_here = recs[0]["dte"]
    print("  " + exp + " (dte=" + str(dte_here) + "): n=" + str(len(recs)) + " strikes=" + str(len(strikes)) + " (" + str(min(strikes)) + "-" + str(max(strikes)) + ") IV_range=" + (str(round(min(ivs),3)) + "-" + str(round(max(ivs),3)) if ivs else "N/A"))

print("\n" + "=" * 100)
print("CROSS-EXPIRATION MONEYNESS MATCHING CHECK -- can we align comparable strikes across expirations?")
print("=" * 100)
sorted_exps = sorted(records_by_exp.keys(), key=lambda e: records_by_exp[e][0]["dte"])
if len(sorted_exps) >= 2:
    exp_near, exp_far = sorted_exps[0], sorted_exps[1]
    strikes_near = set(r["strike"] for r in records_by_exp[exp_near])
    strikes_far = set(r["strike"] for r in records_by_exp[exp_far])
    common_strikes = strikes_near & strikes_far
    print("Near expiration: " + exp_near + " (" + str(len(strikes_near)) + " strikes)")
    print("Far expiration: " + exp_far + " (" + str(len(strikes_far)) + " strikes)")
    print("Common (identical) strikes across both: " + str(len(common_strikes)))
    if common_strikes:
        sample_strike = sorted(common_strikes)[len(common_strikes)//2]
        iv_near = [r["volatility"] for r in records_by_exp[exp_near] if r["strike"] == sample_strike]
        iv_far = [r["volatility"] for r in records_by_exp[exp_far] if r["strike"] == sample_strike]
        print("Sample matched strike " + str(sample_strike) + ": near_IV=" + str(iv_near) + " far_IV=" + str(iv_far))
        print("-> Term-structure slope (far_IV - near_IV) IS constructible at matched strikes, without fabrication.")
    else:
        print("-> NO identical strikes shared between these two expirations -- term structure would require")
        print("   INTERPOLATION across strikes to compare, which is a real, additional methodological step,")
        print("   not fabrication, but not a free lunch either.")
else:
    print("Insufficient expirations found to test cross-expiration matching.")

print("\nAUDIT 1 COMPLETE. No signal tested, no threshold searched.")
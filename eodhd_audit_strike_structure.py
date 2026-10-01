from dotenv import load_dotenv
load_dotenv()

"""
EODHD Audit 2 -- FULL CHAIN / STRIKE STRUCTURE COVERAGE. Pure data-
capability check for a single expiration. No trading signal, no
threshold search, no significance test.
"""

import os
import requests
from datetime import datetime, timedelta

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"

TICKER = "AAPL"
DATE = "2026-07-15"
target_date = datetime.strptime(DATE, "%Y-%m-%d").date()

print("=" * 100)
print("AUDIT 2: FULL CHAIN / STRIKE STRUCTURE -- " + TICKER + " " + DATE)
print("=" * 100)

params = {
    "filter[underlying_symbol]": TICKER,
    "filter[tradetime_from]": DATE,
    "filter[tradetime_to]": DATE,
    "filter[exp_date_from]": (target_date + timedelta(days=12)).isoformat(),
    "filter[exp_date_to]": (target_date + timedelta(days=16)).isoformat(),
    "api_token": EODHD_API_TOKEN,
    "page[limit]": 1000,
}
resp = requests.get(BASE_URL, params=params, timeout=60)
resp.raise_for_status()
data = resp.json()
records = [r["attributes"] for r in data.get("data", [])]
print("Total records (calls+puts, single near-14-DTE expiration): " + str(len(records)))

if not records:
    print("NO RECORDS RETURNED.")
else:
    exp_date = records[0]["exp_date"]
    print("Expiration used: " + exp_date + " (dte=" + str(records[0]["dte"]) + ")")

    calls = [r for r in records if r["type"] == "call"]
    puts = [r for r in records if r["type"] == "put"]
    print("Calls: " + str(len(calls)) + " | Puts: " + str(len(puts)))

    strikes_calls = sorted(set(r["strike"] for r in calls))
    strikes_puts = sorted(set(r["strike"] for r in puts))
    print("\nCall strike range: " + str(min(strikes_calls)) + " - " + str(max(strikes_calls)) + " (" + str(len(strikes_calls)) + " unique strikes)")
    print("Put strike range: " + str(min(strikes_puts)) + " - " + str(max(strikes_puts)) + " (" + str(len(strikes_puts)) + " unique strikes)")
    print("Call/Put strike sets identical: " + str(set(strikes_calls) == set(strikes_puts)))

    atm_candidates = sorted(records, key=lambda r: abs(r.get("moneyness", 999) - 1.0))
    approx_underlying = atm_candidates[0]["strike"] / atm_candidates[0]["moneyness"] if atm_candidates and atm_candidates[0].get("moneyness") else None
    print("\nApprox underlying price (derived from moneyness): " + str(round(approx_underlying,2) if approx_underlying else "N/A"))

    print("\n" + "=" * 100)
    print("COVERAGE BY FIELD, ACROSS THE FULL STRIKE RANGE")
    print("=" * 100)
    fields_to_check = ["bid", "ask", "open_interest", "volume", "gamma", "delta"]
    for f in fields_to_check:
        vals = [r.get(f) for r in records]
        non_null = [v for v in vals if v is not None]
        zero = [v for v in non_null if v == 0]
        print("  " + f + ": null=" + str(round((len(vals)-len(non_null))/len(vals)*100,1)) + "% zero=" + str(round(len(zero)/len(vals)*100,1) if vals else 0) + "%")

    print("\n" + "=" * 100)
    print("OI / GAMMA CONCENTRATION -- CONSTRUCTIBILITY CHECK (descriptive, not a signal)")
    print("=" * 100)
    oi_by_strike = {}
    gamma_by_strike = {}
    for r in calls:
        oi_by_strike[r["strike"]] = r.get("open_interest", 0)
        gamma_by_strike[r["strike"]] = r.get("gamma", 0)

    max_oi_strike = max(oi_by_strike, key=oi_by_strike.get) if oi_by_strike else None
    max_gamma_strike = max(gamma_by_strike, key=lambda k: (gamma_by_strike[k] or 0) * (oi_by_strike.get(k,0) or 0)) if gamma_by_strike else None
    print("Strike with max call OI: " + str(max_oi_strike) + " (OI=" + str(oi_by_strike.get(max_oi_strike)) + ")")
    print("Strike with max (gamma * OI) proxy: " + str(max_gamma_strike))
    print("-> Both OI-concentration and gamma*OI-weighted 'wall' style features appear TECHNICALLY")
    print("   constructible from this real data, without fabrication -- this is a capability")
    print("   confirmation only, NOT a claim these features predict anything.")

    print("\n" + "=" * 100)
    print("CALL/PUT POSITIONING -- CONSTRUCTIBILITY CHECK")
    print("=" * 100)
    total_call_oi = sum(r.get("open_interest",0) or 0 for r in calls)
    total_put_oi = sum(r.get("open_interest",0) or 0 for r in puts)
    print("Total call OI: " + str(total_call_oi) + " | Total put OI: " + str(total_put_oi))
    if total_put_oi > 0:
        print("Call/Put OI ratio: " + str(round(total_call_oi/total_put_oi,3)) + " -- constructible from real data.")
    else:
        print("Put OI is zero -- ratio not computable for this specific sample.")

print("\nAUDIT 2 COMPLETE. No signal tested, no threshold searched.")
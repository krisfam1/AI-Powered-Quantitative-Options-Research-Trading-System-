from dotenv import load_dotenv
load_dotenv()

"""
EODHD Historical Coverage Audit. Samples real trading days spread
across the full clean window (weekly-ish, not exhaustive daily --
explicitly disclosed) for all 7 tickers, checking field coverage,
zero rates, and contract/expiration availability CONSISTENCY over
time and across tickers. No predictive testing. No signal search.
"""

import os
import requests
from datetime import datetime, timedelta
from collections import defaultdict

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"

TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR", "SPY"]
WINDOW_START = datetime(2026, 6, 11)
WINDOW_END = datetime(2026, 9, 9)

sample_dates = []
d = WINDOW_START
while d <= WINDOW_END:
    if d.weekday() < 5:
        sample_dates.append(d.date())
    d += timedelta(days=7)
print("Sampled dates (weekly, weekdays only): " + str(len(sample_dates)))
print([d.isoformat() for d in sample_dates])

FIELDS = ["volatility", "delta", "gamma", "theta", "vega", "rho", "bid", "ask", "volume", "open_interest"]

results = defaultdict(lambda: {"dates_with_data": 0, "dates_no_data": 0, "total_contracts": 0,
                                "field_null_counts": defaultdict(int), "field_zero_counts": defaultdict(int),
                                "field_total_counts": defaultdict(int), "expirations_seen": set(), "strikes_seen": set()})

for ticker in TICKERS:
    print("\nAuditing " + ticker + "...")
    for date in sample_dates:
        exp_from = (date + timedelta(days=12)).isoformat()
        exp_to = (date + timedelta(days=16)).isoformat()
        params = {
            "filter[underlying_symbol]": ticker,
            "filter[tradetime_from]": date.isoformat(),
            "filter[tradetime_to]": date.isoformat(),
            "filter[exp_date_from]": exp_from,
            "filter[exp_date_to]": exp_to,
            "api_token": EODHD_API_TOKEN,
            "page[limit]": 1000,
        }
        try:
            resp = requests.get(BASE_URL, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            records = [r["attributes"] for r in data.get("data", [])]
        except Exception as e:
            records = []

        r = results[ticker]
        if records:
            r["dates_with_data"] += 1
            r["total_contracts"] += len(records)
            for rec in records:
                r["expirations_seen"].add(rec.get("exp_date"))
                r["strikes_seen"].add(rec.get("strike"))
                for f in FIELDS:
                    v = rec.get(f)
                    r["field_total_counts"][f] += 1
                    if v is None:
                        r["field_null_counts"][f] += 1
                    elif v == 0:
                        r["field_zero_counts"][f] += 1
        else:
            r["dates_no_data"] += 1

print("\n" + "=" * 100)
print("HISTORICAL COVERAGE AUDIT REPORT (sampled, weekly cadence)")
print("=" * 100)

for ticker in TICKERS:
    r = results[ticker]
    total_dates = r["dates_with_data"] + r["dates_no_data"]
    print("\n--- " + ticker + " ---")
    print("  Date coverage: " + str(r["dates_with_data"]) + " / " + str(total_dates) + " sampled dates had data")
    print("  Total contracts observed: " + str(r["total_contracts"]))
    print("  Distinct expirations seen: " + str(len(r["expirations_seen"])))
    print("  Distinct strikes seen: " + str(len(r["strikes_seen"])))
    print("  Field coverage (null% / zero%):")
    for f in FIELDS:
        total = r["field_total_counts"][f]
        if total == 0:
            print("    " + f + ": NO DATA")
            continue
        null_pct = r["field_null_counts"][f] / total * 100
        zero_pct = r["field_zero_counts"][f] / total * 100
        print("    " + f + ": null=" + str(round(null_pct,1)) + "% zero=" + str(round(zero_pct,1)) + "%")

print("\n" + "=" * 100)
print("CROSS-TICKER CONSISTENCY SUMMARY")
print("=" * 100)
for f in FIELDS:
    print("\n  " + f + " null rate by ticker:")
    for ticker in TICKERS:
        r = results[ticker]
        total = r["field_total_counts"][f]
        null_pct = (r["field_null_counts"][f] / total * 100) if total else None
        print("    " + ticker + ": " + (str(round(null_pct,1)) + "%" if null_pct is not None else "NO DATA"))

print("\nHISTORICAL COVERAGE AUDIT COMPLETE. No predictive testing performed. No signal searched.")
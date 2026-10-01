from dotenv import load_dotenv
load_dotenv()

"""
Six-ticker data-quality audit for the next chronological window:
2025-09-14 to 2025-12-13. Two dates selected BEFORE viewing any data:
- 2025-09-24 (ordinary late-September day, clear of Labor Day)
- 2025-11-12 (ordinary mid-November day, clear of Thanksgiving)

First audit in this whole investigation to use all six study tickers,
not just AAPL.
"""

import os
import requests
from datetime import datetime, timedelta

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
SAMPLE_DATES = ["2025-09-24", "2025-11-12"]


def audit_ticker_day(ticker, date_str):
    obs_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    params = {
        "filter[underlying_symbol]": ticker,
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

    return {
        "ticker": ticker, "date": date_str, "total": total, "retained": matching,
        "excluded": total - matching, "stale_gaps": stale_gaps,
        "missing_oi": missing_oi, "missing_gamma": missing_gamma,
        "duplicates": duplicates, "unique_contracts": len(seen_contracts),
    }


print("=" * 90)
print("SEPTEMBER-DECEMBER 2025 WINDOW AUDIT -- all six tickers")
print("=" * 90)

all_results = []
for date_str in SAMPLE_DATES:
    print("\n--- " + date_str + " ---")
    for ticker in TICKERS:
        r = audit_ticker_day(ticker, date_str)
        all_results.append(r)
        pct = round(r["excluded"] / r["total"] * 100, 1) if r["total"] else 0
        max_gap = max(r["stale_gaps"]) if r["stale_gaps"] else 0
        print("  " + ticker + ": raw=" + str(r["total"]) + " retained=" + str(r["retained"]) + " stale%=" + str(pct) + " max_gap=" + str(max_gap) + " dup=" + str(r["duplicates"]) + " missing_oi=" + str(r["missing_oi"]) + " missing_gamma=" + str(r["missing_gamma"]))

print("\n" + "=" * 90)
print("PER-DATE AGGREGATE (all 6 tickers combined)")
print("=" * 90)
for date_str in SAMPLE_DATES:
    day_results = [r for r in all_results if r["date"] == date_str]
    total_raw = sum(r["total"] for r in day_results)
    total_retained = sum(r["retained"] for r in day_results)
    total_excluded = sum(r["excluded"] for r in day_results)
    total_dup = sum(r["duplicates"] for r in day_results)
    all_gaps = [g for r in day_results for g in r["stale_gaps"]]
    pct = round(total_excluded / total_raw * 100, 1) if total_raw else 0
    max_gap = max(all_gaps) if all_gaps else 0
    print(date_str + ": raw=" + str(total_raw) + " retained=" + str(total_retained) + " stale%=" + str(pct) + " max_gap=" + str(max_gap) + " duplicates=" + str(total_dup))

print("\n" + "=" * 90)
print("FULL COMPARISON ACROSS ALL AUDITED DATES")
print("=" * 90)
print("Original study (June-Sept 2026): ~12.6% avg exclusion (reference)")
print("2025-12-22: 37.9% stale, 14d max gap, 199 dup (AAPL only)")
print("2026-01-14: 26.0% stale, 20d max gap, 122 dup (AAPL only)")
print("2026-02-20: 0.0% stale, 0d max gap, 0 dup (AAPL only)")
print("2026-03-11: 39.9% stale, 33d max gap, 196 dup (AAPL only)")
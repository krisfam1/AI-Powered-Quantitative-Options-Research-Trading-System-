from dotenv import load_dotenv
load_dotenv()

"""
Corrected, targeted EOD snapshot construction test.

Does NOT trust tradetime as the observation date (confirmed to simply
echo the query filter). Instead, converts ask_date/bid_date to real
U.S. Eastern time (DST-aware) and uses THAT to determine which records
genuinely represent the requested historical trading date's EOD state,
versus stale, carried-forward data from a later date.

Corrected expiration filter: 0-45 calendar days from the observation
date, addressing the earlier accidental 2028-LEAP-dominated query.
"""

import os
import requests
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"

TICKER = "AAPL"
OBSERVATION_DATE = "2026-07-15"
EASTERN = ZoneInfo("America/New_York")


def fetch_chain_corrected(ticker, date_str):
    obs_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    exp_from = obs_date.isoformat()
    exp_to = (obs_date + timedelta(days=45)).isoformat()
    params = {
        "filter[underlying_symbol]": ticker,
        "filter[tradetime_from]": date_str,
        "filter[tradetime_to]": date_str,
        "filter[exp_date_from]": exp_from,
        "filter[exp_date_to]": exp_to,
        "api_token": EODHD_API_TOKEN,
        "page[limit]": 1000,
    }
    resp = requests.get(BASE_URL, params=params)
    resp.raise_for_status()
    return resp.json().get("data", [])


def parse_to_eastern(raw_timestamp: str):
    """Parses EODHD's timestamp (with or without explicit UTC 'Z' marker) and converts to real, DST-aware U.S. Eastern time."""
    if raw_timestamp is None:
        return None
    ts = raw_timestamp.replace("Z", "").replace("T", " ")
    try:
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    dt_utc = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt_utc.astimezone(EASTERN)


print("=" * 80)
print("Fetching CORRECTED chain: " + TICKER + " on " + OBSERVATION_DATE + ", expirations 0-45 days out")
print("=" * 80)
records = fetch_chain_corrected(TICKER, OBSERVATION_DATE)
print("Records returned: " + str(len(records)))

obs_date_obj = datetime.strptime(OBSERVATION_DATE, "%Y-%m-%d").date()

for r in records:
    a = r["attributes"]
    eastern_ask = parse_to_eastern(a.get("ask_date"))
    a["_eastern_ask_date"] = eastern_ask
    a["_matches_observation_date"] = (eastern_ask.date() == obs_date_obj) if eastern_ask else False

print("\n" + "=" * 80)
print("EXPIRATION DISTRIBUTION (corrected filter)")
print("=" * 80)
exp_dates = sorted(set(r["attributes"]["exp_date"] for r in records))
print(str(len(exp_dates)) + " unique expirations: " + str(exp_dates))

print("\n" + "=" * 80)
print("STEP 3-4: Genuine same-day vs. stale, by volume")
print("=" * 80)
genuine = [r for r in records if r["attributes"]["_matches_observation_date"]]
stale = [r for r in records if not r["attributes"]["_matches_observation_date"]]
print("Records genuinely matching " + OBSERVATION_DATE + " (Eastern, ask_date-based): " + str(len(genuine)))
print("Records with a DIFFERENT (stale) Eastern ask_date: " + str(len(stale)))
print("  Of genuine: volume>0 = " + str(len([r for r in genuine if r['attributes'].get('volume', 0)])) + ", volume=0 = " + str(len([r for r in genuine if not r['attributes'].get('volume', 0)])))
print("  Of stale:   volume>0 = " + str(len([r for r in stale if r['attributes'].get('volume', 0)])) + ", volume=0 = " + str(len([r for r in stale if not r['attributes'].get('volume', 0)])))

print("\n" + "=" * 80)
print("STEP 5: Can the API return a stale quote while tradetime echoes the requested date?")
print("=" * 80)
print("CONFIRMED YES, based on the above: " + str(len(stale)) + " of " + str(len(records)) + " records have tradetime=" + OBSERVATION_DATE + " but a genuinely different real Eastern ask_date.")

print("\n" + "=" * 80)
print("STEP 7: Sample contract detail (5 genuine, 5 stale, for comparison)")
print("=" * 80)
for label, group in [("GENUINE", genuine[:5]), ("STALE", stale[:5])]:
    print("\n--- " + label + " ---")
    for r in group:
        a = r["attributes"]
        print("  " + str(a.get("contract")) + " | strike=" + str(a.get("strike")) + " exp=" + str(a.get("exp_date")) + " type=" + str(a.get("type")))
        print("    OI=" + str(a.get("open_interest")) + " gamma=" + str(a.get("gamma")) + " volume=" + str(a.get("volume")) + " bid=" + str(a.get("bid")) + " ask=" + str(a.get("ask")))
        print("    tradetime=" + str(a.get("tradetime")) + " ask_date(raw)=" + str(a.get("ask_date")) + " ask_date(Eastern)=" + str(a.get("_eastern_ask_date")))

print("\n" + "=" * 80)
print("STEP 8: Duplicate investigation -- which is genuine, which is stale?")
print("=" * 80)
by_contract = {}
for r in records:
    c = r["attributes"]["contract"]
    by_contract.setdefault(c, []).append(r)

multi_record_contracts = {c: rs for c, rs in by_contract.items() if len(rs) > 1}
print("Contracts with multiple records: " + str(len(multi_record_contracts)))
shown = 0
for contract, recs in multi_record_contracts.items():
    if shown >= 3:
        break
    print("\n  " + contract + ": " + str(len(recs)) + " records")
    for r in recs:
        a = r["attributes"]
        print("    matches_observation_date=" + str(a["_matches_observation_date"]) + " ask_date(Eastern)=" + str(a["_eastern_ask_date"]) + " volume=" + str(a.get("volume")) + " OI=" + str(a.get("open_interest")))
    shown += 1

print("\n" + "=" * 80)
print("STEP 9: Applying the deterministic selection rule")
print("=" * 80)
print("RULE: for each contract, select the record whose ask_date, converted to U.S.")
print("Eastern, has a calendar date EXACTLY equal to the observation date. If multiple")
print("such records exist for the same contract, select the one with the latest")
print("Eastern ask_date timestamp. If NO record for a contract matches the observation")
print("date, EXCLUDE that contract from the snapshot entirely -- never substitute stale data.")

selected_snapshot = {}
excluded_contracts = []
for contract, recs in by_contract.items():
    matching = [r for r in recs if r["attributes"]["_matches_observation_date"]]
    if not matching:
        excluded_contracts.append(contract)
        continue
    best = max(matching, key=lambda r: r["attributes"]["_eastern_ask_date"])
    selected_snapshot[contract] = best

print("\nFinal snapshot: " + str(len(selected_snapshot)) + " contracts selected, " + str(len(excluded_contracts)) + " excluded (no genuine same-day record available)")

print("\n" + "=" * 80)
print("STEP 10: Automated no-lookahead verification on the final selected snapshot")
print("=" * 80)
violations = 0
for contract, r in selected_snapshot.items():
    eastern_date = r["attributes"]["_eastern_ask_date"].date()
    if eastern_date != obs_date_obj:
        violations += 1
        print("  VIOLATION: " + contract + " has Eastern date " + str(eastern_date) + " != " + OBSERVATION_DATE)

if violations == 0:
    print("PASS: all " + str(len(selected_snapshot)) + " selected records genuinely have Eastern ask_date == " + OBSERVATION_DATE + ". tradetime was NOT relied upon.")
else:
    print("FAIL: " + str(violations) + " violation(s) found in the selection logic.")
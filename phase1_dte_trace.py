from dotenv import load_dotenv
load_dotenv()

"""
Phase 1: traces the FULL candidate contract list (not just the one
selected) for the 4 DTE-mismatch trades, to determine exactly why the
audit script's own contract-matching heuristic picked a 21-22 DTE
contract over closer alternatives.

IMPORTANT CLARIFICATION: this investigates the AUDIT SCRIPT's own
nearest-neighbor matching logic (fetch_real_contract_near_strike),
built specifically for this validation exercise. It is NOT the
production strategy's actual DTE-targeting/contract-selection system,
which uses a separate, already-validated mechanism
(find_strike_for_target_delta) elsewhere in the codebase.
"""

import os
import requests
from datetime import datetime, timezone, timedelta

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"

TARGET_TRADES = [
    ("MSTR", "2026-06-18", 114.33),
    ("TSLA", "2026-06-18", 406.86),
    ("AMD", "2026-09-04", 506.43),
    ("TSLA", "2026-09-04", 372.44),
]


def fetch_all_candidates(ticker, date_str, target_strike, option_type="call", target_dte=14):
    obs_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    params = {
        "filter[underlying_symbol]": ticker, "filter[tradetime_from]": date_str, "filter[tradetime_to]": date_str,
        "filter[exp_date_from]": obs_date.isoformat(), "filter[exp_date_to]": (obs_date + timedelta(days=45)).isoformat(),
        "api_token": EODHD_API_TOKEN, "page[limit]": 1000,
    }
    resp = requests.get(BASE_URL, params=params, timeout=60)
    resp.raise_for_status()
    records = resp.json().get("data", [])
    valid = []
    for r in records:
        a = r.get("attributes", {})
        if a.get("type") != option_type:
            continue
        parts = r.get("id", "").split("-", 1)
        if len(parts) != 2:
            continue
        try:
            id_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
        except ValueError:
            continue
        if id_date != obs_date or a.get("bid") is None or a.get("ask") is None:
            continue
        exp_date = datetime.strptime(a["exp_date"], "%Y-%m-%d").date()
        a["_actual_dte"] = (exp_date - obs_date).days
        a["_score"] = abs(a["strike"] - target_strike) / target_strike + (abs(a["_actual_dte"] - target_dte) / target_dte) * 0.5
        valid.append(a)
    return sorted(valid, key=lambda a: a["_score"])


for ticker, date_str, target_strike in TARGET_TRADES:
    print("=" * 100)
    print(ticker + " " + date_str + " -- target_strike=" + str(target_strike) + " target_dte=14")
    print("=" * 100)

    candidates = fetch_all_candidates(ticker, date_str, target_strike)
    eligible_expirations = sorted(set(c["exp_date"] for c in candidates))
    print("Eligible expirations available (0-45 DTE window): " + str(eligible_expirations))
    dtes_available = sorted(set(c["_actual_dte"] for c in candidates))
    print("Actual DTEs available on this date: " + str(dtes_available))

    print("\nTop 5 candidates by combined score (strike-distance + 0.5x DTE-distance):")
    for c in candidates[:5]:
        print("  strike=" + str(c["strike"]) + " dte=" + str(c["_actual_dte"]) + " score=" + str(round(c["_score"], 4)) + (" <== SELECTED" if c is candidates[0] else ""))

    near_14 = [c for c in candidates if abs(c["_actual_dte"] - 14) <= 2]
    if near_14:
        best_near_14 = min(near_14, key=lambda c: abs(c["strike"] - target_strike))
        print("\nBest available candidate within 2 days of 14 DTE: strike=" + str(best_near_14["strike"]) + " dte=" + str(best_near_14["_actual_dte"]) + " score=" + str(round(best_near_14["_score"], 4)))
        print("(This candidate was NOT selected -- the winning candidate's score was lower, meaning strike proximity outweighed the DTE penalty in the 0.5x-weighted formula)")
    else:
        print("\nNo real contract available within 2 days of the 14-DTE target on this date -- the nearest real expiration was genuinely further away.")

    print()

print("PHASE 1 TRACE COMPLETE.")
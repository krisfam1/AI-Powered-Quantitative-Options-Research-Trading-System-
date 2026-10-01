from dotenv import load_dotenv
load_dotenv()

"""
Historical EOD Options Pricing Validation -- Phase 7 deliverable: small
audit of ~15 representative trades, comparing synthetic Black-Scholes
prices against real EODHD historical EOD bid/ask/midpoint for the
SAME signals.

LIMITATION, stated per instruction: our strategy generates signals/exits
from 5-minute bars; available historical option quotes are EOD-only.
This CANNOT reconstruct the actual price at the precise intraday
signal/exit timestamp -- it validates whether synthetic PRICING
MAGNITUDES are reasonably consistent with real historical EOD market
data, not precise intraday execution.

Trade selection: every 2nd trade from the already-validated, real,
deterministic 30-trade AAPL calls-only reconciliation dataset --
NOT hand-picked, preserves natural spread across dates/outcomes.
"""

import os
import requests
from datetime import datetime, timezone, timedelta
from portfolio_backtest import run_portfolio_backtest

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)


def fetch_real_contract_near_strike(ticker, date_str, target_strike, option_type, target_dte=14):
    """Fetches the real EODHD chain for a date, applies the validated
    record-ID snapshot-date selection rule, and returns the real
    contract closest to BOTH target_strike AND target_dte -- matching
    strike alone (the original, flawed version) could select a
    real contract with a wildly different expiration, comparing
    apples to oranges on time value."""
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
    resp = requests.get(BASE_URL, params=params, timeout=60)
    resp.raise_for_status()
    records = resp.json().get("data", [])

    valid = []
    for r in records:
        a = r.get("attributes", {})
        if a.get("type") != option_type:
            continue
        record_id = r.get("id", "")
        parts = record_id.split("-", 1)
        if len(parts) != 2:
            continue
        try:
            id_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
        except ValueError:
            continue
        if id_date != obs_date:
            continue  # exclude stale, per validated rule
        if a.get("bid") is None or a.get("ask") is None:
            continue
        exp_date = datetime.strptime(a["exp_date"], "%Y-%m-%d").date()
        actual_dte = (exp_date - obs_date).days
        a["_actual_dte"] = actual_dte
        valid.append(a)

    if not valid:
        return None

    def score(a):
        strike_diff_pct = abs(a["strike"] - target_strike) / target_strike
        dte_diff = abs(a["_actual_dte"] - target_dte)
        return strike_diff_pct + (dte_diff / target_dte) * 0.5  # weighted combined distance

    return min(valid, key=score)


def fetch_specific_contract(ticker, date_str, contract_symbol, exp_date_str):
    """Fetches the real EOD record for a SPECIFIC, already-identified
    contract symbol on a given date -- used for exit pricing, per Phase 5's
    explicit requirement to follow the exact same frozen contract, not
    re-run a fresh nearest-match search."""
    obs_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    params = {
        "filter[underlying_symbol]": ticker,
        "filter[tradetime_from]": date_str,
        "filter[tradetime_to]": date_str,
        "filter[exp_date_from]": exp_date_str,
        "filter[exp_date_to]": exp_date_str,
        "api_token": EODHD_API_TOKEN,
        "page[limit]": 1000,
    }
    resp = requests.get(BASE_URL, params=params, timeout=60)
    resp.raise_for_status()
    records = resp.json().get("data", [])

    for r in records:
        a = r.get("attributes", {})
        if a.get("contract") != contract_symbol:
            continue
        record_id = r.get("id", "")
        parts = record_id.split("-", 1)
        if len(parts) != 2:
            continue
        try:
            id_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
        except ValueError:
            continue
        if id_date != obs_date:
            continue
        if a.get("bid") is None or a.get("ask") is None:
            continue
        return a
    return None
result = run_portfolio_backtest(["AAPL"], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call")
all_trades = sorted(result["closed_trades"], key=lambda t: str(t["entry_date"]))
print("Total synthetic trades: " + str(len(all_trades)))

sample = all_trades[::2]  # every 2nd trade -- simple, non-cherry-picked selection
print("Selected for audit (every 2nd trade): " + str(len(sample)) + " trades\n")

print("=" * 100)
print("PER-TRADE COMPARISON: Signal -> Synthetic -> Real Historical Contract -> Real EOD Quote")
print("=" * 100)

comparison_data = []

for t in sample:
    entry_date_str = str(t["entry_date"])
    exit_date_str = str(t["exit_date"])
    target_strike = t["strike"]

    print("\n--- Entry " + entry_date_str + " -> Exit " + exit_date_str + " (synthetic strike=" + str(target_strike) + ") ---")
    print("Synthetic entry premium: $" + str(round(t["entry_premium"], 3)) + " | Synthetic exit premium: $" + str(round(t["exit_premium"], 3)))

    real_entry = fetch_real_contract_near_strike("AAPL", entry_date_str, target_strike, "call")
    if real_entry is None:
        print("NO REAL CONTRACT FOUND for entry date -- excluding this trade from comparison, not substituting.")
        continue

    real_entry_mid = real_entry.get("midpoint")
    entry_pct_diff = (t["entry_premium"] - real_entry_mid) / real_entry_mid * 100 if real_entry_mid else None
    print("Real contract: " + real_entry.get("contract") + " strike=" + str(real_entry["strike"]) + " exp=" + real_entry.get("exp_date") + " actual_dte=" + str(real_entry.get("_actual_dte")))
    print("Real entry bid=$" + str(real_entry.get("bid")) + " ask=$" + str(real_entry.get("ask")) + " mid=$" + str(real_entry_mid))
    print("Entry synthetic vs real midpoint: " + (str(round(entry_pct_diff, 1)) + "%" if entry_pct_diff is not None else "N/A"))
    in_bid_ask_entry = (real_entry.get("bid") <= t["entry_premium"] <= real_entry.get("ask")) if real_entry.get("bid") is not None and real_entry.get("ask") is not None else None
    print("Synthetic entry price falls inside real bid/ask range: " + str(in_bid_ask_entry))

    real_exit = fetch_specific_contract("AAPL", exit_date_str, real_entry["contract"], real_entry["exp_date"])
    real_exit_mid = None
    exit_pct_diff = None
    in_bid_ask_exit = None
    if real_exit is None:
        print("SAME CONTRACT COULD NOT BE VERIFIED on exit date -- exit comparison unavailable for this trade.")
    else:
        real_exit_mid = real_exit.get("midpoint")
        exit_pct_diff = (t["exit_premium"] - real_exit_mid) / real_exit_mid * 100 if real_exit_mid else None
        print("Real exit bid=$" + str(real_exit.get("bid")) + " ask=$" + str(real_exit.get("ask")) + " mid=$" + str(real_exit_mid))
        print("Exit synthetic vs real midpoint: " + (str(round(exit_pct_diff, 1)) + "%" if exit_pct_diff is not None else "N/A"))
        in_bid_ask_exit = (real_exit.get("bid") <= t["exit_premium"] <= real_exit.get("ask")) if real_exit.get("bid") is not None and real_exit.get("ask") is not None else None
        print("Synthetic exit price falls inside real bid/ask range: " + str(in_bid_ask_exit))

    comparison_data.append({
        "entry_date": entry_date_str, "entry_pct_diff": entry_pct_diff, "in_bid_ask_entry": in_bid_ask_entry,
        "exit_pct_diff": exit_pct_diff, "in_bid_ask_exit": in_bid_ask_exit,
    })

print("\n" + "=" * 100)
print("SUMMARY (audit sample only -- NOT the full Phase 5 statistical analysis)")
print("=" * 100)
print("Trades with a verified real entry contract: " + str(len(comparison_data)) + " / " + str(len(sample)))
entry_diffs = [abs(c["entry_pct_diff"]) for c in comparison_data if c["entry_pct_diff"] is not None]
if entry_diffs:
    print("Entry median abs % diff: " + str(round(sorted(entry_diffs)[len(entry_diffs)//2], 1)) + "%")
in_range_entry = len([c for c in comparison_data if c["in_bid_ask_entry"]])
print("Entry prices inside real bid/ask range: " + str(in_range_entry) + " / " + str(len(comparison_data)))

exit_diffs = [abs(c["exit_pct_diff"]) for c in comparison_data if c["exit_pct_diff"] is not None]
verified_exits = len([c for c in comparison_data if c["exit_pct_diff"] is not None])
print("\nTrades with verified same contract at exit: " + str(verified_exits) + " / " + str(len(comparison_data)))
if exit_diffs:
    print("Exit median abs % diff: " + str(round(sorted(exit_diffs)[len(exit_diffs)//2], 1)) + "%")
in_range_exit = len([c for c in comparison_data if c["in_bid_ask_exit"]])
print("Exit prices inside real bid/ask range: " + str(in_range_exit) + " / " + str(verified_exits) if verified_exits else "N/A")

print("\nAUDIT COMPLETE -- STOPPING per instruction, per Phase 7's 'first deliverable' requirement.")
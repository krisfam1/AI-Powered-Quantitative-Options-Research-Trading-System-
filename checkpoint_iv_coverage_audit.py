from dotenv import load_dotenv
load_dotenv()

"""
Small-sample implementation test + coverage audit for checkpoint/exit
historical-IV lookups. Does NOT implement any missing-IV fallback
policy -- flags gaps explicitly rather than hiding them.

For a small, fixed sample of real V1 trades (reusing already-validated
entry/exit data, no strategy changes), traces every calendar day the
position was open and checks whether that EXACT contract's IV is
available at that day's real T-1 EOD snapshot.
"""

import os
import requests
from datetime import datetime, timezone, timedelta
from portfolio_backtest import run_portfolio_backtest
from gex_data_loader import get_previous_trading_day

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)


def fetch_specific_contract_iv(ticker, date_str, contract_symbol, exp_date_str):
    """Looks up a SPECIFIC, already-identified contract's IV on a given date. No re-matching."""
    obs_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    params = {
        "filter[underlying_symbol]": ticker, "filter[tradetime_from]": date_str, "filter[tradetime_to]": date_str,
        "filter[exp_date_from]": exp_date_str, "filter[exp_date_to]": exp_date_str,
        "api_token": EODHD_API_TOKEN, "page[limit]": 1000,
    }
    resp = requests.get(BASE_URL, params=params, timeout=60)
    resp.raise_for_status()
    records = resp.json().get("data", [])
    for r in records:
        a = r.get("attributes", {})
        if a.get("contract") != contract_symbol:
            continue
        parts = r.get("id", "").split("-", 1)
        if len(parts) != 2:
            continue
        try:
            id_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
        except ValueError:
            continue
        if id_date != obs_date:
            continue
        if a.get("volatility") is None:
            return {"status": "found_but_no_iv"}
        return {"status": "exact_match", "iv": a["volatility"]}
    return {"status": "not_found"}


def fetch_rematch_iv(ticker, date_str, target_strike, option_type, target_dte=14):
    """Re-matching fallback: closest real contract to target_strike/target_dte, per the validated selection rule."""
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
        if a.get("type") != option_type or a.get("volatility") is None:
            continue
        parts = r.get("id", "").split("-", 1)
        if len(parts) != 2:
            continue
        try:
            id_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
        except ValueError:
            continue
        if id_date != obs_date:
            continue
        exp_date = datetime.strptime(a["exp_date"], "%Y-%m-%d").date()
        a["_actual_dte"] = (exp_date - obs_date).days
        valid.append(a)
    if not valid:
        return None
    return min(valid, key=lambda a: abs(a["strike"] - target_strike) / target_strike + (abs(a["_actual_dte"] - target_dte) / target_dte) * 0.5)


print("Generating a small, real V1 trade sample (AAPL, first 6 trades)...\n")
v1 = run_portfolio_backtest(["AAPL"], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v1")
sample_trades = sorted(v1["closed_trades"], key=lambda t: str(t["entry_date"]))[:6]

results = {"exact_match": 0, "rematch_required": 0, "missing": 0, "total_checkpoints": 0}
per_trade_detail = []

for t in sample_trades:
    entry_date = t["entry_date"]
    exit_date = t["exit_date"]
    strike = t["strike"]
    expiry_date = t["expiry_date"]

    # Determine the exact entry contract by finding the T-1 match, per validated rule
    entry_t_minus_1 = get_previous_trading_day(entry_date, reference_ticker="AAPL")
    entry_contract_match = fetch_rematch_iv("AAPL", entry_t_minus_1.isoformat(), strike, "call")
    if entry_contract_match is None:
        print("Trade " + str(entry_date) + ": no entry contract found -- skipping trade")
        continue
    contract_symbol = entry_contract_match["contract"]
    exp_date_str = entry_contract_match["exp_date"]

    print("=" * 90)
    print("TRADE: entry=" + str(entry_date) + " exit=" + str(exit_date) + " contract=" + contract_symbol)
    print("=" * 90)

    # Determine every calendar day the position was open
    checkpoint_dates = []
    d = entry_date
    while d <= exit_date:
        checkpoint_dates.append(d)
        d = d + timedelta(days=1)
    # Filter to real trading days only (approximate: skip weekends; holidays handled by the T-1 lookup itself)
    checkpoint_dates = [d for d in checkpoint_dates if d.weekday() < 5]

    trade_detail = []
    for cp_date in checkpoint_dates:
        cp_t_minus_1 = get_previous_trading_day(cp_date, reference_ticker="AAPL")
        exact = fetch_specific_contract_iv("AAPL", cp_t_minus_1.isoformat(), contract_symbol, exp_date_str)
        results["total_checkpoints"] += 1

        if exact["status"] == "exact_match":
            results["exact_match"] += 1
            status = "EXACT (iv=" + str(round(exact["iv"], 4)) + ")"
        else:
            rematch = fetch_rematch_iv("AAPL", cp_t_minus_1.isoformat(), strike, "call", target_dte=(expiry_date - cp_date).days)
            if rematch is not None:
                results["rematch_required"] += 1
                status = "RE-MATCH REQUIRED (iv=" + str(round(rematch["volatility"], 4)) + ", contract=" + rematch["contract"] + ")"
            else:
                results["missing"] += 1
                status = "MISSING -- FLAGGED, NOT FILLED"

        print("  checkpoint=" + str(cp_date) + " (T-1=" + str(cp_t_minus_1) + "): " + status)
        trade_detail.append({"checkpoint": str(cp_date), "status": status})

    per_trade_detail.append({"entry": str(entry_date), "contract": contract_symbol, "checkpoints": trade_detail})

print("\n" + "=" * 90)
print("COVERAGE SUMMARY")
print("=" * 90)
total = results["total_checkpoints"]
print("Total checkpoints examined: " + str(total))
print("Exact-contract IV available: " + str(results["exact_match"]) + " (" + str(round(results["exact_match"]/total*100,1) if total else 0) + "%)")
print("Re-match required: " + str(results["rematch_required"]) + " (" + str(round(results["rematch_required"]/total*100,1) if total else 0) + "%)")
print("Missing entirely: " + str(results["missing"]) + " (" + str(round(results["missing"]/total*100,1) if total else 0) + "%)")

print("\nAUDIT COMPLETE. No fallback policy implemented. No performance run executed.")
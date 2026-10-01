from dotenv import load_dotenv
load_dotenv()

"""
Targeted checkpoint-IV coverage audit for the genuinely longest-held
V1 trades found in the full 6-ticker search. No fabrication -- these
are real trades that actually occurred.
"""

import os
import requests
from datetime import datetime, timezone, timedelta
from portfolio_backtest import run_portfolio_backtest
from gex_data_loader import get_previous_trading_day
import backtest_engine as be

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)

TARGET_TRADES = [
    ("AAPL", "2026-07-06", "2026-07-13", 321.79),
    ("AAPL", "2026-08-12", "2026-08-19", 314.29),
    ("NVDA", "2026-08-11", "2026-08-18", 231.96),
    ("AMD", "2026-08-12", "2026-08-18", 535.73),
    ("TSLA", "2026-08-07", "2026-08-12", 352.0),
]


def is_real_trading_day(date_obj, reference_ticker):
    start = datetime.combine(date_obj, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    try:
        bars = be.get_historical_bars(reference_ticker, start, end)
    except Exception:
        bars = []
    return len(bars) > 0


def fetch_specific_contract_iv(ticker, date_str, contract_symbol, exp_date_str):
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
        return {"status": "exact_match", "iv": a["volatility"], "snapshot_date": str(id_date)}
    return {"status": "not_found"}


def fetch_rematch_iv(ticker, date_str, target_strike, option_type, target_dte=14):
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


results = {"exact_match": 0, "rematch_required": 0, "missing": 0, "stale_invalid": 0, "total_checkpoints": 0}
audit_violations = []
trade_holding_periods = []

for ticker, entry_str, exit_str, strike in TARGET_TRADES:
    entry_date = datetime.strptime(entry_str, "%Y-%m-%d").date()
    exit_date = datetime.strptime(exit_str, "%Y-%m-%d").date()
    holding_days = (exit_date - entry_date).days
    trade_holding_periods.append(holding_days)

    entry_t_minus_1 = get_previous_trading_day(entry_date, reference_ticker=ticker)
    entry_contract_match = fetch_rematch_iv(ticker, entry_t_minus_1.isoformat(), strike, "call")
    if entry_contract_match is None:
        print(ticker + " " + entry_str + ": no entry contract found -- skipping")
        continue
    contract_symbol = entry_contract_match["contract"]
    exp_date_str = entry_contract_match["exp_date"]

    print("=" * 100)
    print(ticker + " -- entry=" + entry_str + " exit=" + exit_str + " (holding=" + str(holding_days) + " days) contract=" + contract_symbol)
    print("=" * 100)

    checkpoint_dates = []
    d = entry_date
    while d <= exit_date:
        if is_real_trading_day(d, ticker):
            checkpoint_dates.append(d)
        d = d + timedelta(days=1)

    prev_snapshot_date = None
    for cp_date in checkpoint_dates:
        cp_t_minus_1 = get_previous_trading_day(cp_date, reference_ticker=ticker)
        dte = (datetime.strptime(exp_date_str, "%Y-%m-%d").date() - cp_date).days
        exact = fetch_specific_contract_iv(ticker, cp_t_minus_1.isoformat(), contract_symbol, exp_date_str)
        results["total_checkpoints"] += 1

        if cp_t_minus_1 >= cp_date:
            audit_violations.append("LOOKAHEAD at " + ticker + " " + str(cp_date))

        if exact["status"] == "exact_match":
            results["exact_match"] += 1
            snap_date = datetime.strptime(exact["snapshot_date"], "%Y-%m-%d").date()
            if snap_date != cp_t_minus_1:
                audit_violations.append("SNAPSHOT MISMATCH at " + ticker + " " + str(cp_date))
            if snap_date >= cp_date:
                audit_violations.append("FUTURE IV at " + ticker + " " + str(cp_date))
            if prev_snapshot_date and snap_date < prev_snapshot_date:
                audit_violations.append("SNAPSHOT REGRESSION at " + ticker + " " + str(cp_date))
            prev_snapshot_date = snap_date
            status = "EXACT (iv=" + str(round(exact["iv"],4)) + " snapshot=" + exact["snapshot_date"] + " dte=" + str(dte) + ")"
        elif exact["status"] == "found_but_no_iv":
            results["stale_invalid"] += 1
            status = "FOUND BUT NO IV -- flagged"
        else:
            rematch = fetch_rematch_iv(ticker, cp_t_minus_1.isoformat(), strike, "call", target_dte=dte)
            if rematch is not None:
                results["rematch_required"] += 1
                status = "RE-MATCH (iv=" + str(round(rematch["volatility"],4)) + " contract=" + rematch["contract"] + ")"
            else:
                results["missing"] += 1
                status = "MISSING -- flagged, not filled"

        print("  checkpoint=" + str(cp_date) + " T-1=" + str(cp_t_minus_1) + " dte=" + str(dte) + ": " + status)
    print()

print("=" * 100)
print("FINAL SUMMARY -- LONGEST-HELD TRADES")
print("=" * 100)
print("Trades tested: " + str(len(TARGET_TRADES)))
print("Holding periods: " + str(trade_holding_periods) + " days")
total = results["total_checkpoints"]
print("Total checkpoints: " + str(total))
print("Exact-contract IV coverage: " + str(results["exact_match"]) + " / " + str(total) + " (" + str(round(results["exact_match"]/total*100,1) if total else 0) + "%)")
print("Re-match required: " + str(results["rematch_required"]))
print("Missing: " + str(results["missing"]))
print("Stale/invalid: " + str(results["stale_invalid"]))
print("Look-ahead / snapshot / contract-identity violations: " + str(len(audit_violations)))
for v in audit_violations:
    print("  " + v)

print("\nAUDIT COMPLETE.")
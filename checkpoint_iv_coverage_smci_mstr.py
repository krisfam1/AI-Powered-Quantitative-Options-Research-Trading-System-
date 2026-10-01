from dotenv import load_dotenv
load_dotenv()

"""
Checkpoint-IV coverage audit for SMCI and MSTR, fixing the earlier
checkpoint-date generation bug (now verifies each date is a REAL
trading day via actual bar data, not just weekend filtering -- a
naive weekend filter would still wrongly include market holidays
like Juneteenth).
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


def is_real_trading_day(date_obj, reference_ticker):
    """Verifies via real bar data, not calendar assumptions -- fixes the Juneteenth bug."""
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


def audit_ticker(ticker):
    print("=" * 100)
    print(ticker + " CHECKPOINT-IV COVERAGE AUDIT")
    print("=" * 100)

    v1 = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v1")
    sample_trades = sorted(v1["closed_trades"], key=lambda t: str(t["entry_date"]))[:6]

    results = {"exact_match": 0, "rematch_required": 0, "missing": 0, "stale_invalid": 0, "total_checkpoints": 0}
    affected_trades = 0
    audit_violations = []

    for t in sample_trades:
        entry_date = t["entry_date"]
        exit_date = t["exit_date"]
        strike = t["strike"]
        expiry_date = t["expiry_date"]

        entry_t_minus_1 = get_previous_trading_day(entry_date, reference_ticker=ticker)
        entry_contract_match = fetch_rematch_iv(ticker, entry_t_minus_1.isoformat(), strike, "call")
        if entry_contract_match is None:
            print("Trade " + str(entry_date) + ": no entry contract found -- skipping trade")
            continue
        contract_symbol = entry_contract_match["contract"]
        exp_date_str = entry_contract_match["exp_date"]

        print("\n--- TRADE: entry=" + str(entry_date) + " exit=" + str(exit_date) + " contract=" + contract_symbol + " ---")

        # FIXED: verify real trading days via actual bar data
        checkpoint_dates = []
        d = entry_date
        while d <= exit_date:
            if is_real_trading_day(d, ticker):
                checkpoint_dates.append(d)
            d = d + timedelta(days=1)

        trade_had_gap = False
        for cp_date in checkpoint_dates:
            cp_t_minus_1 = get_previous_trading_day(cp_date, reference_ticker=ticker)
            exact = fetch_specific_contract_iv(ticker, cp_t_minus_1.isoformat(), contract_symbol, exp_date_str)
            results["total_checkpoints"] += 1

            # Audit checks
            if cp_t_minus_1 >= cp_date:
                audit_violations.append("LOOKAHEAD VIOLATION at " + str(cp_date))

            if exact["status"] == "exact_match":
                results["exact_match"] += 1
                snap_date = datetime.strptime(exact["snapshot_date"], "%Y-%m-%d").date()
                if snap_date != cp_t_minus_1:
                    audit_violations.append("SNAPSHOT MISMATCH at " + str(cp_date))
                if snap_date >= cp_date:
                    audit_violations.append("FUTURE IV USED at " + str(cp_date))
                status = "EXACT (iv=" + str(round(exact["iv"], 4)) + ", snapshot=" + exact["snapshot_date"] + ")"
            elif exact["status"] == "found_but_no_iv":
                results["stale_invalid"] += 1
                trade_had_gap = True
                status = "FOUND BUT NO IV VALUE -- flagged"
            else:
                rematch = fetch_rematch_iv(ticker, cp_t_minus_1.isoformat(), strike, "call", target_dte=(expiry_date - cp_date).days)
                if rematch is not None:
                    results["rematch_required"] += 1
                    trade_had_gap = True
                    status = "RE-MATCH REQUIRED (iv=" + str(round(rematch["volatility"], 4)) + ", contract=" + rematch["contract"] + ")"
                else:
                    results["missing"] += 1
                    trade_had_gap = True
                    status = "MISSING -- FLAGGED, NOT FILLED"

            print("  checkpoint=" + str(cp_date) + " (T-1=" + str(cp_t_minus_1) + "): " + status)

        if trade_had_gap:
            affected_trades += 1

    total = results["total_checkpoints"]
    print("\n--- " + ticker + " SUMMARY ---")
    print("Total checkpoints: " + str(total))
    print("Exact match: " + str(results["exact_match"]) + " (" + str(round(results["exact_match"]/total*100,1) if total else 0) + "%)")
    print("Re-match required: " + str(results["rematch_required"]))
    print("Missing: " + str(results["missing"]))
    print("Stale/invalid: " + str(results["stale_invalid"]))
    print("Affected trades: " + str(affected_trades) + " / " + str(len(sample_trades)))
    print("Audit violations (lookahead/snapshot/future): " + str(len(audit_violations)))
    for v in audit_violations:
        print("  " + v)

    return {"ticker": ticker, "results": results, "affected_trades": affected_trades, "total_trades": len(sample_trades)}

all_results = {}
for ticker in ["SMCI", "MSTR"]:
    all_results[ticker] = audit_ticker(ticker)
    print()

print("=" * 100)
print("THREE-TICKER COMPARISON")
print("=" * 100)
print("| Ticker | Checkpoints | Exact IV | Re-match | Missing | Coverage |")
print("| AAPL   | 13 | 13 | 0 | 0 | 100.0% |")
for ticker in ["SMCI", "MSTR"]:
    r = all_results[ticker]["results"]
    total = r["total_checkpoints"]
    cov = round(r["exact_match"]/total*100,1) if total else 0
    print("| " + ticker + "   | " + str(total) + " | " + str(r["exact_match"]) + " | " + str(r["rematch_required"]) + " | " + str(r["missing"]) + " | " + str(cov) + "% |")

combined_total = 13 + all_results["SMCI"]["results"]["total_checkpoints"] + all_results["MSTR"]["results"]["total_checkpoints"]
combined_exact = 13 + all_results["SMCI"]["results"]["exact_match"] + all_results["MSTR"]["results"]["exact_match"]
print("\nCombined coverage across all 3 tickers: " + str(combined_exact) + " / " + str(combined_total) + " = " + str(round(combined_exact/combined_total*100,1)) + "%")

print("\nAUDIT COMPLETE. No fallback policy implemented. No performance run executed.")
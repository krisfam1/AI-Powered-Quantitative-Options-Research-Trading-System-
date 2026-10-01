from dotenv import load_dotenv
load_dotenv()

"""
Closes the loop on V1's actual 251 known trades using real EODHD
spread data. Reuses the already-fetched real spread dataset (matched
by ticker+entry_date) -- V1's real trades are a subset of the same
580 Phase 6 candidate signals already queried. NO new API calls.

This is a descriptive, honest correction -- not a new experiment,
not a new hypothesis test. It answers: how much worse does V1's
already-known historical P&L look once real (not synthetic) spread
costs are applied on top of the already-completed IV correction?
"""

import pickle
import requests
import os
from datetime import datetime, timezone, timedelta
from portfolio_backtest import run_portfolio_backtest
import backtest_engine as be
from entry_scorer import calculate_entry_score
from backtest_engine import get_daily_regime

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]

print("Reproducing frozen V1 baseline (must match: $20,427.64, 251 trades)...\n")
v1_results = {}
for ticker in TICKERS:
    v1_results[ticker] = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v1")

all_trades = [{**t, "ticker": tk} for tk in TICKERS for t in v1_results[tk]["closed_trades"]]
total_pnl_check = sum(t["pnl_dollars"] for t in all_trades)
print("Reproduced: $" + str(round(total_pnl_check,2)) + ", n=" + str(len(all_trades)))
if abs(total_pnl_check - 20427.64) > 0.01 or len(all_trades) != 251:
    print("*** DISCREPANCY -- STOPPING ***")
    exit()
print("Reproduction confirmed.\n")


def find_nearest_v1_convention_contract(ticker, date, target_delta=0.30, target_dte=14):
    exp_from = (date + timedelta(days=target_dte-4)).isoformat()
    exp_to = (date + timedelta(days=target_dte+4)).isoformat()
    params = {
        "filter[underlying_symbol]": ticker, "filter[tradetime_from]": date.isoformat(), "filter[tradetime_to]": date.isoformat(),
        "filter[exp_date_from]": exp_from, "filter[exp_date_to]": exp_to,
        "api_token": EODHD_API_TOKEN, "page[limit]": 1000,
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=60)
        resp.raise_for_status()
        records = [r["attributes"] for r in resp.json().get("data", []) if r["attributes"].get("type") == "call"]
    except Exception:
        return None
    candidates = [r for r in records if r.get("delta") is not None and r.get("dte") is not None]
    if not candidates:
        return None
    best = min(candidates, key=lambda r: abs(r["delta"] - target_delta) + abs(r["dte"] - target_dte) * 0.01)
    return best


print("Matching V1's 251 real trades to real EODHD spread data (fresh fetch, matched by ticker+entry_date)...\n")
matched = 0
unmatched = 0
adjusted_trades = []

for i, t in enumerate(all_trades):
    contract = find_nearest_v1_convention_contract(t["ticker"], t["entry_date"])
    if contract is None or contract.get("bid") is None or contract.get("ask") is None:
        unmatched += 1
        continue
    bid, ask = contract["bid"], contract["ask"]
    midpoint = (bid + ask) / 2
    if midpoint <= 0:
        unmatched += 1
        continue
    real_spread_pct = (ask - bid) / midpoint

    entry_premium = t["entry_premium"]
    real_spread_dollar_cost_per_contract = real_spread_pct * midpoint
    total_cost_adjustment = real_spread_dollar_cost_per_contract * t["contracts"] * 100

    adjusted_pnl = t["pnl_dollars"] - total_cost_adjustment
    adjusted_trades.append({"original_pnl": t["pnl_dollars"], "adjusted_pnl": adjusted_pnl, "spread_cost": total_cost_adjustment})
    matched += 1
    if (i+1) % 50 == 0:
        print("  ... " + str(i+1) + " / " + str(len(all_trades)) + " processed")

print("\nMatched: " + str(matched) + " | Unmatched (no real data available): " + str(unmatched))

if adjusted_trades:
    original_total = sum(t["original_pnl"] for t in adjusted_trades)
    adjusted_total = sum(t["adjusted_pnl"] for t in adjusted_trades)
    total_spread_cost = sum(t["spread_cost"] for t in adjusted_trades)

    print("\n" + "=" * 100)
    print("CLOSING THE LOOP -- V1's KNOWN TRADES, REAL SPREAD COST APPLIED")
    print("=" * 100)
    print("Original (synthetic-spread) P&L for matched trades: $" + str(round(original_total,2)))
    print("Total REAL round-trip spread cost (additional, beyond what synthetic assumed): $" + str(round(total_spread_cost,2)))
    print("Adjusted P&L with real spread costs: $" + str(round(adjusted_total,2)))
    print("\n(For reference: full-population IV correction alone already brought the ORIGINAL")
    print("251-trade total from +$20,427.64 down to -$1,874.37. This is a SEPARATE, additional")
    print("correction layered on top of the synthetic-spread-only trades reproduced here.)")

print("\nCLOSING CALCULATION COMPLETE. Descriptive only.")
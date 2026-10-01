from dotenv import load_dotenv
load_dotenv()

"""
Forensic pricing investigation, per explicit request. Reuses the SAME
15-trade sample and validated contract-matching logic from the pricing
audit. Investigations 1, 2, 4 (contract match, input comparison,
liquidity) are reported directly. Investigation 3 (the critical IV
test): back-solves our synthetic volatility input from the known
synthetic price (Black-Scholes is monotonic in vol, so this recovers
the exact input used), then recomputes price using EODHD's real,
historical implied volatility for the same contract -- isolating how
much of the gap volatility alone explains.
"""

import os
import requests
import math
from datetime import datetime, timezone, timedelta
from scipy.stats import norm
from portfolio_backtest import run_portfolio_backtest
from options_backtest_engine import black_scholes_price
import backtest_engine as be

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)


def fetch_real_contract_near_strike(ticker, date_str, target_strike, option_type, target_dte=14):
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
        valid.append(a)
    if not valid:
        return None
    return min(valid, key=lambda a: abs(a["strike"] - target_strike) / target_strike + (abs(a["_actual_dte"] - target_dte) / target_dte) * 0.5)


def solve_implied_vol_from_price(target_price, spot, strike, dte, option_type="call", risk_free_rate=0.04):
    """Bisection solve: what volatility, held in our OWN Black-Scholes formula, reproduces target_price -- recovers our synthetic model's actual vol input."""
    low, high = 0.001, 5.0
    for _ in range(100):
        mid = (low + high) / 2
        price = black_scholes_price(spot, strike, dte, mid, risk_free_rate, option_type)
        if price < target_price:
            low = mid
        else:
            high = mid
        if abs(high - low) < 1e-6:
            break
    return (low + high) / 2


print("Regenerating the real, deterministic synthetic dataset...\n")
result = run_portfolio_backtest(["AAPL"], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call")
all_trades = sorted(result["closed_trades"], key=lambda t: str(t["entry_date"]))
sample = all_trades[::2]
print("Sample size: " + str(len(sample)) + "\n")

bars_cache = be.get_historical_bars("AAPL", FIXED_START, FIXED_END)
bars_by_date = {}
for b in bars_cache:
    bars_by_date.setdefault(b.timestamp.date().isoformat(), []).append(b)

decomposition_results = []

for t in sample:
    entry_date_str = str(t["entry_date"])
    strike = t["strike"]
    dte = 14

    print("=" * 100)
    print("TRADE: Entry " + entry_date_str + " strike=" + str(strike))
    print("=" * 100)

    real_entry = fetch_real_contract_near_strike("AAPL", entry_date_str, strike, "call")
    if real_entry is None:
        print("No real contract found -- skipping.")
        continue

    day_bars = bars_by_date.get(entry_date_str)
    entry_spot = float(day_bars[-1].close) if day_bars else None

    print("\n--- INVESTIGATION 1: Contract matching ---")
    print("Underlying=AAPL | option_type=call (both) | strike: synthetic=" + str(strike) + " real=" + str(real_entry["strike"]))
    print("Real contract: " + real_entry["contract"] + " | exp=" + real_entry["exp_date"] + " | actual_dte=" + str(real_entry["_actual_dte"]) + " (target=14)")

    print("\n--- INVESTIGATION 2: Black-Scholes input comparison ---")
    print("Underlying price: our_synthetic=$" + str(entry_spot) + " (from real Alpaca bar)")
    print("Risk-free rate: 4% (hardcoded default) | Dividend yield: NOT MODELED (confirmed absent from function)")

    synthetic_vol = solve_implied_vol_from_price(t["entry_premium"], entry_spot, strike, dte, "call")
    real_iv = real_entry.get("volatility")
    print("Volatility: our_synthetic_input(back-solved)=" + str(round(synthetic_vol, 4)) + " | EODHD_real_IV=" + str(real_iv))

    print("\n--- INVESTIGATION 4: Liquidity ---")
    bid, ask = real_entry.get("bid"), real_entry.get("ask")
    spread = ask - bid if bid is not None and ask is not None else None
    spread_pct = (spread / real_entry.get("midpoint") * 100) if spread and real_entry.get("midpoint") else None
    print("bid=$" + str(bid) + " ask=$" + str(ask) + " spread=$" + str(round(spread, 3) if spread else None) + " spread_pct=" + str(round(spread_pct, 1) if spread_pct else None) + "% volume=" + str(real_entry.get("volume")) + " OI=" + str(real_entry.get("open_interest")))

    print("\n--- INVESTIGATION 3 & 7: IV substitution decomposition ---")
    print("Step A -- Current synthetic price: $" + str(round(t["entry_premium"], 3)))
    if real_iv is not None and entry_spot is not None:
        iv_corrected_price = black_scholes_price(entry_spot, strike, dte, real_iv, 0.04, "call")
        real_mid = real_entry.get("midpoint")
        print("Step B -- Same B-S formula, REAL IV (" + str(round(real_iv, 4)) + ") substituted: $" + str(round(iv_corrected_price, 3)))
        print("Step C -- Real market midpoint: $" + str(real_mid))
        original_diff_pct = (t["entry_premium"] - real_mid) / real_mid * 100 if real_mid else None
        iv_corrected_diff_pct = (iv_corrected_price - real_mid) / real_mid * 100 if real_mid else None
        print("Original synthetic vs real: " + (str(round(original_diff_pct, 1)) + "%" if original_diff_pct is not None else "N/A"))
        print("IV-corrected vs real: " + (str(round(iv_corrected_diff_pct, 1)) + "%" if iv_corrected_diff_pct is not None else "N/A"))
        decomposition_results.append({"original_diff": abs(original_diff_pct) if original_diff_pct else None, "iv_corrected_diff": abs(iv_corrected_diff_pct) if iv_corrected_diff_pct else None})
    else:
        print("Real IV not available for this contract -- cannot run substitution test.")

    print()

print("=" * 100)
print("DECOMPOSITION SUMMARY")
print("=" * 100)
orig = [d["original_diff"] for d in decomposition_results if d["original_diff"] is not None]
corrected = [d["iv_corrected_diff"] for d in decomposition_results if d["iv_corrected_diff"] is not None]
if orig:
    print("Original synthetic median abs % diff: " + str(round(sorted(orig)[len(orig)//2], 1)) + "%")
if corrected:
    print("IV-corrected median abs % diff: " + str(round(sorted(corrected)[len(corrected)//2], 1)) + "%")
print("\nDIAGNOSTIC COMPLETE.")
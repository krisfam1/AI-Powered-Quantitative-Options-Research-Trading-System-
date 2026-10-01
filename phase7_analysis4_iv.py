from dotenv import load_dotenv
load_dotenv()

"""
Phase 7, Analysis 4 -- FORENSIC validation of extreme winners under
real historical IV. NOT an attempt to rescue the strategy. Current
conclusion (extreme concentration, no demonstrated repeatable edge)
stands regardless of this analysis's outcome. No strategy changes.
"""

import os
import random
import requests
import statistics
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import backtest_engine as be
from portfolio_backtest import run_portfolio_backtest
from options_backtest_engine import calculate_historical_volatility, black_scholes_price
from gex_data_loader import get_previous_trading_day

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]

def fetch_real_iv(ticker, date_str, target_strike, target_dte=14):
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
        if a.get("type") != "call" or a.get("volatility") is None:
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
    best = min(valid, key=lambda a: abs(a["strike"] - target_strike) / target_strike + (abs(a["_actual_dte"] - target_dte) / target_dte) * 0.5)
    return best["volatility"]

print("Reproducing frozen V1 baseline...\n")
v1_results = {}
all_bars = {}
for ticker in TICKERS:
    v1_results[ticker] = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v1")
    all_bars[ticker] = be.get_historical_bars(ticker, FIXED_START, FIXED_END)

enriched_trades = []
for ticker in TICKERS:
    ground_truth = {(g["ticker"], g["entry_date"], round(g["strike"],2)): g for g in v1_results[ticker]["v1_ground_truth_log"]}
    for t in v1_results[ticker]["closed_trades"]:
        key = (ticker, t["entry_date"], round(t["strike"],2))
        gt = ground_truth.get(key)
        if gt is None:
            continue
        enriched_trades.append({**t, "entry_index": gt["entry_index"], "ticker": ticker, "v1_vol": gt["v1_realized_vol"]})

sorted_by_pnl = sorted(enriched_trades, key=lambda t: -t["pnl_dollars"])
top5 = sorted_by_pnl[:5]
top20 = sorted_by_pnl[:20]
remaining_pool = sorted_by_pnl[20:]
random.seed(42)
remaining_sample = random.sample(remaining_pool, min(20, len(remaining_pool)))

total_pnl = sum(t["pnl_dollars"] for t in enriched_trades)

print("Fetching real historical IV for top-20 trades + a 20-trade sample of remaining trades (entry + exit)...\n")

def reprice_trade(t):
    ticker = t["ticker"]
    entry_date_str = str(t["entry_date"])
    exit_date_str = str(t["exit_date"])
    strike = t["strike"]
    dte_target = 14

    entry_t_minus_1 = get_previous_trading_day(t["entry_date"], reference_ticker=ticker)
    entry_iv = fetch_real_iv(ticker, entry_t_minus_1.isoformat(), strike, dte_target)

    exit_dte = max((t["expiry_date"] - t["exit_date"]).days, 1)
    exit_t_minus_1 = get_previous_trading_day(t["exit_date"], reference_ticker=ticker)
    exit_iv = fetch_real_iv(ticker, exit_t_minus_1.isoformat(), strike, exit_dte)

    if entry_iv is None or exit_iv is None:
        return None

    BRACKETS = [(5.0, 0.02), (2.0, 0.04), (1.0, 0.07), (0.0, 0.12)]
    def recover_raw(p):
        for th, sp in BRACKETS:
            mult = 1 + sp/2
            cand = p / mult
            if cand >= th:
                return cand
        return p / 1.06
    raw_entry = recover_raw(t["entry_premium"])

    def solve_spot(target, strike, dte, vol):
        low, high = 1.0, 5000.0
        for _ in range(100):
            mid = (low+high)/2
            price = black_scholes_price(mid, strike, dte, vol, option_type="call")
            if price < target: low = mid
            else: high = mid
            if abs(high-low) < 0.001: break
        return (low+high)/2

    entry_spot = solve_spot(raw_entry, strike, dte_target, t["v1_vol"])
    exit_spot = solve_spot(t["exit_premium"], strike, exit_dte, t["v1_vol"])

    iv_entry_price = black_scholes_price(entry_spot, strike, dte_target, entry_iv, option_type="call")
    iv_exit_price = black_scholes_price(exit_spot, strike, exit_dte, exit_iv, option_type="call")
    iv_return = (iv_exit_price - iv_entry_price) / iv_entry_price if iv_entry_price else None

    spot_only_price = black_scholes_price(exit_spot, strike, exit_dte, entry_iv, option_type="call")
    spot_only_return = (spot_only_price - iv_entry_price) / iv_entry_price if iv_entry_price else None

    return {
        "ticker": ticker, "entry_date": entry_date_str, "exit_date": exit_date_str,
        "entry_iv": entry_iv, "exit_iv": exit_iv, "entry_spot": entry_spot, "exit_spot": exit_spot,
        "underlying_move_pct": (exit_spot-entry_spot)/entry_spot*100,
        "synthetic_return_pct": t["pnl_pct"], "iv_repriced_return_pct": iv_return*100 if iv_return else None,
        "spot_only_return_pct": spot_only_return*100 if spot_only_return else None,
        "iv_entry_price": iv_entry_price, "iv_exit_price": iv_exit_price,
    }

def report_group(trades, label):
    print("=" * 100)
    print(label)
    print("=" * 100)
    results = []
    for t in trades:
        r = reprice_trade(t)
        if r is None:
            print("  " + t["ticker"] + " " + str(t["entry_date"]) + ": IV data unavailable -- skipped")
            continue
        results.append(r)
        print("  " + r["ticker"] + " " + r["entry_date"] + ": synthetic_ret=" + str(round(r["synthetic_return_pct"],1)) + "% IV_repriced_ret=" + str(round(r["iv_repriced_return_pct"],1) if r["iv_repriced_return_pct"] else None) + "% underlying_move=" + str(round(r["underlying_move_pct"],2)) + "% entry_IV=" + str(round(r["entry_iv"],3)) + " exit_IV=" + str(round(r["exit_iv"],3)) + " spot_only_ret=" + str(round(r["spot_only_return_pct"],1) if r["spot_only_return_pct"] else None) + "%")
    return results

print("\n")
top5_results = report_group(top5, "TOP 5 TRADES -- SYNTHETIC vs REAL-IV REPRICING")
print()
top20_extra = report_group(top20[5:], "TOP 6-20 TRADES (continuing top-20 set)")
print()
remaining_results = report_group(remaining_sample, "REMAINING-TRADES SAMPLE (n=20, random seed=42)")

def summarize(results, label):
    if not results:
        print(label + ": no data")
        return
    synth = [r["synthetic_return_pct"] for r in results]
    ivr = [r["iv_repriced_return_pct"] for r in results if r["iv_repriced_return_pct"] is not None]
    print(label + " (n=" + str(len(results)) + "): median_synthetic=" + str(round(statistics.median(synth),1)) + "% median_IV_repriced=" + str(round(statistics.median(ivr),1) if ivr else None) + "%")

print("\n" + "=" * 100)
print("SUMMARY COMPARISON")
print("=" * 100)
summarize(top5_results, "Top 5")
summarize(top5_results + top20_extra, "Top 20")
summarize(remaining_results, "Remaining sample")

print("\nPHASE 7 ANALYSIS 4 COMPLETE.")
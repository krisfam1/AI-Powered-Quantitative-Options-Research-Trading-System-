from dotenv import load_dotenv
load_dotenv()

"""
Expanded Historical EOD Options Pricing Validation. Separate module,
does NOT modify the production backtest/strategy engines. Extends the
original 15-trade AAPL-only diagnostic to a larger, non-cherry-picked,
multi-ticker sample across the clean June-Sept 2026 EODHD window.

Same methodology as the original diagnostic: exact contract matching
(strike/expiration/DTE/contract-ID/snapshot-date), same Black-Scholes
implementation, same underlying price/risk-free-rate/dividend
assumptions. ONLY intentional input change: realized vol -> real
historical EODHD implied volatility.

Focuses on ENTRY-side comparison (per the requested field list).

LIMITATION (restated): EODHD is EOD-only historical options data. This
validates pricing-magnitude realism against real historical EOD market
data -- it does NOT establish what an intraday trade would have filled
at the exact 5-minute signal timestamp.
"""

import os
import requests
from datetime import datetime, timezone, timedelta
from portfolio_backtest import run_portfolio_backtest
from options_backtest_engine import black_scholes_price
import backtest_engine as be

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]


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


print("Generating real, deterministic synthetic datasets for all 6 tickers...\n")
all_trades = []
bars_by_ticker_date = {}
for ticker in TICKERS:
    result = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call")
    for t in result["closed_trades"]:
        t["_ticker"] = ticker
        all_trades.append(t)
    bars = be.get_historical_bars(ticker, FIXED_START, FIXED_END)
    for b in bars:
        bars_by_ticker_date.setdefault((ticker, b.timestamp.date().isoformat()), []).append(b)
    print(ticker + ": " + str(len(result["closed_trades"])) + " trades")

all_trades = sorted(all_trades, key=lambda t: (str(t["entry_date"]), t["_ticker"]))
print("\nTotal trades across all 6 tickers: " + str(len(all_trades)))

sample = all_trades[::2]
print("Expanded sample size (every 2nd trade): " + str(len(sample)) + "\n")

results = []

for t in sample:
    ticker = t["_ticker"]
    entry_date_str = str(t["entry_date"])
    strike = t["strike"]
    dte = 14

    real_entry = fetch_real_contract_near_strike(ticker, entry_date_str, strike, "call")
    if real_entry is None:
        continue

    day_bars = bars_by_ticker_date.get((ticker, entry_date_str))
    entry_spot = float(day_bars[-1].close) if day_bars else None
    if entry_spot is None:
        continue

    real_iv = real_entry.get("volatility")
    real_mid = real_entry.get("midpoint")
    real_bid, real_ask = real_entry.get("bid"), real_entry.get("ask")
    if real_iv is None or real_mid is None:
        continue

    synthetic_vol = solve_implied_vol_from_price(t["entry_premium"], entry_spot, strike, dte, "call")
    iv_corrected_price = black_scholes_price(entry_spot, strike, dte, real_iv, 0.04, "call")

    orig_abs_err = abs(t["entry_premium"] - real_mid)
    orig_pct_err = orig_abs_err / real_mid * 100
    corrected_abs_err = abs(iv_corrected_price - real_mid)
    corrected_pct_err = corrected_abs_err / real_mid * 100

    spread = (real_ask - real_bid) if real_bid is not None and real_ask is not None else None
    spread_pct = (spread / real_mid * 100) if spread and real_mid else None
    volume = real_entry.get("volume")
    oi = real_entry.get("open_interest")
    is_illiquid = (oi == 0) or (spread_pct is not None and spread_pct > 50)

    in_bid_ask_orig = (real_bid <= t["entry_premium"] <= real_ask) if real_bid is not None and real_ask is not None else None
    in_bid_ask_corrected = (real_bid <= iv_corrected_price <= real_ask) if real_bid is not None and real_ask is not None else None

    row = {
        "ticker": ticker, "contract": real_entry["contract"], "entry_date": entry_date_str,
        "snapshot_date": entry_date_str, "option_type": "call", "strike": real_entry["strike"],
        "expiration": real_entry["exp_date"], "dte": real_entry["_actual_dte"], "underlying_price": entry_spot,
        "realized_vol": round(synthetic_vol, 4), "historical_iv": round(real_iv, 4),
        "original_price": round(t["entry_premium"], 3), "iv_corrected_price": round(iv_corrected_price, 3),
        "real_bid": real_bid, "real_ask": real_ask, "real_midpoint": real_mid,
        "volume": volume, "open_interest": oi, "spread_pct": round(spread_pct, 1) if spread_pct else None,
        "is_illiquid": is_illiquid,
        "orig_abs_err": round(orig_abs_err, 3), "orig_pct_err": round(orig_pct_err, 1),
        "corrected_abs_err": round(corrected_abs_err, 3), "corrected_pct_err": round(corrected_pct_err, 1),
        "in_bid_ask_orig": in_bid_ask_orig, "in_bid_ask_corrected": in_bid_ask_corrected,
    }
    results.append(row)
    print(ticker + " " + entry_date_str + ": orig_err=" + str(row["orig_pct_err"]) + "% corrected_err=" + str(row["corrected_pct_err"]) + "% illiquid=" + str(is_illiquid))


def summarize(subset, label):
    n = len(subset)
    if n == 0:
        print(label + ": no data")
        return
    orig_errs = sorted(r["orig_pct_err"] for r in subset)
    corrected_errs = sorted(r["corrected_pct_err"] for r in subset)
    orig_median = orig_errs[n // 2]
    corrected_median = corrected_errs[n // 2]
    orig_mean = sum(orig_errs) / n
    corrected_mean = sum(corrected_errs) / n
    in_range_orig = len([r for r in subset if r["in_bid_ask_orig"]])
    in_range_corrected = len([r for r in subset if r["in_bid_ask_corrected"]])
    within_5 = len([r for r in subset if r["corrected_pct_err"] <= 5])
    within_10 = len([r for r in subset if r["corrected_pct_err"] <= 10])
    within_20 = len([r for r in subset if r["corrected_pct_err"] <= 20])

    print("\n" + label + " (n=" + str(n) + "):")
    print("  Original median/mean abs % err: " + str(round(orig_median, 1)) + "% / " + str(round(orig_mean, 1)) + "%")
    print("  IV-corrected median/mean abs % err: " + str(round(corrected_median, 1)) + "% / " + str(round(corrected_mean, 1)) + "%")
    print("  Median error reduction: " + str(round(orig_median - corrected_median, 1)) + " percentage points")
    print("  In real bid/ask range -- original: " + str(in_range_orig) + "/" + str(n) + " | corrected: " + str(in_range_corrected) + "/" + str(n))
    print("  IV-corrected within 5%/10%/20% of midpoint: " + str(within_5) + "/" + str(within_10) + "/" + str(within_20) + " (of " + str(n) + ")")


print("\n" + "=" * 100)
print("AGGREGATE RESULTS -- ALL CONTRACTS")
print("=" * 100)
summarize(results, "All contracts")

liquid_only = [r for r in results if not r["is_illiquid"]]
print("\n" + "=" * 100)
print("AGGREGATE RESULTS -- EXCLUDING ZERO-OI / WIDE-SPREAD (>50%) CONTRACTS")
print("=" * 100)
summarize(liquid_only, "Liquid contracts only")

print("\n" + "=" * 100)
print("PER-TICKER BREAKDOWN")
print("=" * 100)
for ticker in TICKERS:
    ticker_results = [r for r in results if r["ticker"] == ticker]
    summarize(ticker_results, ticker)

print("\n" + "=" * 100)
print("COMPARISON TO ORIGINAL 15-TRADE BASELINE (8.0% median)")
print("=" * 100)
n_all = len(results)
all_corrected_errs = sorted(r["corrected_pct_err"] for r in results)
if n_all:
    print("Expanded sample corrected median: " + str(round(all_corrected_errs[n_all // 2], 1)) + "% (n=" + str(n_all) + ") vs. original 8.0% (n=15)")

print("\nUNEXPLAINED RESIDUALS (corrected error > 20% AND not flagged illiquid):")
unexplained = [r for r in results if r["corrected_pct_err"] > 20 and not r["is_illiquid"]]
for r in unexplained:
    print("  " + r["ticker"] + " " + r["entry_date"] + " " + r["contract"] + ": corrected_err=" + str(r["corrected_pct_err"]) + "% spread_pct=" + str(r["spread_pct"]) + " OI=" + str(r["open_interest"]) + " -- UNEXPLAINED, not forcing an explanation")

print("\nVALIDATION COMPLETE -- STOPPING per instruction.")
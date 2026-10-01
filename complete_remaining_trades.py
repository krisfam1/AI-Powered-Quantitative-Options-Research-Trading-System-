from dotenv import load_dotenv
load_dotenv()

"""
Resumable completion of the expanded IV-correction validation.
Regenerates the IDENTICAL sample (same deterministic sort/sampling),
then skips forward past the last successfully-processed trade
(AAPL 2026-08-25) before the network interruption, processing only
the remaining trades.
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

RESUME_AFTER_DATE = "2026-08-25"
RESUME_AFTER_TICKER = "AAPL"


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


print("Regenerating the identical sample (same deterministic sort/sampling)...\n")
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

all_trades = sorted(all_trades, key=lambda t: (str(t["entry_date"]), t["_ticker"]))
sample = all_trades[::2]
print("Full sample size: " + str(len(sample)))

resume_index = None
for i, t in enumerate(sample):
    if str(t["entry_date"]) == RESUME_AFTER_DATE and t["_ticker"] == RESUME_AFTER_TICKER:
        resume_index = i + 1
        break

if resume_index is None:
    print("Could not find resume point -- aborting rather than guessing.")
    exit()

remaining = sample[resume_index:]
print("Resuming after " + RESUME_AFTER_TICKER + " " + RESUME_AFTER_DATE + " -- " + str(len(remaining)) + " trades remaining\n")

results = []
for t in remaining:
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

    iv_corrected_price = black_scholes_price(entry_spot, strike, dte, real_iv, 0.04, "call")

    orig_pct_err = abs(t["entry_premium"] - real_mid) / real_mid * 100
    corrected_pct_err = abs(iv_corrected_price - real_mid) / real_mid * 100

    spread = (real_ask - real_bid) if real_bid is not None and real_ask is not None else None
    spread_pct = (spread / real_mid * 100) if spread and real_mid else None
    oi = real_entry.get("open_interest")
    is_illiquid = (oi == 0) or (spread_pct is not None and spread_pct > 50)

    results.append({"orig_pct_err": orig_pct_err, "corrected_pct_err": corrected_pct_err, "is_illiquid": is_illiquid})
    print(ticker + " " + entry_date_str + ": orig_err=" + str(round(orig_pct_err,1)) + "% corrected_err=" + str(round(corrected_pct_err,1)) + "% illiquid=" + str(is_illiquid))

print("\n" + "=" * 90)
print("REMAINING-TRADES SUMMARY (n=" + str(len(results)) + ")")
print("=" * 90)
if results:
    n = len(results)
    orig = sorted(r["orig_pct_err"] for r in results)
    corrected = sorted(r["corrected_pct_err"] for r in results)
    print("Original median: " + str(round(orig[n//2], 1)) + "%")
    print("IV-corrected median: " + str(round(corrected[n//2], 1)) + "%")

print("\nCOMPLETION RUN DONE.")
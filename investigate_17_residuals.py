from dotenv import load_dotenv
load_dotenv()

"""
Targeted investigation of the 17 specific unexplained residual trades,
identified directly from the real terminal output already in the
conversation (no new API calls for identification). Regenerates the
LOCAL, deterministic synthetic trades (no EODHD cost) to recover each
trade's strike, then makes exactly 17 targeted EODHD calls -- not a
126-trade rerun -- to get full diagnostic detail for these specific
residuals only.
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

TARGET_RESIDUALS = [
    ("AAPL", "2026-06-12"), ("MSTR", "2026-06-18"), ("TSLA", "2026-06-18"),
    ("SMCI", "2026-06-24"), ("SMCI", "2026-06-29"), ("SMCI", "2026-07-13"),
    ("MSTR", "2026-07-20"), ("SMCI", "2026-07-21"), ("AMD", "2026-07-23"),
    ("AAPL", "2026-07-24"), ("AMD", "2026-08-04"), ("SMCI", "2026-08-11"),
    ("MSTR", "2026-08-24"), ("SMCI", "2026-08-25"), ("NVDA", "2026-09-02"),
    ("AMD", "2026-09-04"), ("TSLA", "2026-09-04"),
]
TARGET_TICKERS = sorted(set(t for t, d in TARGET_RESIDUALS))


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


print("Regenerating LOCAL synthetic trades for the " + str(len(TARGET_TICKERS)) + " relevant tickers (no API cost)...\n")
trades_by_key = {}
bars_by_ticker_date = {}
for ticker in TARGET_TICKERS:
    result = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call")
    for t in result["closed_trades"]:
        trades_by_key[(ticker, str(t["entry_date"]))] = t
    bars = be.get_historical_bars(ticker, FIXED_START, FIXED_END)
    for b in bars:
        bars_by_ticker_date.setdefault((ticker, b.timestamp.date().isoformat()), []).append(b)

print("Fetching targeted, full diagnostic detail for the 17 identified residuals...\n")

for ticker, entry_date_str in TARGET_RESIDUALS:
    key = (ticker, entry_date_str)
    t = trades_by_key.get(key)
    if t is None:
        print(ticker + " " + entry_date_str + ": could not locate local trade -- skipping")
        continue

    strike = t["strike"]
    dte = 14
    real_entry = fetch_real_contract_near_strike(ticker, entry_date_str, strike, "call")
    if real_entry is None:
        print(ticker + " " + entry_date_str + ": no real contract found -- DATA-QUALITY ISSUE")
        continue

    day_bars = bars_by_ticker_date.get(key)
    entry_spot = float(day_bars[-1].close) if day_bars else None
    real_iv = real_entry.get("volatility")
    real_mid = real_entry.get("midpoint")
    real_bid, real_ask = real_entry.get("bid"), real_entry.get("ask")
    volume = real_entry.get("volume")
    oi = real_entry.get("open_interest")
    actual_dte = real_entry.get("_actual_dte")
    spread = (real_ask - real_bid) if real_bid is not None and real_ask is not None else None
    spread_pct = (spread / real_mid * 100) if spread and real_mid else None

    synthetic_vol = solve_implied_vol_from_price(t["entry_premium"], entry_spot, strike, dte, "call") if entry_spot else None
    iv_corrected_price = black_scholes_price(entry_spot, strike, dte, real_iv, 0.04, "call") if (entry_spot and real_iv) else None

    print("=" * 90)
    print(ticker + " " + entry_date_str + " -- contract=" + real_entry.get("contract", "N/A"))
    print("=" * 90)
    print("Strike: synthetic_target=" + str(strike) + " real=" + str(real_entry.get("strike")) + " | DTE: target=14 actual=" + str(actual_dte))
    print("Underlying price: $" + str(entry_spot))
    print("Volatility: our_synthetic(back-solved)=" + str(round(synthetic_vol,4) if synthetic_vol else None) + " real_historical_IV=" + str(real_iv))
    print("Prices: original_synthetic=$" + str(round(t["entry_premium"],3)) + " IV_corrected=$" + str(round(iv_corrected_price,3) if iv_corrected_price else None) + " real_bid=$" + str(real_bid) + " real_ask=$" + str(real_ask) + " real_mid=$" + str(real_mid))
    print("Liquidity: volume=" + str(volume) + " OI=" + str(oi) + " spread_pct=" + str(round(spread_pct,1) if spread_pct else None) + "%")

    category = "GENUINELY UNEXPLAINED"
    if oi is not None and oi < 20:
        category = "LOW OI (borderline illiquidity, below the 0-OI hard cutoff used earlier)"
    elif spread_pct is not None and spread_pct > 30:
        category = "WIDE SPREAD (30-50% range, below the 50% hard cutoff used earlier)"
    elif actual_dte is not None and abs(actual_dte - 14) > 3:
        category = "DTE MISMATCH (actual DTE notably far from 14-day target)"
    elif real_iv is not None and (real_iv > 1.5 or real_iv < 0.05):
        category = "EXTREME IV VALUE (possible data-quality issue in the IV field itself)"

    print("CATEGORY: " + category)
    print()

print("TARGETED RESIDUAL INVESTIGATION COMPLETE.")
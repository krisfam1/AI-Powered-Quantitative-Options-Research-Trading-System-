from dotenv import load_dotenv
load_dotenv()

"""
Resumable completion of Phase 2. Checks the existing
iv_correction_diagnostic.db for already-saved trades, regenerates the
local 126-trade sample (free), and fetches ONLY what's still missing.
"""

import os
import sqlite3
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
DB_PATH = "iv_correction_diagnostic.db"


def fetch_real_contract_near_strike(ticker, date_str, target_strike, option_type="call", target_dte=14):
    obs_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    params = {
        "filter[underlying_symbol]": ticker, "filter[tradetime_from]": date_str, "filter[tradetime_to]": date_str,
        "filter[exp_date_from]": obs_date.isoformat(), "filter[exp_date_to]": (obs_date + timedelta(days=45)).isoformat(),
        "api_token": EODHD_API_TOKEN, "page[limit]": 1000,
    }
    resp = requests.get(BASE_URL, params=params, timeout=90)
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


with sqlite3.connect(DB_PATH) as conn:
    already_saved = set(conn.execute("SELECT ticker, entry_date FROM diagnostic").fetchall())
print("Already saved: " + str(len(already_saved)) + " trades\n")

print("Regenerating the local 126-trade sample (free, no API cost)...\n")
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

missing = [t for t in sample if (t["_ticker"], str(t["entry_date"])) not in already_saved]
print("Missing (still need fetching): " + str(len(missing)) + " trades\n")

fetched = 0
skipped = 0
with sqlite3.connect(DB_PATH) as conn:
    for t in missing:
        ticker = t["_ticker"]
        entry_date_str = str(t["entry_date"])
        strike = t["strike"]
        dte = 14

        try:
            real_entry = fetch_real_contract_near_strike(ticker, entry_date_str, strike)
        except Exception as e:
            print("  Fetch error for " + ticker + " " + entry_date_str + ": " + str(e) + " -- will need another pass")
            continue

        if real_entry is None:
            skipped += 1
            continue

        day_bars = bars_by_ticker_date.get((ticker, entry_date_str))
        entry_spot = float(day_bars[-1].close) if day_bars else None
        real_iv = real_entry.get("volatility")
        real_mid = real_entry.get("midpoint")
        if entry_spot is None or real_iv is None or real_mid is None:
            skipped += 1
            continue

        synthetic_vol = solve_implied_vol_from_price(t["entry_premium"], entry_spot, strike, dte, "call")
        iv_corrected_price = black_scholes_price(entry_spot, strike, dte, real_iv, 0.04, "call")
        orig_pct_err = abs(t["entry_premium"] - real_mid) / real_mid * 100
        corrected_pct_err = abs(iv_corrected_price - real_mid) / real_mid * 100

        conn.execute(
            "INSERT OR REPLACE INTO diagnostic (ticker, entry_date, contract, option_type, target_strike, real_strike, expiration, target_dte, actual_dte, historical_iv, realized_vol, original_price, iv_corrected_price, real_bid, real_ask, real_midpoint, volume, open_interest, orig_pct_err, corrected_pct_err) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ticker, entry_date_str, real_entry.get("contract"), "call", strike, real_entry.get("strike"),
             real_entry.get("exp_date"), 14, real_entry.get("_actual_dte"), real_iv, round(synthetic_vol, 4),
             round(t["entry_premium"], 3), round(iv_corrected_price, 3), real_entry.get("bid"), real_entry.get("ask"),
             real_mid, real_entry.get("volume"), real_entry.get("open_interest"),
             round(orig_pct_err, 2), round(corrected_pct_err, 2))
        )
        fetched += 1
        if fetched % 10 == 0:
            conn.commit()
            print("  ... " + str(fetched) + " more saved")
    conn.commit()

print("\nThis pass: " + str(fetched) + " newly saved, " + str(skipped) + " skipped (no valid data)")

with sqlite3.connect(DB_PATH) as conn:
    total = conn.execute("SELECT COUNT(*) FROM diagnostic").fetchone()[0]
print("Total in database now: " + str(total) + " / 126")
from dotenv import load_dotenv
load_dotenv()

"""
Full-population historical-IV repricing for all 251 V1 trades.
RESUMABLE: saves each trade's repricing to a local database as it
completes, so a network interruption doesn't lose progress. Re-running
this script skips already-completed trades automatically.

NOT an attempt to rescue V1. Establishes the most accurate possible
final assessment of historical P&L under realistic pricing.
"""

import os
import sqlite3
import requests
import statistics
from datetime import datetime, timezone, timedelta
from portfolio_backtest import run_portfolio_backtest
from options_backtest_engine import black_scholes_price
from gex_data_loader import get_previous_trading_day

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
DB_PATH = "full_iv_repricing.db"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS repriced_trades (
                ticker TEXT, entry_date TEXT, strike REAL,
                synthetic_pnl REAL, synthetic_return_pct REAL,
                iv_repriced_return_pct REAL, entry_iv REAL, exit_iv REAL,
                underlying_move_pct REAL, contracts INTEGER,
                iv_repriced_pnl REAL,
                UNIQUE(ticker, entry_date, strike)
            )
        """)


def fetch_real_iv(ticker, date_str, target_strike, target_dte=14):
    obs_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    params = {
        "filter[underlying_symbol]": ticker, "filter[tradetime_from]": date_str, "filter[tradetime_to]": date_str,
        "filter[exp_date_from]": obs_date.isoformat(), "filter[exp_date_to]": (obs_date + timedelta(days=45)).isoformat(),
        "api_token": EODHD_API_TOKEN, "page[limit]": 1000,
    }
    for attempt in range(3):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=60)
            resp.raise_for_status()
            break
        except requests.exceptions.RequestException:
            if attempt == 2:
                return None
            import time
            time.sleep(2)
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


def solve_spot(target, strike, dte, vol):
    low, high = 1.0, 5000.0
    for _ in range(100):
        mid = (low + high) / 2
        price = black_scholes_price(mid, strike, dte, vol, option_type="call")
        if price < target:
            low = mid
        else:
            high = mid
        if abs(high - low) < 0.001:
            break
    return (low + high) / 2


BRACKETS = [(5.0, 0.02), (2.0, 0.04), (1.0, 0.07), (0.0, 0.12)]
def recover_raw(p):
    for th, sp in BRACKETS:
        mult = 1 + sp / 2
        cand = p / mult
        if cand >= th:
            return cand
    return p / 1.06


print("Reproducing frozen V1 baseline...\n")
v1_results = {}
for ticker in TICKERS:
    v1_results[ticker] = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v1")

all_trades_raw = [t for tk in TICKERS for t in v1_results[tk]["closed_trades"]]
total_pnl_check = sum(t["pnl_dollars"] for t in all_trades_raw)
print("Reproduced: $" + str(round(total_pnl_check,2)) + ", n=" + str(len(all_trades_raw)))
if abs(total_pnl_check - 20427.64) > 0.01 or len(all_trades_raw) != 251:
    print("*** DISCREPANCY -- STOPPING ***")
    exit()
print("Reproduction confirmed.\n")

init_db()
with sqlite3.connect(DB_PATH) as conn:
    already_done = set(conn.execute("SELECT ticker, entry_date, strike FROM repriced_trades").fetchall())
print("Already repriced: " + str(len(already_done)) + " / 251\n")

enriched_trades = []
for ticker in TICKERS:
    ground_truth = {(g["ticker"], g["entry_date"], round(g["strike"],2)): g for g in v1_results[ticker]["v1_ground_truth_log"]}
    for t in v1_results[ticker]["closed_trades"]:
        key = (ticker, t["entry_date"], round(t["strike"],2))
        gt = ground_truth.get(key)
        if gt is None:
            continue
        enriched_trades.append({**t, "ticker": ticker, "v1_vol": gt["v1_realized_vol"]})

remaining = [t for t in enriched_trades if (t["ticker"], str(t["entry_date"]), round(t["strike"],2)) not in already_done]
print("Remaining to process: " + str(len(remaining)) + "\n")

processed = 0
skipped = 0
with sqlite3.connect(DB_PATH) as conn:
    for t in remaining:
        ticker = t["ticker"]
        strike = t["strike"]
        dte_target = 14

        entry_t_minus_1 = get_previous_trading_day(t["entry_date"], reference_ticker=ticker)
        entry_iv = fetch_real_iv(ticker, entry_t_minus_1.isoformat(), strike, dte_target)

        exit_dte = max((t["expiry_date"] - t["exit_date"]).days, 1)
        exit_t_minus_1 = get_previous_trading_day(t["exit_date"], reference_ticker=ticker)
        exit_iv = fetch_real_iv(ticker, exit_t_minus_1.isoformat(), strike, exit_dte)

        if entry_iv is None or exit_iv is None:
            skipped += 1
            print(ticker + " " + str(t["entry_date"]) + ": IV unavailable -- skipped")
            continue

        raw_entry = recover_raw(t["entry_premium"])
        entry_spot = solve_spot(raw_entry, strike, dte_target, t["v1_vol"])
        exit_spot = solve_spot(t["exit_premium"], strike, exit_dte, t["v1_vol"])

        iv_entry_price = black_scholes_price(entry_spot, strike, dte_target, entry_iv, option_type="call")
        iv_exit_price = black_scholes_price(exit_spot, strike, exit_dte, exit_iv, option_type="call")
        iv_return = (iv_exit_price - iv_entry_price) / iv_entry_price if iv_entry_price else None
        iv_repriced_pnl = (iv_exit_price - iv_entry_price) * t["contracts"] * 100 if iv_return is not None else None

        conn.execute(
            "INSERT OR REPLACE INTO repriced_trades VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ticker, str(t["entry_date"]), strike, t["pnl_dollars"], t["pnl_pct"],
             iv_return*100 if iv_return else None, entry_iv, exit_iv,
             (exit_spot-entry_spot)/entry_spot*100, t["contracts"], iv_repriced_pnl)
        )
        processed += 1
        if processed % 20 == 0:
            conn.commit()
            print("  ... " + str(processed) + " processed this run")
    conn.commit()

print("\nThis run: " + str(processed) + " processed, " + str(skipped) + " skipped (no IV data)")

with sqlite3.connect(DB_PATH) as conn:
    total_done = conn.execute("SELECT COUNT(*) FROM repriced_trades").fetchone()[0]
print("Total in database: " + str(total_done) + " / 251")

if total_done < 251 - skipped:
    print("\nNOT YET COMPLETE -- re-run this script to continue (resumable).")
else:
    print("\nFULL REPRICING COMPLETE. Run the summary script next.")
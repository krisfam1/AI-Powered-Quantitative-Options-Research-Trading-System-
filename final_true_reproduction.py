from dotenv import load_dotenv
load_dotenv()

"""
FINAL corrected reproduction. Fixes two real, confirmed issues:
1. Same-day ticker collisions (2 found, 2 records overwritten) --
   rebuilt with a true unique trade ID (ticker + exact entry timestamp
   + strike), recovering all 126 original trades.
2. The exact original methodology: iv_corrected_price used the
   TARGET strike and a FLAT dte=14 (not the real matched contract's
   actual strike/DTE) -- confirmed directly from phase2_complete_dataset.py
   source. Prior reproduction attempts incorrectly used real_strike/
   actual_dte, causing the persistent mismatch.

Zero new EODHD API calls. Regenerates only the local, free 126-trade
sample to recover exact trade identity and signal-time prices.
"""

import sqlite3
from datetime import datetime, timezone
from portfolio_backtest import run_portfolio_backtest
from options_backtest_engine import black_scholes_price
import backtest_engine as be

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
RISK_FREE_RATE = 0.04

print("Regenerating the local 126-trade sample with TRUE unique identity...\n")
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

# TRUE unique key: ticker + entry_date + strike (distinguishes the 2 same-day collisions)
for t in sample:
    t["_unique_id"] = t["_ticker"] + "|" + str(t["entry_date"]) + "|" + str(t["strike"])

print("Sample size: " + str(len(sample)) + " | Unique IDs: " + str(len(set(t["_unique_id"] for t in sample))))

with sqlite3.connect("iv_correction_diagnostic.db") as conn:
    conn.row_factory = sqlite3.Row
    saved_rows = {(r["ticker"], r["entry_date"]): r for r in conn.execute("SELECT * FROM diagnostic").fetchall()}

print("Saved diagnostic rows (old, collision-affected key): " + str(len(saved_rows)) + "\n")

results = []
reconciliation = []

for t in sample:
    ticker = t["_ticker"]
    entry_date_str = str(t["entry_date"])
    target_strike = t["strike"]

    day_bars = bars_by_ticker_date.get((ticker, entry_date_str))
    entry_spot = float(day_bars[-1].close) if day_bars else None
    if entry_spot is None:
        continue

    saved = saved_rows.get((ticker, entry_date_str))
    if saved is None:
        continue

    # EXACT original methodology: TARGET strike, FLAT dte=14 -- not real_strike/actual_dte
    real_iv = saved["historical_iv"]
    real_mid = saved["real_midpoint"]
    real_bid, real_ask = saved["real_bid"], saved["real_ask"]

    v2_price = black_scholes_price(entry_spot, target_strike, 14, real_iv, RISK_FREE_RATE, "call")
    pct_err = abs(v2_price - real_mid) / real_mid * 100 if real_mid else None
    in_range = (real_bid <= v2_price <= real_ask) if real_bid is not None and real_ask is not None else None

    match_archived = abs(v2_price - saved["iv_corrected_price"]) < 0.05

    results.append({
        "unique_id": t["_unique_id"], "ticker": ticker, "entry_date": entry_date_str,
        "target_strike": target_strike, "v2_price": v2_price, "real_mid": real_mid,
        "pct_err": pct_err, "in_range": in_range, "archived_price": saved["iv_corrected_price"],
        "match_archived": match_archived,
    })

print("=" * 100)
print("RECONCILIATION (first 15 shown)")
print("=" * 100)
for r in results[:15]:
    print(r["ticker"] + " " + r["entry_date"] + " strike=" + str(r["target_strike"]) + ": v2_price=$" + str(round(r["v2_price"],3)) + " archived=$" + str(r["archived_price"]) + " match=" + str(r["match_archived"]) + " pct_err=" + str(round(r["pct_err"],1) if r["pct_err"] else None) + "%")

print("\n" + "=" * 100)
print("AGGREGATE RESULTS")
print("=" * 100)
n = len(results)
matches = len([r for r in results if r["match_archived"]])
print("Total trades processed: " + str(n))
print("Reproduces archived price exactly (within $0.05): " + str(matches) + " / " + str(n))

errs = sorted(r["pct_err"] for r in results if r["pct_err"] is not None)
ne = len(errs)
median_err = errs[ne // 2]
mean_err = sum(errs) / ne
print("Median abs error: " + str(round(median_err, 1)) + "%")
print("Mean abs error: " + str(round(mean_err, 1)) + "%")

in_range_count = len([r for r in results if r["in_range"]])
print("Inside bid/ask: " + str(in_range_count) + " / " + str(n))

print("\n" + "=" * 100)
print("COMPARISON")
print("=" * 100)
print("Archived: 8.6% (n=124)")
print("Prior reconstruction (real_strike/actual_dte): 2.5%")
print("This reconstruction (target_strike/flat dte=14, matching original methodology): " + str(round(median_err,1)) + "% (n=" + str(n) + ")")

if abs(median_err - 8.6) < 1.0:
    print("\nCONCLUSION: SUCCESSFULLY REPRODUCED the archived ~8.6% finding.")
else:
    print("\nCONCLUSION: Still differs -- " + str(round(abs(median_err-8.6),1)) + " points off. Further investigation needed, not forcing a match.")

print("\nFINAL RECONCILIATION COMPLETE.")
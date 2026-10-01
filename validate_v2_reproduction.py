from dotenv import load_dotenv
load_dotenv()

"""
Validates that the newly-built, properly-versioned V2 module reproduces
the previously observed ~8.6% median error. Runs V2 fresh (real API
calls, real contract selection, real logging) on a representative
subset, reusing (ticker, date, target_strike) identity already known
from the saved iv_correction_diagnostic.db. Underlying price is
re-fetched from Alpaca (free, no EODHD cost) since it wasn't saved
directly in the original database.
"""

import sqlite3
from datetime import datetime, timezone
import backtest_engine as be
from v2_iv_pricing_model import calculate_v2_price

SOURCE_DB = "iv_correction_diagnostic.db"

with sqlite3.connect(SOURCE_DB) as conn:
    conn.row_factory = sqlite3.Row
    all_rows = conn.execute("SELECT * FROM diagnostic").fetchall()

subset = all_rows[::6]
print("Validation subset size: " + str(len(subset)) + " (every 6th trade from the complete 124-trade dataset)\n")

results = []
for row in subset:
    ticker = row["ticker"]
    signal_date = row["entry_date"]
    target_strike = row["target_strike"]

    from datetime import timedelta
    obs_dt = datetime.strptime(signal_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    bars = be.get_historical_bars(ticker, obs_dt, obs_dt + timedelta(days=1))
    if not bars:
        from datetime import timedelta
        bars = be.get_historical_bars(ticker, obs_dt, obs_dt + timedelta(days=1))
    if not bars:
        print(ticker + " " + signal_date + ": no Alpaca bars found -- skipping")
        continue
    underlying_price = float(bars[-1].close)

    v2_result = calculate_v2_price(ticker, signal_date, target_strike, underlying_price, "call", 14)
    if v2_result is None:
        print(ticker + " " + signal_date + ": V2 found no valid real contract -- skipping (honest, not fabricated)")
        continue

    # Cross-check against the already-saved value for this exact trade
    saved_iv_price = row["iv_corrected_price"]
    saved_mid = row["real_midpoint"]
    v2_price = v2_result["calculated_price"]
    v2_pct_err = abs(v2_price - saved_mid) / saved_mid * 100 if saved_mid else None

    match = abs(v2_price - saved_iv_price) < 0.05 if saved_iv_price else None

    print(ticker + " " + signal_date + ": V2_price=$" + str(round(v2_price,3)) + " saved_price=$" + str(round(saved_iv_price,3) if saved_iv_price else None) + " match=" + str(match) + " V2_pct_err_vs_real=" + str(round(v2_pct_err,1) if v2_pct_err else None) + "%")

    results.append({"pct_err": v2_pct_err, "match": match})

print("\n" + "=" * 90)
print("VALIDATION SUMMARY")
print("=" * 90)
n = len(results)
matches = len([r for r in results if r["match"]])
print("Trades processed: " + str(n))
print("Reproduced saved value exactly (within $0.05): " + str(matches) + " / " + str(n))

errs = sorted(r["pct_err"] for r in results if r["pct_err"] is not None)
if errs:
    ne = len(errs)
    print("V2 median abs error vs real market: " + str(round(errs[ne//2], 1)) + "%")
    print("(Compare against the previously observed ~8.6% median on the full 124-trade dataset)")

print("\nVALIDATION COMPLETE.")
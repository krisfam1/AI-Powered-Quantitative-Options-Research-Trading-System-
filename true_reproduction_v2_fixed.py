from dotenv import load_dotenv
load_dotenv()

"""
TRUE reproduction of the archived 8.6% median error result -- CORRECTED
approach. entry_date in closed_trades is date-only (no time component),
so exact-timestamp bar matching is genuinely impossible with that data.

Instead: back-solves the ORIGINAL underlying price V1 used, from the
already-saved original_price and realized_vol (Black-Scholes is
monotonic in spot for calls, making this a valid, unique recovery).
ZERO new EODHD API calls, ZERO backtest regeneration needed -- uses
only the already-saved iv_correction_diagnostic.db.
"""

import sqlite3
from options_backtest_engine import black_scholes_price

RISK_FREE_RATE = 0.04


def solve_spot_from_price(target_price, strike, dte, vol, option_type="call", risk_free_rate=0.04):
    low, high = 1.0, 5000.0
    for _ in range(100):
        mid = (low + high) / 2
        price = black_scholes_price(mid, strike, dte, vol, risk_free_rate, option_type)
        if price < target_price:
            low = mid
        else:
            high = mid
        if abs(high - low) < 0.001:
            break
    return (low + high) / 2


with sqlite3.connect("iv_correction_diagnostic.db") as conn:
    conn.row_factory = sqlite3.Row
    saved_rows = conn.execute("SELECT * FROM diagnostic").fetchall()

print("Saved diagnostic rows: " + str(len(saved_rows)) + "\n")

results = []
for r in saved_rows:
    original_spot = solve_spot_from_price(r["original_price"], r["target_strike"], r["target_dte"], r["realized_vol"])

    real_strike = r["real_strike"]
    real_iv = r["historical_iv"]
    actual_dte = r["actual_dte"]
    real_mid = r["real_midpoint"]
    real_bid, real_ask = r["real_bid"], r["real_ask"]

    v2_price = black_scholes_price(original_spot, real_strike, actual_dte, real_iv, RISK_FREE_RATE, "call")
    pct_err = abs(v2_price - real_mid) / real_mid * 100 if real_mid else None
    in_range = (real_bid <= v2_price <= real_ask) if real_bid is not None and real_ask is not None else None

    results.append({
        "ticker": r["ticker"], "entry_date": r["entry_date"], "original_spot": original_spot,
        "v2_price": v2_price, "real_mid": real_mid, "pct_err": pct_err, "in_range": in_range,
        "archived_iv_price": r["iv_corrected_price"],
    })

print("=" * 100)
print("PER-TRADE RESULTS (first 15 shown)")
print("=" * 100)
for r in results[:15]:
    print(r["ticker"] + " " + r["entry_date"] + ": recovered_spot=$" + str(round(r["original_spot"],2)) + " v2_price=$" + str(round(r["v2_price"],3)) + " real_mid=$" + str(r["real_mid"]) + " pct_err=" + str(round(r["pct_err"],1) if r["pct_err"] else None) + "% archived_price=$" + str(r["archived_iv_price"]))

print("\n" + "=" * 100)
print("AGGREGATE RESULTS")
print("=" * 100)
n = len(results)
errs = sorted(r["pct_err"] for r in results if r["pct_err"] is not None)
ne = len(errs)
median_err = errs[ne // 2]
mean_err = sum(errs) / ne
print("Complete trades: " + str(n))
print("Median abs error: " + str(round(median_err, 1)) + "%")
print("Mean abs error: " + str(round(mean_err, 1)) + "%")

in_range_count = len([r for r in results if r["in_range"]])
print("Inside bid/ask: " + str(in_range_count) + " / " + str(n))

within5 = len([e for e in errs if e <= 5])
within10 = len([e for e in errs if e <= 10])
within20 = len([e for e in errs if e <= 20])
print("Within 5%/10%/20%: " + str(within5) + "/" + str(within10) + "/" + str(within20) + " (of " + str(n) + ")")

# Cross-check: how many EXACTLY match the archived iv_corrected_price (should be ~all, since this recovers the same inputs)
close_matches = len([r for r in results if abs(r["v2_price"] - r["archived_iv_price"]) < 0.05])
print("\nReproduces archived iv_corrected_price exactly (within $0.05): " + str(close_matches) + " / " + str(n))

print("\n" + "=" * 100)
print("COMPARISON TO ARCHIVED RESULT")
print("=" * 100)
print("Archived median: 8.6% (n=124)")
print("Reproduced median: " + str(round(median_err, 1)) + "% (n=" + str(n) + ")")
print("Difference: " + str(round(abs(median_err - 8.6), 2)) + " percentage points")

if abs(median_err - 8.6) < 1.0:
    print("\nCONCLUSION: Reproduction CONFIRMS the archived ~8.6% finding.")
else:
    print("\nCONCLUSION: Reproduction DIFFERS from the archived result -- investigate, do not force a match.")

print("\nTRUE REPRODUCTION (CORRECTED METHOD) COMPLETE.")
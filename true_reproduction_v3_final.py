from dotenv import load_dotenv
load_dotenv()

"""
FINAL, properly-corrected reproduction. Inverts the exact original
pricing equation:
  saved_price = raw_black_scholes_price * (1 + spread_pct(raw_price) / 2)
where spread_pct is a step function of the RAW (pre-adjustment) price:
>=5.0 -> 2%, >=2.0 -> 4%, >=1.0 -> 7%, else -> 12%.

Recovers raw_price via self-consistent bracket search (the multiplier
depends on the unknown raw price, not the known saved price), then
back-solves the true original signal-time spot from THAT raw price
(not the spread-adjusted saved price, correcting the prior attempt's
flaw). Zero new EODHD API calls -- uses only the saved diagnostic DB.
"""

import sqlite3
from options_backtest_engine import black_scholes_price

RISK_FREE_RATE = 0.04

BRACKETS = [(5.0, 0.02), (2.0, 0.04), (1.0, 0.07), (0.0, 0.12)]


def recover_raw_price(saved_price):
    """Self-consistent inversion: try each bracket's multiplier, keep the one where the resulting raw_price actually falls in that bracket."""
    for threshold, spread_pct in BRACKETS:
        multiplier = 1 + spread_pct / 2
        candidate_raw = saved_price / multiplier
        if candidate_raw >= threshold:
            return candidate_raw
    return saved_price / 1.06  # fallback, lowest bracket


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
    saved_original_price = r["original_price"]
    raw_price = recover_raw_price(saved_original_price)
    original_spot = solve_spot_from_price(raw_price, r["target_strike"], r["target_dte"], r["realized_vol"])

    check_spread_pct = next(sp for th, sp in BRACKETS if raw_price >= th)
    check_saved = raw_price * (1 + check_spread_pct / 2)
    consistency_ok = abs(check_saved - saved_original_price) < 0.01

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
        "raw_price": raw_price, "consistency_ok": consistency_ok,
        "v2_price": v2_price, "real_mid": real_mid, "pct_err": pct_err, "in_range": in_range,
        "archived_iv_price": r["iv_corrected_price"],
    })

inconsistent = [r for r in results if not r["consistency_ok"]]
print("Self-consistency check: " + str(len(results) - len(inconsistent)) + " / " + str(len(results)) + " passed\n")
if inconsistent:
    print("INCONSISTENT recoveries (should be 0 or very few): " + str(len(inconsistent)))

print("=" * 100)
print("PER-TRADE RESULTS (first 15 shown)")
print("=" * 100)
for r in results[:15]:
    print(r["ticker"] + " " + r["entry_date"] + ": recovered_spot=$" + str(round(r["original_spot"],2)) + " raw_price=$" + str(round(r["raw_price"],3)) + " v2_price=$" + str(round(r["v2_price"],3)) + " real_mid=$" + str(r["real_mid"]) + " pct_err=" + str(round(r["pct_err"],1) if r["pct_err"] else None) + "%")

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
    print("\nCONCLUSION: Reproduction DIFFERS from the archived result -- investigate further, do not force a match.")

print("\nFINAL CORRECTED REPRODUCTION COMPLETE.")
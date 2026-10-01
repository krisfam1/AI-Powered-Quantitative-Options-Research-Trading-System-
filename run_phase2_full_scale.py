from dotenv import load_dotenv
load_dotenv()

"""
Phase 2, full-scale run: computes GEX metrics for every ticker-day
already validated by Phase 1's data loader. Produces a complete audit.

METHODOLOGY NOTE (per review): Method B (true zero-gamma) is the
PRIMARY gamma-flip measure going forward. Method A (cumulative strike
transition) is retained ONLY as a diagnostic/research comparison, not
used as a primary feature unless explicitly authorized later.

HONEST LABELING (per review): Net GEX magnitude is internally consistent
with the calculation/data but has NOT been independently benchmarked
against a third-party source. Call/put wall proximity to spot is an
internal sanity check only, NOT evidence these levels function as real
support/resistance.

Does NOT touch the frozen baseline, run forward-return analysis, or
connect GEX to the trading signal in any way.
"""

import sqlite3
import statistics
from gex_calculator import calculate_gex_for_ticker_day, DB_PATH

with sqlite3.connect(DB_PATH) as conn:
    ticker_days = conn.execute(
        "SELECT DISTINCT ticker, snapshot_date FROM cleaned_snapshot ORDER BY ticker, snapshot_date"
    ).fetchall()

print("=" * 80)
print("PHASE 2 FULL-SCALE RUN -- " + str(len(ticker_days)) + " ticker-days from Phase 1's validated dataset")
print("=" * 80)

all_results = []
failures = []

for ticker, date_str in ticker_days:
    try:
        results = calculate_gex_for_ticker_day(ticker, date_str)
        if not results:
            failures.append({"ticker": ticker, "date": date_str, "reason": "no results (likely missing spot price)"})
        else:
            all_results.extend(results)
            print("  " + ticker + " " + date_str + ": OK (" + str(results[0]["contracts_used"]) + " contracts)")
    except Exception as exc:
        failures.append({"ticker": ticker, "date": date_str, "reason": str(exc)})
        print("  " + ticker + " " + date_str + ": FAILED -- " + str(exc))

model_a_results = [r for r in all_results if r["sign_convention"] == "model_a"]
flipped_results = [r for r in all_results if r["sign_convention"] == "flipped"]

print("\n" + "=" * 80)
print("AUDIT: TICKER-DAYS")
print("=" * 80)
print("Total ticker-days in Phase 1 dataset: " + str(len(ticker_days)))
print("Successful calculations: " + str(len(ticker_days) - len(failures)))
print("Failed calculations: " + str(len(failures)))
if failures:
    for f in failures:
        print("  FAILED: " + f["ticker"] + " " + f["date"] + " -- " + f["reason"])

print("\n" + "=" * 80)
print("AUDIT: CONTRACTS, CALLS/PUTS, COVERAGE (model_a rows -- identical contract counts for flipped)")
print("=" * 80)
contract_counts = [r["contracts_used"] for r in model_a_results]
calls_counts = [r["calls_used"] for r in model_a_results]
puts_counts = [r["puts_used"] for r in model_a_results]
print("Contracts per ticker-day: min=" + str(min(contract_counts)) + " max=" + str(max(contract_counts)) + " mean=" + str(round(statistics.mean(contract_counts), 1)))
print("Total calls used (summed): " + str(sum(calls_counts)))
print("Total puts used (summed): " + str(sum(puts_counts)))
print("(Both OI and gamma coverage were already confirmed 100% in Phase 1 -- calculate_gex_for_ticker_day only counts contracts where both are present)")

print("\n" + "=" * 80)
print("AUDIT: NET GEX DISTRIBUTION (both sign conventions)")
print("=" * 80)
for label, results in [("model_a", model_a_results), ("flipped", flipped_results)]:
    values = [r["net_gex"] for r in results]
    print(label + ": min=$" + str(round(min(values), 0)) + " max=$" + str(round(max(values), 0)) + " mean=$" + str(round(statistics.mean(values), 0)) + " median=$" + str(round(statistics.median(values), 0)))

print("\n" + "=" * 80)
print("AUDIT: GEX REGIME DISTRIBUTION")
print("=" * 80)
for label, results in [("model_a", model_a_results), ("flipped", flipped_results)]:
    pos = len([r for r in results if r["gex_regime"] == "positive"])
    neg = len([r for r in results if r["gex_regime"] == "negative"])
    print(label + ": positive=" + str(pos) + " negative=" + str(neg) + " (of " + str(len(results)) + ")")

print("\n" + "=" * 80)
print("AUDIT: METHOD B (true zero-gamma, PRIMARY measure) -- availability and distribution")
print("=" * 80)
method_b_available = [r for r in model_a_results if r["true_zero_gamma_price"] is not None]
method_b_missing = [r for r in model_a_results if r["true_zero_gamma_price"] is None]
print("Available: " + str(len(method_b_available)) + " / " + str(len(model_a_results)))
print("Missing/no crossing found: " + str(len(method_b_missing)))
if method_b_available:
    values = [r["true_zero_gamma_price"] for r in method_b_available]
    spot_values = [r["spot_price"] for r in method_b_available]
    pct_from_spot = [(v - s) / s * 100 for v, s in zip(values, spot_values)]
    print("Distance from spot: min=" + str(round(min(pct_from_spot), 1)) + "% max=" + str(round(max(pct_from_spot), 1)) + "% mean=" + str(round(statistics.mean(pct_from_spot), 1)) + "%")
if method_b_missing:
    for r in method_b_missing:
        print("  MISSING: " + r["ticker"] + " " + r["snapshot_date"] + " -- " + str(r["true_zero_gamma_note"]))

print("\n" + "=" * 80)
print("AUDIT: METHOD A (cumulative strike transition, DIAGNOSTIC ONLY) -- for comparison")
print("=" * 80)
method_a_available = [r for r in model_a_results if r["cumulative_strike_transition_price"] is not None]
print("Available: " + str(len(method_a_available)) + " / " + str(len(model_a_results)))
if method_a_available:
    values = [r["cumulative_strike_transition_price"] for r in method_a_available]
    spot_values = [r["spot_price"] for r in method_a_available]
    pct_from_spot_a = [(v - s) / s * 100 for v, s in zip(values, spot_values)]
    print("Distance from spot: min=" + str(round(min(pct_from_spot_a), 1)) + "% max=" + str(round(max(pct_from_spot_a), 1)) + "% mean=" + str(round(statistics.mean(pct_from_spot_a), 1)) + "%")
    implausible_a = len([p for p in pct_from_spot_a if abs(p) > 50])
    print("Results >50% from spot (implausible, consistent with the AAPL 7/15 finding): " + str(implausible_a) + " / " + str(len(method_a_available)))
print("REMINDER: Method A is diagnostic only, not the primary gamma-flip feature.")

print("\n" + "=" * 80)
print("AUDIT: CALL WALL / PUT WALL")
print("=" * 80)
call_wall_available = [r for r in model_a_results if r["call_wall_strike"] is not None]
put_wall_available = [r for r in model_a_results if r["put_wall_strike"] is not None]
print("Call wall available: " + str(len(call_wall_available)) + " / " + str(len(model_a_results)))
print("Put wall available: " + str(len(put_wall_available)) + " / " + str(len(model_a_results)))
if call_wall_available:
    dist = [(r["call_wall_strike"] - r["spot_price"]) / r["spot_price"] * 100 for r in call_wall_available]
    print("Call wall distance from spot: mean=" + str(round(statistics.mean(dist), 1)) + "% (internal sanity check only -- NOT evidence of support/resistance function)")
if put_wall_available:
    dist = [(r["put_wall_strike"] - r["spot_price"]) / r["spot_price"] * 100 for r in put_wall_available]
    print("Put wall distance from spot: mean=" + str(round(statistics.mean(dist), 1)) + "% (internal sanity check only -- NOT evidence of support/resistance function)")

print("\n" + "=" * 80)
print("AUDIT: GAMMA GRADIENT")
print("=" * 80)
gradient_available = [r for r in model_a_results if r["gamma_gradient_at_spot"] is not None]
print("Available: " + str(len(gradient_available)) + " / " + str(len(model_a_results)))
if gradient_available:
    values = [r["gamma_gradient_at_spot"] for r in gradient_available]
    print("Distribution: min=$" + str(round(min(values), 0)) + " max=$" + str(round(max(values), 0)) + " mean=$" + str(round(statistics.mean(values), 0)))

print("\n" + "=" * 80)
print("AUDIT: EXTREME/OUTLIER NET GEX VALUES (beyond 2 std dev from mean, model_a)")
print("=" * 80)
values = [r["net_gex"] for r in model_a_results]
mean_v, std_v = statistics.mean(values), statistics.stdev(values)
outliers = [r for r in model_a_results if abs(r["net_gex"] - mean_v) > 2 * std_v]
print("Outliers found: " + str(len(outliers)))
for r in outliers:
    print("  " + r["ticker"] + " " + r["snapshot_date"] + ": Net GEX=$" + str(round(r["net_gex"], 0)))

print("\n" + "=" * 80)
print("DETERMINISM / REPRODUCIBILITY CHECK")
print("=" * 80)
if ticker_days:
    check_ticker, check_date = ticker_days[0]
    run1 = calculate_gex_for_ticker_day(check_ticker, check_date)
    run2 = calculate_gex_for_ticker_day(check_ticker, check_date)
    match = all(
        run1[i]["net_gex"] == run2[i]["net_gex"] and run1[i]["true_zero_gamma_price"] == run2[i]["true_zero_gamma_price"]
        for i in range(len(run1))
    )
    print(check_ticker + " " + check_date + " recomputed twice: identical results = " + str(match))

print("\n" + "=" * 80)
print("PHASE 2 FULL-SCALE AUDIT COMPLETE -- STOPPING per instruction, awaiting review before Phase 3 (gex_lookup.py)")
print("=" * 80)
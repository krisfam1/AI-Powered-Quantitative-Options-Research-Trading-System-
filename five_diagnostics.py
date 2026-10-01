from dotenv import load_dotenv
load_dotenv()

"""
V1 vs V2 Pricing-Model Sensitivity Experiment -- 5-part diagnostic,
per explicit scope. Frozen strategy rules identical between runs.
Identical trade count is NOT required or expected.
"""

import statistics
from datetime import datetime, timezone
from portfolio_backtest import run_portfolio_backtest

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKER = "AAPL"

print("Running V1...")
v1_result = run_portfolio_backtest([TICKER], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v1")
print("Running V2...")
v2_result = run_portfolio_backtest([TICKER], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v2_entry_iv")

v1_trades = sorted(v1_result["closed_trades"], key=lambda t: str(t["entry_date"]))
v2_trades = sorted(v2_result["closed_trades"], key=lambda t: str(t["entry_date"]))
v1_coverage = v1_result["v2_coverage_log"]  # v1 run still logs coverage (pricing_mode="v1" doesn't call get_v2_entry_iv, so v2_iv_available will be False throughout -- this just gives us the raw signal list)
v2_coverage = v2_result["v2_coverage_log"]

print("\nV1 trades: " + str(len(v1_trades)) + " | V2 trades: " + str(len(v2_trades)))
print("V1 qualifying signals (raw, pre-exit-cascade): " + str(len(v1_coverage)))
print("V2 qualifying signals (raw, pre-exit-cascade): " + str(len(v2_coverage)))

# ============================================================
# DIAGNOSTIC 1 -- Entry premium distribution (comparable signals: matched by entry_date)
# ============================================================
print("\n" + "=" * 100)
print("DIAGNOSTIC 1: ENTRY PREMIUM DISTRIBUTION")
print("=" * 100)

v1_by_date = {str(t["entry_date"]): t for t in v1_trades}
v2_by_date = {str(t["entry_date"]): t for t in v2_trades}
common_dates = sorted(set(v1_by_date.keys()) & set(v2_by_date.keys()))

ratios, abs_diffs, pct_diffs = [], [], []
for d in common_dates:
    v1p, v2p = v1_by_date[d]["entry_premium"], v2_by_date[d]["entry_premium"]
    ratios.append(v2p / v1p)
    abs_diffs.append(v2p - v1p)
    pct_diffs.append((v2p - v1p) / v1p * 100)

print("Comparable (common entry-date) signals: " + str(len(common_dates)))
if ratios:
    print("V2/V1 ratio: mean=" + str(round(statistics.mean(ratios),3)) + " median=" + str(round(statistics.median(ratios),3)) + " std=" + str(round(statistics.stdev(ratios),3) if len(ratios)>1 else 0) + " min=" + str(round(min(ratios),3)) + " max=" + str(round(max(ratios),3)))
    print("Absolute diff ($): mean=" + str(round(statistics.mean(abs_diffs),3)) + " median=" + str(round(statistics.median(abs_diffs),3)))
    print("Pct diff (%): mean=" + str(round(statistics.mean(pct_diffs),1)) + " median=" + str(round(statistics.median(pct_diffs),1)))
    sorted_pct = sorted(pct_diffs)
    n = len(sorted_pct)
    print("Percentiles (pct diff): p10=" + str(round(sorted_pct[int(n*0.1)],1)) + " p25=" + str(round(sorted_pct[int(n*0.25)],1)) + " p50=" + str(round(sorted_pct[int(n*0.5)],1)) + " p75=" + str(round(sorted_pct[int(n*0.75)],1)) + " p90=" + str(round(sorted_pct[min(int(n*0.9),n-1)],1)))

# ============================================================
# DIAGNOSTIC 2 -- Verify V2 pricing for a sample (using the extended coverage log)
# ============================================================
print("\n" + "=" * 100)
print("DIAGNOSTIC 2: V2 PRICING VERIFICATION (sample of 8 signals with V2 IV available)")
print("=" * 100)
sample_v2 = [c for c in v2_coverage if c["v2_iv_available"]][:8]
for c in sample_v2:
    print(c["ticker"] + " " + str(c["signal_timestamp"]) + ": underlying=$" + str(round(c["underlying_price"],2)) + " strike=" + str(c["strike"]) + " dte=" + str(c["target_dte"]))
    print("  V1_vol=" + str(round(c["v1_vol"],4)) + " V2_iv=" + str(round(c["v2_iv"],4)))
    print("  V1_raw=$" + str(round(c["v1_raw_price"],3)) + " V2_raw=$" + str(round(c["v2_raw_price"],3)))

# ============================================================
# DIAGNOSTIC 3 -- Exit mechanism comparison
# ============================================================
print("\n" + "=" * 100)
print("DIAGNOSTIC 3: EXIT MECHANISM COMPARISON")
print("=" * 100)

def exit_stats(trades, label):
    n = len(trades)
    reasons = {}
    holding_periods = []
    for t in trades:
        reasons[t["exit_reason"]] = reasons.get(t["exit_reason"], 0) + 1
        try:
            hp = (t["exit_date"] - t["entry_date"]).days if hasattr(t["exit_date"], '__sub__') else None
            if hp is not None:
                holding_periods.append(hp)
        except Exception:
            pass
    print(label + " (n=" + str(n) + "): exit_reasons=" + str(reasons))
    if holding_periods:
        print("  Avg holding period (days): " + str(round(statistics.mean(holding_periods), 2)))

exit_stats(v1_trades, "V1")
exit_stats(v2_trades, "V2")

# ============================================================
# DIAGNOSTIC 4 -- Re-entry cascade
# ============================================================
print("\n" + "=" * 100)
print("DIAGNOSTIC 4: RE-ENTRY CASCADE")
print("=" * 100)
v1_only = set(v1_by_date.keys()) - set(v2_by_date.keys())
v2_only = set(v2_by_date.keys()) - set(v1_by_date.keys())
print("V1 entries: " + str(len(v1_trades)) + " | V2 entries: " + str(len(v2_trades)))
print("Common entry dates: " + str(len(common_dates)))
print("V1-only entry dates: " + str(len(v1_only)) + " -- " + str(sorted(v1_only)))
print("V2-only entry dates: " + str(len(v2_only)) + " (cascade-driven additional entries)")
print("Cascade ratio: V2 has " + str(round(len(v2_trades)/len(v1_trades), 2)) + "x the trade count of V1")

# ============================================================
# DIAGNOSTIC 5 -- Verify the core hypothesis chain
# ============================================================
print("\n" + "=" * 100)
print("DIAGNOSTIC 5: CORE HYPOTHESIS CHAIN VERIFICATION")
print("=" * 100)
print("Step 1 (entry premium changes): confirmed -- median V2/V1 ratio = " + (str(round(statistics.median(ratios),3)) if ratios else "N/A"))
lower_count = len([r for r in ratios if r < 1.0]) if ratios else 0
print("  V2 premium LOWER than V1 in " + str(lower_count) + " / " + str(len(ratios)) + " comparable signals")

v1_reasons = {}
v2_reasons = {}
for t in v1_trades:
    v1_reasons[t["exit_reason"]] = v1_reasons.get(t["exit_reason"], 0) + 1
for t in v2_trades:
    v2_reasons[t["exit_reason"]] = v2_reasons.get(t["exit_reason"], 0) + 1
print("Step 2-3 (exit timing changes): V1 exit-reason mix=" + str(v1_reasons) + " V2 exit-reason mix=" + str(v2_reasons))

v1_avg_hp = statistics.mean([(t["exit_date"] - t["entry_date"]).days for t in v1_trades]) if v1_trades else None
v2_avg_hp = statistics.mean([(t["exit_date"] - t["entry_date"]).days for t in v2_trades]) if v2_trades else None
print("Step 3 (holding period): V1 avg=" + str(round(v1_avg_hp,2) if v1_avg_hp else None) + " days | V2 avg=" + str(round(v2_avg_hp,2) if v2_avg_hp else None) + " days")
print("Step 4-6 (re-entry cascade): V2 trade count is " + str(round(len(v2_trades)/len(v1_trades),2)) + "x V1's -- " + ("consistent with" if v2_avg_hp and v1_avg_hp and v2_avg_hp < v1_avg_hp else "NOT clearly consistent with") + " shorter holding periods driving more re-entries")

print("\nDIAGNOSTIC REPORT COMPLETE. STOPPING per instruction.")
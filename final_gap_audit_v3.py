from dotenv import load_dotenv
load_dotenv()

"""
Final pre-performance gap audit -- v3, using the new entry_date/
exp_date_str fields now stored directly in each gap-log entry
(no fragile joins needed). Also adds defensive error handling for
the forward-search hitting the edge of available data.
"""

import statistics
from datetime import datetime, timezone, timedelta
from portfolio_backtest import run_portfolio_backtest
from v2_iv_pricing_model import get_v2_checkpoint_iv
import backtest_engine as be

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
LARGE_DIFF_THRESHOLD = 0.05


def find_next_available_iv(ticker, contract_symbol, exp_date_str, gap_date, max_forward_days=10):
    """EX-POST DIAGNOSTIC ONLY -- uses future information, never fed back into the backtest."""
    d = gap_date
    for _ in range(max_forward_days):
        d = d + timedelta(days=1)
        try:
            bars = be.get_historical_bars(ticker, datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc), datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1))
        except Exception:
            continue
        if not bars:
            continue
        try:
            result = get_v2_checkpoint_iv(ticker, contract_symbol, exp_date_str, d)
        except Exception:
            continue
        if result is not None:
            return {"date": d, "iv": result["iv"]}
    return None


print("Running corrected V2 (AAPL) to capture the real gap log...\n")
v2 = run_portfolio_backtest(["AAPL"], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v2_corrected")
gap_log = v2["v2_checkpoint_gap_log"]
trades = v2["closed_trades"]

print("1. GAP COUNT")
print("=" * 90)
print("Total gaps: " + str(len(gap_log)))
print("Total V2 trades: " + str(len(trades)))

print("\n2. GAP DISTRIBUTION BY TICKER")
print("=" * 90)
by_ticker = {}
for g in gap_log:
    by_ticker.setdefault(g["ticker"], []).append(g)
for ticker, gaps in by_ticker.items():
    affected_contracts = set(g["contract"] for g in gaps)
    print(ticker + ": " + str(len(gaps)) + " gaps, " + str(len(affected_contracts)) + " affected contracts")

print("\n3 & 4. GAP AGE RELATIVE TO ENTRY (using real entry_date, no join needed)")
print("=" * 90)
age_buckets = {"entry": 0, "1day": 0, "2day": 0, "3plus": 0}
valid_gaps = [g for g in gap_log if g.get("entry_date") is not None]
print("Gaps with entry_date recorded: " + str(len(valid_gaps)) + " / " + str(len(gap_log)))

for g in valid_gaps:
    days_since_entry = (g["checkpoint_date"] - g["entry_date"]).days
    if days_since_entry == 0:
        age_buckets["entry"] += 1
    elif days_since_entry == 1:
        age_buckets["1day"] += 1
    elif days_since_entry == 2:
        age_buckets["2day"] += 1
    else:
        age_buckets["3plus"] += 1
print("Gap age relative to entry: " + str(age_buckets))

print("\n5. GAP CLUSTERING")
print("=" * 90)
sorted_gaps = sorted(gap_log, key=lambda g: (g["contract"], g["checkpoint_date"]))
clusters = []
current_cluster = []
for g in sorted_gaps:
    if current_cluster and current_cluster[-1]["contract"] == g["contract"] and (g["checkpoint_date"] - current_cluster[-1]["checkpoint_date"]).days <= 3:
        current_cluster.append(g)
    else:
        if current_cluster:
            clusters.append(current_cluster)
        current_cluster = [g]
if current_cluster:
    clusters.append(current_cluster)

isolated = len([c for c in clusters if len(c) == 1])
multi_day = len([c for c in clusters if len(c) > 1])
print("Isolated single-day gaps: " + str(isolated))
print("Multi-day consecutive gap clusters: " + str(multi_day))
for c in clusters:
    if len(c) > 1:
        print("  " + c[0]["contract"] + ": " + str([str(g["checkpoint_date"]) for g in c]))

print("\n6. IMPACT ON VALUATION (ex-post diagnostic, NOT used in backtest)")
print("=" * 90)
iv_diffs = []
for g in gap_log:
    exp_date_str = g.get("exp_date_str")
    if exp_date_str is None:
        print("  " + g["contract"] + " " + str(g["checkpoint_date"]) + ": no exp_date_str recorded -- skipping")
        continue
    next_iv_result = find_next_available_iv(g["ticker"], g["contract"], exp_date_str, g["checkpoint_date"])
    if next_iv_result is None:
        print("  " + g["contract"] + " " + str(g["checkpoint_date"]) + ": no next IV found within 10 days (likely near expiry/data edge)")
        continue
    diff = abs(next_iv_result["iv"] - g["carried_forward_iv"])
    iv_diffs.append(diff)
    print("  " + g["contract"] + " " + str(g["checkpoint_date"]) + ": carried=" + str(round(g["carried_forward_iv"],4)) + " next=" + str(round(next_iv_result["iv"],4)) + " (date=" + str(next_iv_result["date"]) + ") diff=" + str(round(diff,4)))

if iv_diffs:
    print("\nMedian abs IV diff: " + str(round(statistics.median(iv_diffs),4)))
    print("Mean abs IV diff: " + str(round(statistics.mean(iv_diffs),4)))
    print("Max diff: " + str(round(max(iv_diffs),4)))
    large_diffs = len([d for d in iv_diffs if d > LARGE_DIFF_THRESHOLD])
    print("Large differences (>" + str(LARGE_DIFF_THRESHOLD) + "): " + str(large_diffs) + " / " + str(len(iv_diffs)))

print("\n8. METHODOLOGY CLASSIFICATION")
print("=" * 90)
if iv_diffs:
    median_diff = statistics.median(iv_diffs)
    large_pct = len([d for d in iv_diffs if d > LARGE_DIFF_THRESHOLD]) / len(iv_diffs) * 100
    if median_diff < 0.02 and large_pct < 10:
        print("CLASSIFICATION: A -- Low-risk data-gap handling suitable to freeze as the V2 methodology")
    elif median_diff < 0.05 and large_pct < 25:
        print("CLASSIFICATION: B -- Potentially material, requires methodological decision before performance testing")
    else:
        print("CLASSIFICATION: C -- Clearly problematic, requires redesign")
else:
    print("Insufficient data to classify (no valid next-IV comparisons found).")

print("\nGAP AUDIT COMPLETE.")
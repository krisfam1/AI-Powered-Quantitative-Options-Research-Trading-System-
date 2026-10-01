from dotenv import load_dotenv
load_dotenv()

"""
Final pre-performance gap audit. Does NOT modify the backtest, strategy,
or methodology. The forward-looking "next available IV" comparison is
an EX-POST DIAGNOSTIC ONLY, using information that would not have been
available at the time -- explicitly never fed back into the actual
backtest or used to alter any trade decision.
"""

import os
import requests
import statistics
from datetime import datetime, timezone, timedelta
from portfolio_backtest import run_portfolio_backtest
from gex_data_loader import get_previous_trading_day
from v2_iv_pricing_model import get_v2_checkpoint_iv
import backtest_engine as be

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
LARGE_DIFF_THRESHOLD = 0.05  # 5 percentage points of IV, stated explicitly


def find_next_available_iv(ticker, contract_symbol, exp_date_str, gap_date, max_forward_days=10):
    """EX-POST DIAGNOSTIC ONLY. Searches FORWARD from gap_date for the next
    real day where this exact contract's IV becomes available. This uses
    information that would not have existed at the time of the gap -- it
    is NEVER used in the actual backtest, only to measure how different
    the carried-forward assumption was from what came next."""
    d = gap_date
    for _ in range(max_forward_days):
        d = d + timedelta(days=1)
        if not be.get_historical_bars(ticker, datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc), datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1)):
            continue
        result = get_v2_checkpoint_iv(ticker, contract_symbol, exp_date_str, d)
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

print("\n3 & 4. GAP AGE AND CARRY-FORWARD AGE")
print("=" * 90)
# Need entry date per contract to compute "age since entry"
entry_by_contract = {}
for t in trades:
    entry_by_contract[t["strike"]] = t["entry_date"]  # approximate join by strike (single-ticker, should be unique enough for this small sample)

age_buckets = {"entry": 0, "1day": 0, "2day": 0, "3plus": 0}
carryforward_age_buckets = {"1day": 0, "2day": 0, "3plus": 0}
max_carryforward_age = 0

detailed_gaps = []
for g in gap_log:
    gap_date = g["checkpoint_date"]
    # Find matching trade by contract prefix strike (best-effort join)
    matching_trade = None
    for t in trades:
        if str(t["strike"]) in g["contract"]:
            matching_trade = t
            break

    if matching_trade:
        days_since_entry = (gap_date - matching_trade["entry_date"]).days
        if days_since_entry == 0:
            age_buckets["entry"] += 1
        elif days_since_entry == 1:
            age_buckets["1day"] += 1
        elif days_since_entry == 2:
            age_buckets["2day"] += 1
        else:
            age_buckets["3plus"] += 1

    detailed_gaps.append({"ticker": g["ticker"], "contract": g["contract"], "gap_date": gap_date, "carried_iv": g["carried_forward_iv"]})

print("Gap age relative to entry: " + str(age_buckets))

print("\n5. GAP CLUSTERING")
print("=" * 90)
sorted_gaps = sorted(detailed_gaps, key=lambda g: (g["contract"], g["gap_date"]))
clusters = []
current_cluster = []
for g in sorted_gaps:
    if current_cluster and current_cluster[-1]["contract"] == g["contract"] and (g["gap_date"] - current_cluster[-1]["gap_date"]).days <= 3:
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
        print("  Cluster: " + c[0]["contract"] + " " + str([str(g["gap_date"]) for g in c]))

print("\n6. IMPACT ON VALUATION (ex-post diagnostic, NOT used in backtest)")
print("=" * 90)
iv_diffs = []
for g in detailed_gaps:
    exp_date_str = None
    for t in trades:
        if str(t["strike"]) in g["contract"]:
            exp_date_str = t["expiry_date"].isoformat()
            break
    if exp_date_str is None:
        continue

    next_iv_result = find_next_available_iv(g["ticker"], g["contract"], exp_date_str, g["gap_date"])
    if next_iv_result is None:
        print("  " + g["contract"] + " " + str(g["gap_date"]) + ": no next IV found within 10 days")
        continue

    diff = abs(next_iv_result["iv"] - g["carried_iv"])
    iv_diffs.append(diff)
    print("  " + g["contract"] + " " + str(g["gap_date"]) + ": carried=" + str(round(g["carried_iv"],4)) + " next_available=" + str(round(next_iv_result["iv"],4)) + " (date=" + str(next_iv_result["date"]) + ") diff=" + str(round(diff,4)))

if iv_diffs:
    print("\nMedian abs IV diff: " + str(round(statistics.median(iv_diffs),4)))
    print("Mean abs IV diff: " + str(round(statistics.mean(iv_diffs),4)))
    print("Max diff: " + str(round(max(iv_diffs),4)))
    large_diffs = len([d for d in iv_diffs if d > LARGE_DIFF_THRESHOLD])
    print("Large differences (>" + str(LARGE_DIFF_THRESHOLD) + "): " + str(large_diffs) + " / " + str(len(iv_diffs)))

print("\n7. P&L SENSITIVITY DIAGNOSTIC (EX-POST ONLY, USES FUTURE INFO, NOT A VALID BACKTEST RESULT)")
print("=" * 90)
print("(Illustrative only -- shows the magnitude of potential valuation impact IF the next")
print(" available IV had been used instead of the carry-forward value, at each gap checkpoint)")

print("\n8. METHODOLOGY CLASSIFICATION")
print("=" * 90)
if iv_diffs:
    median_diff = statistics.median(iv_diffs)
    max_diff = max(iv_diffs)
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
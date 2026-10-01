from dotenv import load_dotenv
load_dotenv()

"""
PURELY DESCRIPTIVE diagnostic comparing the 5-bar and 20-bar eligible
observation populations from the already-closed Experiment 1. No new
hypothesis test, no changes to Experiment 1, no Experiment 2 design.

"Eligible" = the complete-feature population (all 10 locked features
present) BEFORE any train/val/test split -- the natural population
each horizon's analysis draws from.
"""

import pickle
from datetime import datetime, timezone
from collections import defaultdict
import backtest_engine as be
import numpy as np
from ml_experiment1_executor import LOCKED_FEATURES, BASELINE_FEATURE
from ml_experiment1_robustness_checks import _encode_value
from data_prep_experiment1 import TICKERS

with open("ml_experiment1_dataset.pkl", "rb") as f:
    dataset = pickle.load(f)

eligible_20bar = dataset["all_complete_rows"]
print("20-bar eligible count (already persisted): " + str(len(eligible_20bar)))

print("\nRecomputing 5-bar eligible population (targets only, same features reused)...")
eligible_5bar = []
for ticker in TICKERS:
    ticker_rows = [r for r in eligible_20bar if r["ticker"] == ticker]
    if not ticker_rows:
        continue
    bars = be.get_historical_bars(ticker, datetime(2026,6,11,tzinfo=timezone.utc), datetime(2026,9,9,tzinfo=timezone.utc))
    for r in ticker_rows:
        idx = r["signal_index"]
        if idx + 5 >= len(bars):
            continue
        entry = float(bars[idx].close)
        exitp = float(bars[idx+5].close)
        new_row = dict(r)
        new_row["target"] = (exitp - entry) / entry
        eligible_5bar.append(new_row)
print("5-bar eligible count: " + str(len(eligible_5bar)))

# ============================================================
# QUESTION 1: Overlap
# ============================================================
print("\n" + "=" * 100)
print("QUESTION 1: OVERLAP BETWEEN 5-BAR AND 20-BAR ELIGIBLE POPULATIONS")
print("=" * 100)
keys_20 = set((r["ticker"], r["signal_index"]) for r in eligible_20bar)
keys_5 = set((r["ticker"], r["signal_index"]) for r in eligible_5bar)
intersection = keys_20 & keys_5
only_20 = keys_20 - keys_5
only_5 = keys_5 - keys_20

print("20-bar eligible: " + str(len(keys_20)))
print("5-bar eligible: " + str(len(keys_5)))
print("Intersection: " + str(len(intersection)))
print("20-only: " + str(len(only_20)))
print("5-only: " + str(len(only_5)))
print("Overlap as % of 20-bar: " + str(round(len(intersection)/len(keys_20)*100, 1)) + "%")
print("Overlap as % of 5-bar: " + str(round(len(intersection)/len(keys_5)*100, 1)) + "%")

# ============================================================
# QUESTION 2: Common-subset descriptive comparison (NO significance test)
# ============================================================
print("\n" + "=" * 100)
print("QUESTION 2: COMMON-SUBSET DESCRIPTIVE PERFORMANCE (purely descriptive, NO significance test)")
print("=" * 100)

rows_20_common = [r for r in eligible_20bar if (r["ticker"], r["signal_index"]) in intersection]
rows_5_common = [r for r in eligible_5bar if (r["ticker"], r["signal_index"]) in intersection]

print("Common-subset size: " + str(len(rows_20_common)) + " (both horizons, by construction)")

def extract(rows, feature_names):
    X = np.array([[_encode_value(r[f]) for f in feature_names] for r in rows])
    y = np.array([r["target"] for r in rows])
    return X, y

def descriptive_mse(rows, model_a, model_b, feature_names):
    Xa, y = extract(rows, [BASELINE_FEATURE])
    Xb, _ = extract(rows, feature_names)
    err_a = (y - model_a.predict(Xa)) ** 2
    err_b = (y - model_b.predict(Xb)) ** 2
    return err_a, err_b

from sklearn.linear_model import Ridge

def fit_simple(rows, feature_names):
    X, y = extract(rows, feature_names)
    model = Ridge(alpha=1.0)
    model.fit(X, y)
    return model

for label, rows in [("20-bar (common subset)", rows_20_common), ("5-bar (common subset)", rows_5_common)]:
    model_a = fit_simple(rows, [BASELINE_FEATURE])
    model_b = fit_simple(rows, LOCKED_FEATURES)
    err_a, err_b = descriptive_mse(rows, model_a, model_b, LOCKED_FEATURES)
    mse_a, mse_b = float(np.mean(err_a)), float(np.mean(err_b))
    rel_reduction = (mse_a - mse_b) / mse_a if mse_a != 0 else 0.0
    print("\n  " + label + " (n=" + str(len(rows)) + "):")
    print("    baseline MSE: " + str(round(mse_a, 6)))
    print("    full-model MSE: " + str(round(mse_b, 6)))
    print("    relative MSE reduction: " + str(round(rel_reduction*100, 2)) + "%")
    diffs = err_a - err_b
    print("    error-diff distribution: min=" + str(round(diffs.min(),5)) + " median=" + str(round(np.median(diffs),5)) + " max=" + str(round(diffs.max(),5)))

# ============================================================
# QUESTION 3: Per-ticker breakdown of the 5-bar population
# ============================================================
print("\n" + "=" * 100)
print("QUESTION 3: 5-BAR EFFECT BY TICKER (descriptive only, no ranking/winner declared)")
print("=" * 100)
model_a_5full = fit_simple(eligible_5bar, [BASELINE_FEATURE])
model_b_5full = fit_simple(eligible_5bar, LOCKED_FEATURES)

for ticker in TICKERS:
    ticker_rows = [r for r in eligible_5bar if r["ticker"] == ticker]
    if not ticker_rows:
        print("  " + ticker + ": 0 eligible observations")
        continue
    err_a, err_b = descriptive_mse(ticker_rows, model_a_5full, model_b_5full, LOCKED_FEATURES)
    mse_a, mse_b = float(np.mean(err_a)), float(np.mean(err_b))
    rel_reduction = (mse_a - mse_b) / mse_a if mse_a != 0 else 0.0
    print("  " + ticker + ": n=" + str(len(ticker_rows)) + " baseline_MSE=" + str(round(mse_a,6)) + " full_MSE=" + str(round(mse_b,6)) + " rel_reduction=" + str(round(rel_reduction*100,2)) + "%")

# ============================================================
# TIMESTAMP DISTRIBUTION COMPARISON
# ============================================================
print("\n" + "=" * 100)
print("TIMESTAMP DISTRIBUTION -- 5-BAR VS 20-BAR ELIGIBLE POPULATIONS")
print("=" * 100)

def bucket_by_month(rows):
    buckets = defaultdict(int)
    for r in rows:
        month = r["signal_timestamp"][:7]  # YYYY-MM
        buckets[month] += 1
    return dict(sorted(buckets.items()))

dist_20 = bucket_by_month(eligible_20bar)
dist_5 = bucket_by_month(eligible_5bar)
all_months = sorted(set(dist_20.keys()) | set(dist_5.keys()))
print("Month      20-bar   5-bar")
for month in all_months:
    print("  " + month + "     " + str(dist_20.get(month,0)).rjust(4) + "     " + str(dist_5.get(month,0)).rjust(4))

print("\n" + "=" * 100)
print("DIAGNOSTIC COMPLETE. No changes made to Experiment 1. No new significance test performed.")
print("No Experiment 2 designed. This is descriptive analysis only.")
print("=" * 100)
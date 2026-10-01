from dotenv import load_dotenv
load_dotenv()

"""
SECOND CORRECTION of Questions 2-3. v2 pooled all 6 tickers' rows
BEFORE splitting, which is wrong -- each ticker has its own
independent signal_index numbering (not a shared timeline), so
pooled-then-split purging compared unrelated tickers' indices
against each other. VOID.

This version splits PER-TICKER FIRST (each ticker's own chronological
index, its own purging), THEN pools the resulting train/val/test
partitions -- exactly matching Experiment 1's actual, correct
methodology (as implemented in run_data_prep_audit.py's per-ticker loop).
"""

import pickle
from datetime import datetime, timezone
import backtest_engine as be
import numpy as np
from sklearn.linear_model import Ridge
from ml_experiment1_executor import LOCKED_FEATURES, BASELINE_FEATURE
from ml_experiment1_robustness_checks import _encode_value
from data_prep_experiment1 import chronological_split_with_purging, TICKERS

print("=" * 100)
print("VOIDED (again): v2's Questions 2-3 -- pooled tickers before splitting, comparing")
print("unrelated tickers' signal_index values against each other during purging. INVALID.")
print("RETAINED AS VALID: v1's Question 1 (100% overlap, 371/371) and timestamp distribution.")
print("=" * 100)

with open("ml_experiment1_dataset.pkl", "rb") as f:
    dataset = pickle.load(f)

eligible_20bar = dataset["all_complete_rows"]

print("\nRecomputing 5-bar targets...")
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

print("\nSplitting PER-TICKER (each ticker's own chronological index), then pooling...")
all_train, all_val, all_test = [], [], []
for ticker in TICKERS:
    ticker_rows = sorted([r for r in eligible_5bar if r["ticker"] == ticker], key=lambda r: r["signal_index"])
    if not ticker_rows:
        continue
    train_t, val_t, test_t, purge_t = chronological_split_with_purging(ticker_rows, horizon=5)
    print("  " + ticker + ": train=" + str(len(train_t)) + " val=" + str(len(val_t)) + " test=" + str(len(test_t)) + " (purged train=" + str(purge_t["purged_train"]) + " val=" + str(purge_t["purged_val"]) + ")")
    all_train.extend(train_t)
    all_val.extend(val_t)
    all_test.extend(test_t)

print("\nPooled totals: train=" + str(len(all_train)) + " val=" + str(len(all_val)) + " test=" + str(len(all_test)))

def extract(rows, feature_names):
    X = np.array([[_encode_value(r[f]) for f in feature_names] for r in rows])
    y = np.array([r["target"] for r in rows])
    return X, y

def fit_with_val_selection(train_rows, val_rows, feature_names):
    Xtr, ytr = extract(train_rows, feature_names)
    Xv, yv = extract(val_rows, feature_names)
    best_model, best_val_mse = None, None
    for alpha in [0.01, 0.1, 1.0, 10.0, 100.0]:
        m = Ridge(alpha=alpha)
        m.fit(Xtr, ytr)
        val_mse = float(np.mean((yv - m.predict(Xv)) ** 2))
        if best_val_mse is None or val_mse < best_val_mse:
            best_model, best_val_mse = m, val_mse
    return best_model

print("\n" + "=" * 100)
print("QUESTION 2 (CORRECTED v3): GENUINE OUT-OF-SAMPLE PERFORMANCE ON HELD-OUT TEST SET")
print("=" * 100)

model_a = fit_with_val_selection(all_train, all_val, [BASELINE_FEATURE])
model_b = fit_with_val_selection(all_train, all_val, LOCKED_FEATURES)

Xa_test, y_test = extract(all_test, [BASELINE_FEATURE])
Xb_test, _ = extract(all_test, LOCKED_FEATURES)
err_a = (y_test - model_a.predict(Xa_test)) ** 2
err_b = (y_test - model_b.predict(Xb_test)) ** 2
mse_a, mse_b = float(np.mean(err_a)), float(np.mean(err_b))
rel_reduction = (mse_a - mse_b) / mse_a if mse_a != 0 else 0.0

print("Held-out test set size: " + str(len(all_test)))
print("Baseline MSE (held-out): " + str(round(mse_a, 6)))
print("Full-model MSE (held-out): " + str(round(mse_b, 6)))
print("Relative MSE reduction (held-out, genuine OOS): " + str(round(rel_reduction*100, 2)) + "%")

print("\n" + "=" * 100)
print("QUESTION 3 (CORRECTED v3): PER-TICKER BREAKDOWN, USING THE SAME HELD-OUT TEST SET")
print("=" * 100)

for ticker in TICKERS:
    ticker_test_rows = [r for r in all_test if r["ticker"] == ticker]
    if not ticker_test_rows:
        print("  " + ticker + ": 0 observations in the held-out test set")
        continue
    Xa_t, y_t = extract(ticker_test_rows, [BASELINE_FEATURE])
    Xb_t, _ = extract(ticker_test_rows, LOCKED_FEATURES)
    err_a_t = (y_t - model_a.predict(Xa_t)) ** 2
    err_b_t = (y_t - model_b.predict(Xb_t)) ** 2
    mse_a_t, mse_b_t = float(np.mean(err_a_t)), float(np.mean(err_b_t))
    rel_t = (mse_a_t - mse_b_t) / mse_a_t if mse_a_t != 0 else 0.0
    print("  " + ticker + ": n=" + str(len(ticker_test_rows)) + " baseline_MSE=" + str(round(mse_a_t,6)) + " full_MSE=" + str(round(mse_b_t,6)) + " rel_reduction=" + str(round(rel_t*100,2)) + "%")

print("\n" + "=" * 100)
print("DIAGNOSTIC v3 COMPLETE. Descriptive only. No new significance claim. No Experiment 1 changes.")
print("=" * 100)
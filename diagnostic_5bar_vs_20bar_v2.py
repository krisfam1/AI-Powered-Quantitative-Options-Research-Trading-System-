from dotenv import load_dotenv
load_dotenv()

"""
CORRECTED rebuild of Questions 2-3 from diagnostic_5bar_vs_20bar.py.
The original v1 diagnostic's Questions 2-3 are VOID -- fit and
evaluated on the same rows (in-sample), not a genuine out-of-sample
comparison. This version reuses Experiment 1's own methodology:
chronological split, purged, train-only fitting, held-out evaluation.

Question 1 (100% overlap) and the timestamp distribution from v1
REMAIN VALID and are not recomputed here.

Scope, deliberately narrow: does the previously observed 5-bar
improvement remain visible under genuine out-of-sample evaluation,
and how is it distributed across tickers -- using the SAME held-out
partition for every ticker, not six separate per-ticker models.
This is NOT a new significance claim and NOT a "does it work" question.
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
print("VOIDED: v1 diagnostic's Questions 2-3 (in-sample fit/evaluate -- not valid out-of-sample evidence)")
print("RETAINED AS VALID: v1's Question 1 (100% overlap, 371/371) and timestamp distribution")
print("=" * 100)

with open("ml_experiment1_dataset.pkl", "rb") as f:
    dataset = pickle.load(f)

eligible_20bar = dataset["all_complete_rows"]

print("\nRecomputing 5-bar targets on the same 371 observations...")
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
print("5-bar rows: " + str(len(eligible_5bar)) + " (confirms same 371 minus any horizon-specific end-of-data exclusion)")

# Chronological split WITH purging at horizon=5, same structure as Experiment 1
train, val, test, purge_stats = chronological_split_with_purging(eligible_5bar, horizon=5)
print("Chronological split (60/20/20, purged at horizon=5): train=" + str(len(train)) + " val=" + str(len(val)) + " test=" + str(len(test)))
print("Purged: train=" + str(purge_stats["purged_train"]) + " val=" + str(purge_stats["purged_val"]))

def extract(rows, feature_names):
    X = np.array([[_encode_value(r[f]) for f in feature_names] for r in rows])
    y = np.array([r["target"] for r in rows])
    return X, y

def fit_with_val_selection(train_rows, val_rows, feature_names):
    """Same hyperparameter-selection procedure as Experiment 1: grid search, chosen on validation MSE."""
    Xtr, ytr = extract(train_rows, feature_names)
    Xv, yv = extract(val_rows, feature_names)
    best_model, best_val_mse = None, None
    for alpha in [0.01, 0.1, 1.0, 10.0, 100.0]:
        m = Ridge(alpha=alpha)
        m.fit(Xtr, ytr)  # fit ONLY on train
        val_mse = float(np.mean((yv - m.predict(Xv)) ** 2))
        if best_val_mse is None or val_mse < best_val_mse:
            best_model, best_val_mse = m, val_mse
    return best_model

print("\n" + "=" * 100)
print("QUESTION 2 (CORRECTED): GENUINE OUT-OF-SAMPLE PERFORMANCE ON HELD-OUT TEST SET")
print("=" * 100)

model_a = fit_with_val_selection(train, val, [BASELINE_FEATURE])
model_b = fit_with_val_selection(train, val, LOCKED_FEATURES)

Xa_test, y_test = extract(test, [BASELINE_FEATURE])
Xb_test, _ = extract(test, LOCKED_FEATURES)
err_a = (y_test - model_a.predict(Xa_test)) ** 2
err_b = (y_test - model_b.predict(Xb_test)) ** 2
mse_a, mse_b = float(np.mean(err_a)), float(np.mean(err_b))
rel_reduction = (mse_a - mse_b) / mse_a if mse_a != 0 else 0.0

print("Held-out test set size: " + str(len(test)))
print("Baseline MSE (held-out): " + str(round(mse_a, 6)))
print("Full-model MSE (held-out): " + str(round(mse_b, 6)))
print("Relative MSE reduction (held-out, genuine OOS): " + str(round(rel_reduction*100, 2)) + "%")
print("NOTE: descriptive only -- no new significance test performed, consistent with the")
print("preregistered Experiment 1 finding, not a new independent claim.")

print("\n" + "=" * 100)
print("QUESTION 3 (CORRECTED): PER-TICKER BREAKDOWN, USING THE SAME HELD-OUT TEST SET")
print("=" * 100)
print("(Same single model, same held-out partition for every ticker -- not per-ticker models)")

for ticker in TICKERS:
    ticker_test_rows = [r for r in test if r["ticker"] == ticker]
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
print("DIAGNOSTIC v2 COMPLETE. Descriptive only. No new significance claim. No Experiment 1 changes.")
print("No Experiment 2 designed.")
print("=" * 100)
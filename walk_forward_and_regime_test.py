from dotenv import load_dotenv
load_dotenv()

"""
Two additional, real validation tests requested for the Gradient
Boosting provisional decision:

1. TRUE rolling walk-forward: multiple sequential folds marching forward
   through time -- each fold trains ONLY on data before it, unlike our
   earlier tests which all started from index 0. This is a genuinely
   stricter test than what's been run so far.

2. Volatility-regime breakdown: using realized_vol_percentile as an
   honest, available proxy for market regime (a full bull/bear/ranging
   classifier doesn't exist yet -- this is the real, current substitute).

HONEST NOTE: a full realistic-transaction-cost re-test would require
connecting model predictions back to actual backtest P&L with spread
costs applied -- a larger, separate undertaking not covered in this
pass. This script covers walk-forward and regime-proxy only.
"""

import json
import sqlite3
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score

FEATURE_KEYS = [
    "delta", "gamma", "theta", "charm", "vega_per_1pct_iv",
    "realized_volatility", "realized_vol_percentile", "relative_volume",
    "breakout_magnitude_score", "trend_strength_score", "momentum_score",
    "moneyness", "dte",
]


def load_training_data():
    with sqlite3.connect("ml_training_data.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM training_examples ORDER BY entry_date ASC").fetchall()

    X, y, vol_pctile = [], [], []
    for r in rows:
        features = json.loads(r["features_json"])
        row_vector = []
        valid = True
        for key in FEATURE_KEYS:
            val = features.get(key)
            if val is None:
                valid = False
                break
            row_vector.append(val)
        if not valid:
            continue
        X.append(row_vector)
        y.append(r["won"])
        vol_pctile.append(features.get("realized_vol_percentile", 50))

    return np.array(X), np.array(y), np.array(vol_pctile)


X, y, vol_pctile = load_training_data()
print("Total usable examples: " + str(len(X)) + "\n")

models = {
    "Logistic Regression": lambda: LogisticRegression(max_iter=1000),
    "Gradient Boosting": lambda: GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42),
}

print("=" * 70)
print("TEST A: TRUE rolling walk-forward (5 sequential folds)")
print("=" * 70)
n_folds = 5
fold_size = len(X) // n_folds

for model_name, model_fn in models.items():
    print("\n" + model_name + ":")
    fold_accuracies = []
    for fold in range(1, n_folds):
        train_end = fold * fold_size
        test_start = train_end
        test_end = min(test_start + fold_size, len(X))

        X_train, X_test = X[:train_end], X[test_start:test_end]
        y_train, y_test = y[:train_end], y[test_start:test_end]

        if len(X_test) < 5:
            continue

        model = model_fn()
        model.fit(X_train, y_train)
        accuracy = accuracy_score(y_test, model.predict(X_test))
        fold_accuracies.append(accuracy)
        print("  Fold " + str(fold) + " (train n=" + str(len(X_train)) + ", test n=" + str(len(X_test)) + "): " + str(round(accuracy*100, 1)) + "%")

    print("  Average across folds: " + str(round(np.mean(fold_accuracies)*100, 1)) + "%  (std: " + str(round(np.std(fold_accuracies)*100, 1)) + ")")

print("\n" + "=" * 70)
print("TEST B: Performance by realized-volatility regime (proxy for market regime)")
print("=" * 70)
split_index = int(len(X) * 0.75)
X_train, X_test = X[:split_index], X[split_index:]
y_train, y_test = y[:split_index], y[split_index:]
vol_test = vol_pctile[split_index:]

low_vol_mask = vol_test < 33
mid_vol_mask = (vol_test >= 33) & (vol_test < 67)
high_vol_mask = vol_test >= 67

for model_name, model_fn in models.items():
    print("\n" + model_name + ":")
    model = model_fn()
    model.fit(X_train, y_train)

    for label, mask in [("Low volatility regime", low_vol_mask), ("Mid volatility regime", mid_vol_mask), ("High volatility regime", high_vol_mask)]:
        if mask.sum() < 5:
            print("  " + label + ": too few examples (n=" + str(mask.sum()) + ")")
            continue
        accuracy = accuracy_score(y_test[mask], model.predict(X_test[mask]))
        print("  " + label + ": " + str(round(accuracy*100, 1)) + "% (n=" + str(mask.sum()) + ")")
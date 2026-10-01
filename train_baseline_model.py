from dotenv import load_dotenv
load_dotenv()

"""
Baseline ML model: logistic regression predicting win probability.

Uses a genuine CHRONOLOGICAL train/test split (earliest 75% of trades
for training, most recent 25% for testing) -- never a random split,
consistent with the walk-forward discipline used throughout this whole
project. This is the honest floor to beat before any more sophisticated
model is considered worth its added complexity.
"""

import json
import sqlite3
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score

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

    X, y, meta = [], [], []
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
        meta.append({"ticker": r["ticker"], "entry_date": r["entry_date"], "pnl_pct": r["pnl_pct"]})

    return np.array(X), np.array(y), meta


def train_and_evaluate():
    X, y, meta = load_training_data()
    print("Total usable examples (all features present): " + str(len(X)))

    if len(X) < 50:
        print("Too few examples for a meaningful train/test split -- aborting.")
        return

    split_index = int(len(X) * 0.75)
    X_train, X_test = X[:split_index], X[split_index:]
    y_train, y_test = y[:split_index], y[split_index:]

    print("Training set: " + str(len(X_train)) + " examples (chronologically earliest)")
    print("Test set:     " + str(len(X_test)) + " examples (chronologically most recent)")

    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    probabilities = model.predict_proba(X_test)[:, 1]

    accuracy = accuracy_score(y_test, predictions)
    try:
        auc = roc_auc_score(y_test, probabilities)
    except Exception:
        auc = None

    # Honest baseline comparison: what if we just always predicted the majority class?
    majority_class = 1 if sum(y_train) > len(y_train) / 2 else 0
    majority_predictions = [majority_class] * len(y_test)
    majority_accuracy = accuracy_score(y_test, majority_predictions)

    print("\n--- RESULTS (on chronologically held-out, unseen test data) ---")
    print("Model accuracy:            " + str(round(accuracy * 100, 1)) + "%")
    print("Majority-class baseline:   " + str(round(majority_accuracy * 100, 1)) + "% (always guessing the more common outcome)")
    print("Model AUC-ROC:             " + (str(round(auc, 3)) if auc is not None else "could not compute"))

    print("\n--- Feature importance (logistic regression coefficients) ---")
    for key, coef in sorted(zip(FEATURE_KEYS, model.coef_[0]), key=lambda x: abs(x[1]), reverse=True):
        print("  " + key + ": " + str(round(coef, 4)))

    if accuracy <= majority_accuracy:
        print("\nHONEST VERDICT: the model does NOT beat simply guessing the majority class.")
        print("This means the current feature set does not yet contain a real, learnable edge.")
    else:
        print("\nHONEST VERDICT: the model beats the majority-class baseline by " + str(round((accuracy - majority_accuracy) * 100, 1)) + " percentage points.")
        print("This is a real, if modest, signal -- worth further validation before trusting it.")


if __name__ == "__main__":
    train_and_evaluate()
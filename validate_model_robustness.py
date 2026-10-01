from dotenv import load_dotenv
load_dotenv()

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

    X, y, tickers = [], [], []
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
        tickers.append(r["ticker"])

    return np.array(X), np.array(y), np.array(tickers)


X, y, tickers = load_training_data()
print("Total usable examples: " + str(len(X)) + "\n")

print("=" * 60)
print("TEST 1: Multiple chronological splits")
print("=" * 60)
for split_pct in [0.60, 0.70, 0.75, 0.80]:
    split_index = int(len(X) * split_pct)
    X_train, X_test = X[:split_index], X[split_index:]
    y_train, y_test = y[:split_index], y[split_index:]

    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)
    accuracy = accuracy_score(y_test, model.predict(X_test))
    majority = 1 if sum(y_train) > len(y_train) / 2 else 0
    majority_acc = accuracy_score(y_test, [majority] * len(y_test))
    print("Split " + str(int(split_pct*100)) + "/" + str(int((1-split_pct)*100)) + ": model=" + str(round(accuracy*100,1)) + "% vs majority=" + str(round(majority_acc*100,1)) + "% (n_test=" + str(len(X_test)) + ")")

print("\n" + "=" * 60)
print("TEST 2: Ticker-based holdout (train on 5, test on 1 UNSEEN ticker)")
print("=" * 60)
unique_tickers = sorted(set(tickers))
for held_out_ticker in unique_tickers:
    train_mask = tickers != held_out_ticker
    test_mask = tickers == held_out_ticker

    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]

    if len(X_test) < 10:
        continue

    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)
    accuracy = accuracy_score(y_test, model.predict(X_test))
    majority = 1 if sum(y_train) > len(y_train) / 2 else 0
    majority_acc = accuracy_score(y_test, [majority] * len(y_test))
    print("Held out " + held_out_ticker + ": model=" + str(round(accuracy*100,1)) + "% vs majority=" + str(round(majority_acc*100,1)) + "% (n_test=" + str(len(X_test)) + ")")

print("\n" + "=" * 60)
print("TEST 3: Random label shuffle (sanity check for leakage)")
print("=" * 60)
np.random.seed(42)
y_shuffled = np.random.permutation(y)
split_index = int(len(X) * 0.75)
X_train, X_test = X[:split_index], X[split_index:]
y_train_shuffled, y_test_shuffled = y_shuffled[:split_index], y_shuffled[split_index:]

model = LogisticRegression(max_iter=1000)
model.fit(X_train, y_train_shuffled)
shuffled_accuracy = accuracy_score(y_test_shuffled, model.predict(X_test))
print("Accuracy on RANDOMLY SHUFFLED labels: " + str(round(shuffled_accuracy*100, 1)) + "%")
print("(This should be close to 50% -- if it's much higher, something in the pipeline is leaking information)")
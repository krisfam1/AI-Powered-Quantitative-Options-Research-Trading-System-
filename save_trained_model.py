from dotenv import load_dotenv
load_dotenv()

"""
Trains the baseline model on ALL available data (not just a chronological
split, since we've already validated this model's robustness thoroughly)
and saves it as a reusable file, so other scripts (like the time-based
decay exit) can load and use it without retraining every time.
"""

import json
import sqlite3
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

FEATURE_KEYS = [
    "delta", "gamma", "theta", "charm", "vega_per_1pct_iv",
    "realized_volatility", "realized_vol_percentile", "relative_volume",
    "breakout_magnitude_score", "trend_strength_score", "momentum_score",
    "moneyness", "dte",
]

MODEL_PATH = "baseline_model.joblib"


def load_training_data():
    with sqlite3.connect("ml_training_data.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM training_examples ORDER BY entry_date ASC").fetchall()

    X, y = [], []
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

    return np.array(X), np.array(y)


if __name__ == "__main__":
    X, y = load_training_data()
    print("Training final model on all " + str(len(X)) + " available examples...")

    model = LogisticRegression(max_iter=1000)
    model.fit(X, y)

    joblib.dump({"model": model, "feature_keys": FEATURE_KEYS}, MODEL_PATH)
    print("Saved trained model to " + MODEL_PATH)
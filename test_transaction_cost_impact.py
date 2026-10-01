from dotenv import load_dotenv
load_dotenv()

"""
Realistic transaction-cost re-test.

Uses the REAL dollar P&L already stored in ml_training_data.db -- which
already includes realistic spread costs (apply_spread_cost=True was used
when this data was generated). Tests whether filtering to only each
model's highest-confidence predictions genuinely improves total real
dollar P&L, or whether it just reduces trade count without a real
economic benefit.
"""

import json
import sqlite3
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier

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

    X, y, pnl_dollars = [], [], []
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
        pnl_dollars.append(r["pnl_dollars"])

    return np.array(X), np.array(y), np.array(pnl_dollars)


X, y, pnl_dollars = load_training_data()
split_index = int(len(X) * 0.75)
X_train, X_test = X[:split_index], X[split_index:]
y_train, y_test = y[:split_index], y[split_index:]
pnl_test = pnl_dollars[split_index:]

baseline_total_pnl = pnl_test.sum()
print("BASELINE: taking ALL " + str(len(X_test)) + " holdout trades (no model filtering)")
print("  Real, realistic total P&L (spread costs included): $" + str(round(baseline_total_pnl, 2)) + "\n")

models = {
    "Logistic Regression": lambda: LogisticRegression(max_iter=1000),
    "Gradient Boosting": lambda: GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42),
}

for model_name, model_fn in models.items():
    print("=" * 70)
    print(model_name + ": filtering to only high-confidence predicted trades")
    print("=" * 70)

    model = model_fn()
    model.fit(X_train, y_train)
    probabilities = model.predict_proba(X_test)[:, 1]

    for threshold in [0.50, 0.60, 0.70, 0.80]:
        mask = probabilities >= threshold
        n_trades = mask.sum()
        if n_trades == 0:
            print("  Threshold " + str(threshold) + ": 0 trades qualify -- skipping")
            continue
        filtered_pnl = pnl_test[mask].sum()
        avg_pnl_per_trade = filtered_pnl / n_trades
        baseline_avg = baseline_total_pnl / len(X_test)
        print("  Threshold " + str(threshold) + ": n=" + str(n_trades) + " trades, total P&L=$" + str(round(filtered_pnl, 2)) + ", avg/trade=$" + str(round(avg_pnl_per_trade, 2)) + " (vs baseline avg/trade $" + str(round(baseline_avg, 2)) + ")")
    print("")
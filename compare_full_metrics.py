from dotenv import load_dotenv
load_dotenv()

"""
Comprehensive comparison: baseline strategy vs. ML-filtered variants,
using Sharpe, Sortino, max drawdown, and profit factor -- all computed
on REAL, realistic-cost-adjusted backtest P&L (apply_spread_cost=True
was used when this data was generated).

Also breaks down by volatility regime (the honest, currently-available
proxy for market regime -- a full bull/bear/ranging classifier doesn't
exist yet).
"""

import json
import sqlite3
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from performance_metrics import compute_all_metrics

FEATURE_KEYS = [
    "delta", "gamma", "theta", "charm", "vega_per_1pct_iv",
    "realized_volatility", "realized_vol_percentile", "relative_volume",
    "breakout_magnitude_score", "trend_strength_score", "momentum_score",
    "moneyness", "dte",
]


def load_data():
    with sqlite3.connect("ml_training_data.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM training_examples ORDER BY entry_date ASC").fetchall()

    X, trades = [], []
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
        trades.append({
            "pnl_dollars": r["pnl_dollars"], "pnl_pct": r["pnl_pct"],
            "exit_date": r["exit_date"], "won": r["won"],
            "realized_vol_percentile": features.get("realized_vol_percentile", 50),
        })

    return np.array(X), trades


X, trades = load_data()
y = np.array([t["won"] for t in trades])
split_index = int(len(X) * 0.75)
X_train, X_test = X[:split_index], X[split_index:]
y_train = y[:split_index]
test_trades = trades[split_index:]

print("=" * 80)
print("STRATEGY 1: Baseline (all holdout trades, no ML filtering)")
print("=" * 80)
baseline_metrics = compute_all_metrics(test_trades)
for k, v in baseline_metrics.items():
    print("  " + k + ": " + str(v))

models = {
    "Logistic Regression (>=0.6 confidence)": (LogisticRegression(max_iter=1000), 0.6),
    "Gradient Boosting (>=0.6 confidence)": (GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42), 0.6),
}

results_table = {"Baseline (unfiltered)": baseline_metrics}

for model_name, (model, threshold) in models.items():
    model.fit(X_train, y_train)
    probabilities = model.predict_proba(X_test)[:, 1]
    filtered_trades = [t for t, p in zip(test_trades, probabilities) if p >= threshold]

    print("\n" + "=" * 80)
    print("STRATEGY: " + model_name + " (n=" + str(len(filtered_trades)) + ")")
    print("=" * 80)
    metrics = compute_all_metrics(filtered_trades)
    for k, v in metrics.items():
        print("  " + k + ": " + str(v))
    results_table[model_name] = metrics

print("\n" + "=" * 80)
print("SUMMARY TABLE (realistic costs already included)")
print("=" * 80)
print(f"{'Strategy':<42} {'Sharpe':>8} {'Sortino':>9} {'MaxDD%':>8} {'ProfitFactor':>13}")
for name, m in results_table.items():
    dd = m.get("max_drawdown_pct")
    dd_str = str(dd) if dd is not None else "N/A"
    print(f"{name:<42} {str(m['sharpe_ratio']):>8} {str(m['sortino_ratio']):>9} {dd_str:>8} {str(m['profit_factor']):>13}")

print("\n" + "=" * 80)
print("BREAKDOWN BY VOLATILITY REGIME (proxy for market regime)")
print("=" * 80)
low_vol = [t for t in test_trades if t["realized_vol_percentile"] < 33]
mid_vol = [t for t in test_trades if 33 <= t["realized_vol_percentile"] < 67]
high_vol = [t for t in test_trades if t["realized_vol_percentile"] >= 67]

for label, group in [("Low volatility", low_vol), ("Mid volatility", mid_vol), ("High volatility", high_vol)]:
    print("\n" + label + " (n=" + str(len(group)) + "):")
    if len(group) < 3:
        print("  too few trades for meaningful metrics")
        continue
    m = compute_all_metrics(group)
    for k, v in m.items():
        print("  " + k + ": " + str(v))
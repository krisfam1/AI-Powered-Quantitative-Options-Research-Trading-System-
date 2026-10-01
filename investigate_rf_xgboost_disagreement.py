from dotenv import load_dotenv
load_dotenv()

"""
DIAGNOSTIC INVESTIGATION, not a pre-registered experiment -- no config
hash, no Stage 1/Stage 2, no VALIDATED/REJECTED decision rule. Purpose is
understanding WHY Random Forest and XGBoost disagreed on the forward-
realized-volatility dataset (randomforest_volatility_prediction_v1_20260925,
CLOSED REJECTED, CLAUDE.md Section 46), not claiming or testing a
tradeable signal. "Inconclusive, no clear explanation" is a legitimate,
acceptable outcome here.

Reuses the existing 4,027-row xgboost_volatility_dataset.db and the same
8 features/3 target horizons -- zero new data collection. Reuses the same
chronological split and the same best hyperparameters already found for
Ridge/RF/XGBoost in the two closed experiments, as the baseline for every
check below.
"""

import json
import sqlite3
import warnings
from datetime import datetime

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

warnings.filterwarnings("ignore")

DB_PATH = "xgboost_volatility_dataset.db"
FEATURES = [
    "term_structure_slope_pct", "oi_skew", "trailing_realized_vol_20d",
    "delta", "gamma", "theta", "charm", "vega_per_1pct_iv",
]
TARGET_COL = "target_realized_vol_20d"

# Best hyperparameters already found in the two closed experiments -- reused
# as the baseline configuration for this investigation, not re-tuned.
RIDGE_ALPHA = 100.0
RF_PARAMS = {"max_depth": 4, "min_samples_leaf": 10, "max_features": "sqrt"}
XGB_PARAMS = {"max_depth": 3, "min_child_weight": 5, "reg_alpha": 1.0, "reg_lambda": 1.0, "subsample": 0.8, "colsample_bytree": 0.8}


def log(msg: str) -> None:
    print(msg, flush=True)


def load_rows():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM volatility_training_examples ORDER BY obs_date, ticker, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def chronological_split(data):
    dates_sorted = sorted(set(r["obs_date"] for r in data))
    counts_by_date = {}
    for r in data:
        counts_by_date[r["obs_date"]] = counts_by_date.get(r["obs_date"], 0) + 1
    total = len(data)
    cum = 0
    train_end_date = val_end_date = None
    for d in dates_sorted:
        cum += counts_by_date[d]
        if train_end_date is None and cum / total >= 0.60:
            train_end_date = d
        if val_end_date is None and cum / total >= 0.80:
            val_end_date = d
            break
    train = [r for r in data if r["obs_date"] <= train_end_date]
    val = [r for r in data if train_end_date < r["obs_date"] <= val_end_date]
    test = [r for r in data if r["obs_date"] > val_end_date]
    return train, val, test, train_end_date, val_end_date


def to_xy(rows):
    X = np.array([[r[f] for f in FEATURES] for r in rows], dtype=float)
    y = np.array([r[TARGET_COL] for r in rows], dtype=float)
    return X, y


def main():
    report = {}
    log("Loading data...")
    data = load_rows()
    train, val, test, train_end, val_end = chronological_split(data)
    train_val = train + val
    log(f"train_val={len(train_val)} test={len(test)} (test: {test[0]['obs_date']}..{test[-1]['obs_date']})")

    X_trainval_raw, y_trainval = to_xy(train_val)
    scaler = StandardScaler().fit(X_trainval_raw)
    X_trainval = scaler.transform(X_trainval_raw)
    X_test_raw, y_test = to_xy(test)
    X_test = scaler.transform(X_test_raw)

    log("\nFitting baseline models (best hyperparameters from the closed experiments, seed=42)...")
    ridge = Ridge(alpha=RIDGE_ALPHA, random_state=42).fit(X_trainval, y_trainval)
    rf = RandomForestRegressor(n_estimators=300, random_state=42, **RF_PARAMS).fit(X_trainval, y_trainval)
    xgb_model = xgb.XGBRegressor(n_estimators=200, learning_rate=0.05, random_state=42, **XGB_PARAMS).fit(X_trainval, y_trainval)

    pred_ridge = ridge.predict(X_test)
    pred_rf = rf.predict(X_test)
    pred_xgb = xgb_model.predict(X_test)

    log(f"Full test set (n={len(test)}): R2_Ridge={r2_score(y_test, pred_ridge):.4f} R2_RF={r2_score(y_test, pred_rf):.4f} R2_XGB={r2_score(y_test, pred_xgb):.4f}")

    # =========================================================================
    # CHECK 1: Prediction-level disagreement
    # =========================================================================
    log("\n" + "=" * 100)
    log("CHECK 1: Prediction-level disagreement (RF vs XGBoost) on the full test set")
    log("=" * 100)

    disagreement = pred_rf - pred_xgb  # positive = RF predicts higher vol than XGB
    err_rf = np.abs(y_test - pred_rf)
    err_xgb = np.abs(y_test - pred_xgb)
    who_is_more_accurate = err_rf - err_xgb  # negative = RF more accurate on this obs

    report["check1_overall"] = {
        "n": len(test), "mean_disagreement": float(np.mean(disagreement)), "std_disagreement": float(np.std(disagreement)),
        "mean_abs_disagreement": float(np.mean(np.abs(disagreement))),
        "mean_err_rf": float(np.mean(err_rf)), "mean_err_xgb": float(np.mean(err_xgb)),
    }
    log(f"Overall: mean disagreement (RF-XGB)={np.mean(disagreement):+.4f}, std={np.std(disagreement):.4f}, mean|disagreement|={np.mean(np.abs(disagreement)):.4f}")
    log(f"Overall: mean|err| RF={np.mean(err_rf):.4f}  XGB={np.mean(err_xgb):.4f}")

    # by ticker
    log("\n--- By ticker ---")
    tickers = sorted(set(r["ticker"] for r in test))
    by_ticker = {}
    for t in tickers:
        idx = [i for i, r in enumerate(test) if r["ticker"] == t]
        by_ticker[t] = {
            "n": len(idx),
            "mean_disagreement": float(np.mean(disagreement[idx])),
            "mean_abs_disagreement": float(np.mean(np.abs(disagreement[idx]))),
            "mean_err_rf": float(np.mean(err_rf[idx])), "mean_err_xgb": float(np.mean(err_xgb[idx])),
            "rf_more_accurate_pct": float(np.mean(who_is_more_accurate[idx] < 0) * 100),
        }
        log(f"  {t}: n={len(idx)} mean_disagree={by_ticker[t]['mean_disagreement']:+.4f} mean|disagree|={by_ticker[t]['mean_abs_disagreement']:.4f} "
            f"err_RF={by_ticker[t]['mean_err_rf']:.4f} err_XGB={by_ticker[t]['mean_err_xgb']:.4f} RF_more_accurate={by_ticker[t]['rf_more_accurate_pct']:.0f}% of days")
    report["check1_by_ticker"] = by_ticker

    # by time (quartiles of the test period)
    log("\n--- By chronological quartile of the test period ---")
    n = len(test)
    quartile_bounds = [0, n // 4, n // 2, 3 * n // 4, n]
    by_time = {}
    for qi in range(4):
        idx = list(range(quartile_bounds[qi], quartile_bounds[qi + 1]))
        dates_in_q = (test[idx[0]]["obs_date"], test[idx[-1]]["obs_date"])
        by_time[f"Q{qi+1}"] = {
            "n": len(idx), "date_range": dates_in_q,
            "mean_disagreement": float(np.mean(disagreement[idx])), "mean_abs_disagreement": float(np.mean(np.abs(disagreement[idx]))),
            "mean_err_rf": float(np.mean(err_rf[idx])), "mean_err_xgb": float(np.mean(err_xgb[idx])),
        }
        log(f"  Q{qi+1} ({dates_in_q[0]}..{dates_in_q[1]}, n={len(idx)}): mean_disagree={by_time[f'Q{qi+1}']['mean_disagreement']:+.4f} "
            f"err_RF={by_time[f'Q{qi+1}']['mean_err_rf']:.4f} err_XGB={by_time[f'Q{qi+1}']['mean_err_xgb']:.4f}")
    report["check1_by_time_quartile"] = by_time

    # by volatility regime (terciles of the ACTUAL target -- diagnostic only, not a live decision)
    log("\n--- By realized volatility regime (terciles of the actual target value) ---")
    tercile_edges = np.percentile(y_test, [33.33, 66.67])
    regime_labels = np.where(y_test <= tercile_edges[0], "low", np.where(y_test <= tercile_edges[1], "mid", "high"))
    by_regime = {}
    for regime in ["low", "mid", "high"]:
        idx = np.where(regime_labels == regime)[0]
        by_regime[regime] = {
            "n": int(len(idx)), "target_range": (float(np.min(y_test[idx])), float(np.max(y_test[idx]))),
            "mean_disagreement": float(np.mean(disagreement[idx])), "mean_abs_disagreement": float(np.mean(np.abs(disagreement[idx]))),
            "mean_err_rf": float(np.mean(err_rf[idx])), "mean_err_xgb": float(np.mean(err_xgb[idx])),
        }
        log(f"  {regime} vol (target {by_regime[regime]['target_range'][0]:.3f}-{by_regime[regime]['target_range'][1]:.3f}, n={len(idx)}): "
            f"mean_disagree={by_regime[regime]['mean_disagreement']:+.4f} err_RF={by_regime[regime]['mean_err_rf']:.4f} err_XGB={by_regime[regime]['mean_err_xgb']:.4f}")
    report["check1_by_vol_regime"] = by_regime

    # =========================================================================
    # CHECK 2: Feature importance comparison
    # =========================================================================
    log("\n" + "=" * 100)
    log("CHECK 2: Feature importance comparison (RF vs XGBoost)")
    log("=" * 100)

    rf_importance = dict(zip(FEATURES, rf.feature_importances_.tolist()))
    xgb_importance_gain = dict(zip(FEATURES, xgb_model.feature_importances_.tolist()))

    log("\n--- Native importances (RF: mean decrease impurity, XGBoost: gain) ---")
    log(f"{'Feature':<32}{'RF (impurity)':<18}{'XGBoost (gain)':<18}")
    for f in FEATURES:
        log(f"{f:<32}{rf_importance[f]:<18.4f}{xgb_importance_gain[f]:<18.4f}")
    report["check2_native_importance"] = {"rf_impurity": rf_importance, "xgb_gain": xgb_importance_gain}

    log("\n--- Permutation importance on the SAME test set (fairest apples-to-apples comparison) ---")
    perm_rf = permutation_importance(rf, X_test, y_test, n_repeats=20, random_state=42, scoring="r2")
    perm_xgb = permutation_importance(xgb_model, X_test, y_test, n_repeats=20, random_state=42, scoring="r2")
    perm_rf_dict = {f: float(perm_rf.importances_mean[i]) for i, f in enumerate(FEATURES)}
    perm_xgb_dict = {f: float(perm_xgb.importances_mean[i]) for i, f in enumerate(FEATURES)}
    log(f"{'Feature':<32}{'RF (perm R2 drop)':<20}{'XGBoost (perm R2 drop)':<20}")
    for f in FEATURES:
        log(f"{f:<32}{perm_rf_dict[f]:<20.4f}{perm_xgb_dict[f]:<20.4f}")
    report["check2_permutation_importance"] = {"rf": perm_rf_dict, "xgb": perm_xgb_dict}

    rf_top3 = sorted(perm_rf_dict, key=perm_rf_dict.get, reverse=True)[:3]
    xgb_top3 = sorted(perm_xgb_dict, key=perm_xgb_dict.get, reverse=True)[:3]
    log(f"\nRF top-3 features (permutation): {rf_top3}")
    log(f"XGBoost top-3 features (permutation): {xgb_top3}")
    log(f"Overlap: {set(rf_top3) & set(xgb_top3)}")
    report["check2_top3_overlap"] = {"rf_top3": rf_top3, "xgb_top3": xgb_top3, "overlap": list(set(rf_top3) & set(xgb_top3))}

    # =========================================================================
    # CHECK 3: Stability across seeds and nearby hyperparameters
    # =========================================================================
    log("\n" + "=" * 100)
    log("CHECK 3: Stability check -- does XGBoost's result flip with seed/hyperparameter changes?")
    log("=" * 100)

    log("\n--- Seed sensitivity (same hyperparameters, seeds 42-48) ---")
    seed_results = {"rf": {}, "xgb": {}}
    for seed in range(42, 49):
        rf_s = RandomForestRegressor(n_estimators=300, random_state=seed, **RF_PARAMS).fit(X_trainval, y_trainval)
        xgb_s = xgb.XGBRegressor(n_estimators=200, learning_rate=0.05, random_state=seed, **XGB_PARAMS).fit(X_trainval, y_trainval)
        r2_rf_s = r2_score(y_test, rf_s.predict(X_test))
        r2_xgb_s = r2_score(y_test, xgb_s.predict(X_test))
        seed_results["rf"][seed] = float(r2_rf_s)
        seed_results["xgb"][seed] = float(r2_xgb_s)
        log(f"  seed={seed}: R2_RF={r2_rf_s:+.4f}  R2_XGB={r2_xgb_s:+.4f}")
    rf_seed_vals = list(seed_results["rf"].values())
    xgb_seed_vals = list(seed_results["xgb"].values())
    log(f"\nRF across seeds:  mean={np.mean(rf_seed_vals):+.4f} std={np.std(rf_seed_vals):.4f} range=[{min(rf_seed_vals):+.4f}, {max(rf_seed_vals):+.4f}] all_positive={all(v>0 for v in rf_seed_vals)}")
    log(f"XGB across seeds: mean={np.mean(xgb_seed_vals):+.4f} std={np.std(xgb_seed_vals):.4f} range=[{min(xgb_seed_vals):+.4f}, {max(xgb_seed_vals):+.4f}] all_negative={all(v<0 for v in xgb_seed_vals)}")
    report["check3_seed_sensitivity"] = seed_results

    log("\n--- Nearby-hyperparameter sensitivity for XGBoost (toggling one param at a time from the found optimum) ---")
    base = dict(XGB_PARAMS)
    variants = {
        "base (found optimum)": dict(base),
        "subsample 0.7 (was 0.8)": {**base, "subsample": 0.7},
        "colsample_bytree 0.7 (was 0.8)": {**base, "colsample_bytree": 0.7},
        "reg_alpha 0.1 (was 1.0)": {**base, "reg_alpha": 0.1},
        "reg_lambda 5.0 (was 1.0)": {**base, "reg_lambda": 5.0},
        "max_depth 2 (was 3)": {**base, "max_depth": 2},
        "min_child_weight 10 (was 5)": {**base, "min_child_weight": 10},
    }
    xgb_hparam_results = {}
    for name, params in variants.items():
        m = xgb.XGBRegressor(n_estimators=200, learning_rate=0.05, random_state=42, **params).fit(X_trainval, y_trainval)
        r2_v = r2_score(y_test, m.predict(X_test))
        xgb_hparam_results[name] = float(r2_v)
        log(f"  {name}: R2={r2_v:+.4f}")
    report["check3_xgb_hyperparameter_sensitivity"] = xgb_hparam_results

    # =========================================================================
    # CHECK 4: Overfitting diagnostics (train vs test gap)
    # =========================================================================
    log("\n" + "=" * 100)
    log("CHECK 4: Overfitting diagnostics -- train (in-sample) vs test performance gap")
    log("=" * 100)

    pred_ridge_train = ridge.predict(X_trainval)
    pred_rf_train = rf.predict(X_trainval)
    pred_xgb_train = xgb_model.predict(X_trainval)

    overfitting = {}
    for name, pred_train, pred_test_ in [("Ridge", pred_ridge_train, pred_ridge), ("RandomForest", pred_rf_train, pred_rf), ("XGBoost", pred_xgb_train, pred_xgb)]:
        r2_train = r2_score(y_trainval, pred_train)
        r2_test = r2_score(y_test, pred_test_)
        mae_train = mean_absolute_error(y_trainval, pred_train)
        mae_test = mean_absolute_error(y_test, pred_test_)
        overfitting[name] = {
            "r2_train": float(r2_train), "r2_test": float(r2_test), "r2_gap": float(r2_train - r2_test),
            "mae_train": float(mae_train), "mae_test": float(mae_test), "mae_gap": float(mae_test - mae_train),
        }
        log(f"  {name}: R2_train={r2_train:.4f} R2_test={r2_test:.4f} GAP={r2_train-r2_test:.4f}  |  MAE_train={mae_train:.4f} MAE_test={mae_test:.4f} GAP={mae_test-mae_train:.4f}")
    report["check4_overfitting"] = overfitting

    with open("rf_xgboost_disagreement_investigation.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log("\nFull results written to rf_xgboost_disagreement_investigation.json")


if __name__ == "__main__":
    main()

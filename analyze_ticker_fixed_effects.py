from dotenv import load_dotenv
load_dotenv()

"""
Ticker-fixed-effects diagnostic (Option A, per explicit user instruction,
2026-09-28) -- applied to all four experiments built on
xgboost_volatility_dataset.db's forward-realized-volatility target:
xgboost_volatility_prediction_v1_20260925 (Section 45), randomforest_
volatility_prediction_v1/v2_20260925 (Sections 46/48), and
xgboost_volatility_prediction_regularized_v2_20260925 (Section 51/54/56).

TRIGGER: the regularized XGBoost v2 shuffled_target_placebo re-leaked (4/8
seeds) on the clean (post-contamination-fix) dataset. Root-caused: real
per-ticker mean target levels vary ~4x (AAPL 0.24 to SMCI 0.92), and a
GLOBAL (non-ticker-blocked) label shuffle doesn't fully destroy that
between-ticker structure -- for any one random permutation, a model that
can even weakly infer ticker identity from the features can exploit the
residual, chance-driven per-ticker mean. Confirmed directly: a model using
ZERO options features -- just "which ticker, predict its own historical
average" -- scores R2=0.5078 on regularized XGBoost v2's own real primary
test set, HIGHER than that experiment's own real, fully-tuned 8-feature
XGBoost result (R2=0.4971/0.5007).

THIS SCRIPT answers the follow-up question directly: once every model is
GIVEN ticker identity explicitly (as one-hot dummy columns, added
alongside the real 8 features), how much do the 8 real options-derived
features add BEYOND that ticker-fixed-effects baseline? Applied
identically to all four experiments so the answer is comparable across
all of them, not just the one that surfaced the issue.

SCOPE DISCLOSURE, stated plainly, not hidden: this reuses each experiment's
ALREADY-TUNED hyperparameters (found via nested CV on the 8-features-only
input space) and simply refits with [8 features + 6 ticker dummies] as the
input matrix. Hyperparameters were NOT re-tuned for the enlarged input
space -- a full re-tune would be a much larger undertaking (re-running all
four Stage 1 pipelines' nested-CV grid searches from scratch). This is a
diagnostic-scale analysis, matching the effort level of this project's
other diagnostic investigations (Sections 47/49/50), not a new formal
Stage 1 rerun. Ridge's alpha and RF/XGBoost's regularization strength were
also not re-tuned for the enlarged space.

Does NOT touch the placebo mechanism, the gap-closure question, or any
pre-registration file. Read-only analysis against each experiment's own
already-generated dataset and already-confirmed hyperparameters/results.
"""

import numpy as np
from sklearn.linear_model import Ridge, LinearRegression
from sklearn.metrics import r2_score
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

import xgboost_volatility_stage1_execution as v1          # shared "unlocked" split (RF v1/v2 + XGBoost v1)
import xgboost_volatility_v2_stage1_execution as v2        # regularized XGBoost v2's own locked split


def one_hot(tickers, cats):
    return np.array([[1.0 if t == c else 0.0 for c in cats] for t in tickers])


def ticker_only_baseline(y_trainval, tickers_trainval, y_primary, tickers_primary):
    means = {t: y_trainval[tickers_trainval == t].mean() for t in sorted(set(tickers_trainval))}
    pred = np.array([means[t] for t in tickers_primary])
    return r2_score(y_primary, pred), means


def run_group_unlocked_split():
    """RF v1, RF v2 (identical shared split/model), and XGBoost v1."""
    print("=" * 100)
    print("GROUP 1: shared 'unlocked' split (RF v1, RF v2, XGBoost v1) -- xgboost_volatility_stage1_execution.py's split")
    print("=" * 100)

    data = v1.load_rows()
    train, val, test, train_end, val_end = v1.chronological_split(data)
    train_val = train + val
    primary_test = v1.build_primary_test_set(test)
    print(f"train_val n={len(train_val)}, primary_test n={len(primary_test)} (train ends {train_end}, val ends {val_end})")

    X_tv_raw, y_tv = v1.to_xy(train_val, v1.PRIMARY_HORIZON)
    X_p_raw, y_p = v1.to_xy(primary_test, v1.PRIMARY_HORIZON)
    scaler = StandardScaler().fit(X_tv_raw)
    X_tv = scaler.transform(X_tv_raw)
    X_p = scaler.transform(X_p_raw)

    tickers_tv = np.array([r["ticker"] for r in train_val])
    tickers_p = np.array([r["ticker"] for r in primary_test])
    all_tickers = sorted(set(tickers_tv))
    D_tv = one_hot(tickers_tv, all_tickers)
    D_p = one_hot(tickers_p, all_tickers)

    r2_baseline, means = ticker_only_baseline(y_tv, tickers_tv, y_p, tickers_p)
    print(f"\nTicker-only baseline (per-ticker mean, no features at all): R2 = {r2_baseline:.4f}")
    print("Per-ticker means:", {t: round(v, 4) for t, v in means.items()})

    X_tv_aug = np.hstack([X_tv, D_tv])
    X_p_aug = np.hstack([X_p, D_p])

    # --- Model A: Ridge, already-tuned alpha=50.0 (confirmed from the real reruns) ---
    ridge_alpha = 50.0
    ma = Ridge(alpha=ridge_alpha, random_state=42).fit(X_tv_aug, y_tv)
    r2_ridge_aug = r2_score(y_p, ma.predict(X_p_aug))
    print(f"\n[Model A] Ridge (alpha={ridge_alpha}) + 8 features + ticker dummies: R2 = {r2_ridge_aug:.4f} "
          f"(incremental over ticker-only baseline: {r2_ridge_aug - r2_baseline:+.4f})")

    # --- Model B, RF v1/v2 shared config: max_depth=4, min_samples_leaf=10, max_features='sqrt' ---
    rf_params = {"max_depth": 4, "min_samples_leaf": 10, "max_features": "sqrt"}
    mb_rf = RandomForestRegressor(n_estimators=300, random_state=42, **rf_params).fit(X_tv_aug, y_tv)
    r2_rf_aug = r2_score(y_p, mb_rf.predict(X_p_aug))
    print(f"[Model B, RF v1/v2 shared config {rf_params}] + 8 features + ticker dummies: R2 = {r2_rf_aug:.4f} "
          f"(incremental over ticker-only baseline: {r2_rf_aug - r2_baseline:+.4f})")

    # --- Model B, XGBoost v1 config: max_depth=2, min_child_weight=10, reg_alpha=1.0, reg_lambda=5.0,
    #     learning_rate=0.05, subsample=0.7, colsample_bytree=0.7, n_estimators=200 ---
    xgb_v1_params = {"max_depth": 2, "min_child_weight": 10, "reg_alpha": 1.0, "reg_lambda": 5.0,
                      "subsample": 0.7, "colsample_bytree": 0.7}
    mb_xgb1 = xgb.XGBRegressor(n_estimators=200, learning_rate=0.05, random_state=42, **xgb_v1_params).fit(X_tv_aug, y_tv)
    r2_xgb1_aug = r2_score(y_p, mb_xgb1.predict(X_p_aug))
    print(f"[Model B, XGBoost v1 config {xgb_v1_params}] + 8 features + ticker dummies: R2 = {r2_xgb1_aug:.4f} "
          f"(incremental over ticker-only baseline: {r2_xgb1_aug - r2_baseline:+.4f})")

    return {
        "n_trainval": len(train_val), "n_primary": len(primary_test),
        "ticker_only_baseline_r2": r2_baseline,
        "ridge_aug_r2": r2_ridge_aug, "ridge_incremental": r2_ridge_aug - r2_baseline,
        "rf_aug_r2": r2_rf_aug, "rf_incremental": r2_rf_aug - r2_baseline,
        "xgb_v1_aug_r2": r2_xgb1_aug, "xgb_v1_incremental": r2_xgb1_aug - r2_baseline,
    }


def run_regularized_xgb_v2():
    """Regularized XGBoost v2's own locked Stage-1 window."""
    print("\n" + "=" * 100)
    print("GROUP 2: regularized XGBoost v2's own locked split (obs_date<=2026-07-15)")
    print("=" * 100)

    data = v2.load_rows()
    train, val, test, train_end, val_end = v2.chronological_split(data)
    train_val = train + val
    primary_test = v2.build_primary_test_set(test)
    print(f"train_val n={len(train_val)}, primary_test n={len(primary_test)} (train ends {train_end}, val ends {val_end})")

    X_tv_raw, y_tv = v2.to_xy(train_val, v2.PRIMARY_HORIZON)
    X_p_raw, y_p = v2.to_xy(primary_test, v2.PRIMARY_HORIZON)
    scaler = StandardScaler().fit(X_tv_raw)
    X_tv = scaler.transform(X_tv_raw)
    X_p = scaler.transform(X_p_raw)

    tickers_tv = np.array([r["ticker"] for r in train_val])
    tickers_p = np.array([r["ticker"] for r in primary_test])
    all_tickers = sorted(set(tickers_tv))
    D_tv = one_hot(tickers_tv, all_tickers)
    D_p = one_hot(tickers_p, all_tickers)

    r2_baseline, means = ticker_only_baseline(y_tv, tickers_tv, y_p, tickers_p)
    print(f"\nTicker-only baseline (per-ticker mean, no features at all): R2 = {r2_baseline:.4f}")
    print("Per-ticker means:", {t: round(v, 4) for t, v in means.items()})

    X_tv_aug = np.hstack([X_tv, D_tv])
    X_p_aug = np.hstack([X_p, D_p])

    ridge_alpha = 50.0  # confirmed from the fresh clean rerun's own printed params
    ma = Ridge(alpha=ridge_alpha, random_state=42).fit(X_tv_aug, y_tv)
    r2_ridge_aug = r2_score(y_p, ma.predict(X_p_aug))
    print(f"\n[Model A] Ridge (alpha={ridge_alpha}) + 8 features + ticker dummies: R2 = {r2_ridge_aug:.4f} "
          f"(incremental over ticker-only baseline: {r2_ridge_aug - r2_baseline:+.4f})")

    # Regularized XGBoost v2's own tuned config, reusing best_iter=554 as a fixed n_estimators
    # (disclosed: early stopping itself is not re-run against the enlarged input space here)
    xgb_v2_params = {"max_depth": 2, "min_child_weight": 15, "reg_alpha": 5.0, "reg_lambda": 10.0,
                      "learning_rate": 0.01, "subsample": 0.6, "colsample_bytree": 0.7}
    mb_xgb2 = xgb.XGBRegressor(n_estimators=554, random_state=42, **xgb_v2_params).fit(X_tv_aug, y_tv)
    r2_xgb2_aug = r2_score(y_p, mb_xgb2.predict(X_p_aug))
    print(f"[Model B, regularized XGBoost v2 config {xgb_v2_params}, n_estimators=554] + 8 features + ticker dummies: "
          f"R2 = {r2_xgb2_aug:.4f} (incremental over ticker-only baseline: {r2_xgb2_aug - r2_baseline:+.4f})")

    return {
        "n_trainval": len(train_val), "n_primary": len(primary_test),
        "ticker_only_baseline_r2": r2_baseline,
        "ridge_aug_r2": r2_ridge_aug, "ridge_incremental": r2_ridge_aug - r2_baseline,
        "xgb_v2_aug_r2": r2_xgb2_aug, "xgb_v2_incremental": r2_xgb2_aug - r2_baseline,
    }


if __name__ == "__main__":
    g1 = run_group_unlocked_split()
    g2 = run_regularized_xgb_v2()

    print("\n" + "=" * 100)
    print("SUMMARY -- incremental R2 of the 8 real features BEYOND a ticker-fixed-effects baseline")
    print("=" * 100)
    print(f"RF v1 / RF v2 (shared split+model): ticker-only={g1['ticker_only_baseline_r2']:.4f}, "
          f"Ridge+dummies={g1['ridge_aug_r2']:.4f} (incr {g1['ridge_incremental']:+.4f}), "
          f"RF+dummies={g1['rf_aug_r2']:.4f} (incr {g1['rf_incremental']:+.4f})")
    print(f"XGBoost v1: ticker-only={g1['ticker_only_baseline_r2']:.4f}, "
          f"Ridge+dummies={g1['ridge_aug_r2']:.4f} (incr {g1['ridge_incremental']:+.4f}), "
          f"XGBoost+dummies={g1['xgb_v1_aug_r2']:.4f} (incr {g1['xgb_v1_incremental']:+.4f})")
    print(f"Regularized XGBoost v2: ticker-only={g2['ticker_only_baseline_r2']:.4f}, "
          f"Ridge+dummies={g2['ridge_aug_r2']:.4f} (incr {g2['ridge_incremental']:+.4f}), "
          f"reg.XGBoost+dummies={g2['xgb_v2_aug_r2']:.4f} (incr {g2['xgb_v2_incremental']:+.4f})")

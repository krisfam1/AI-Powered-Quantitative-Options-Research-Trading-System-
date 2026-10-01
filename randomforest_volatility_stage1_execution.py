from dotenv import load_dotenv
load_dotenv()

"""
Stage 1 execution for the Random-Forest-vs-Ridge forward-realized-
volatility pre-registration (CLAUDE.md Section 46,
preregister_randomforest_volatility_experiment.py, config_hash
0655c4a23b41024954b07f29fb5d813b873fd14d9dd145f17640a3549af4557e).

Reuses xgboost_volatility_dataset.db's existing, already-verified 4,027-
row dataset unmodified -- zero new data collection. Does NOT call
preregister_experiment() or run_experiment(). This is Stage 1 ONLY --
Stage 2 (the genuinely rolling, currently-empty out-of-sample window
starting 2026-07-16) is not addressed here; overall VALIDATED status
requires Stage 2 separately, per the pre-registration's own decision
rules.

Model A = Ridge, 8 features. Model B = Random Forest, SAME 8 features
(swapped from the closed XGBoost-volatility experiment, which used
XGBoost as Model B and Random Forest only as its alternate-model
robustness check). The alternate-model robustness check here is
correspondingly XGBoost, closing the loop.
"""

import json
import sqlite3
import warnings
from datetime import datetime

import numpy as np
from scipy.stats import wilcoxon
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

warnings.filterwarnings("ignore")

DB_PATH = "xgboost_volatility_dataset.db"

FEATURES = [
    "term_structure_slope_pct", "oi_skew", "trailing_realized_vol_20d",
    "delta", "gamma", "theta", "charm", "vega_per_1pct_iv",
]
TARGET_COL_BY_HORIZON = {10: "target_realized_vol_10d", 20: "target_realized_vol_20d", 50: "target_realized_vol_50d"}
PRIMARY_HORIZON = 20

TUNING_SEED = 42
PRIMARY_ALPHA_CORRECTED = 0.0167
EFFECT_SIZE_THRESHOLD_R2 = 0.05
MIN_N_PRIMARY = 100

RIDGE_ALPHA_GRID = [0.1, 1.0, 10.0, 50.0, 100.0]

RF_GRID = [
    {"max_depth": md, "min_samples_leaf": msl, "max_features": mf}
    for md in (4, 6, 8) for msl in (5, 10) for mf in ("sqrt", "log2")
]

XGB_GRID = [
    {"max_depth": md, "min_child_weight": mcw, "reg_alpha": ra, "reg_lambda": rl, "subsample": ss, "colsample_bytree": cb}
    for md in (2, 3) for mcw in (5, 10) for ra in (0.1, 1.0) for rl in (1.0, 5.0) for ss in (0.7, 0.8) for cb in (0.7, 0.8)
]


def log(msg: str) -> None:
    print(f"[{datetime.now().isoformat()}] {msg}", flush=True)


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


def iso_week_key(date_str):
    y, w, _ = datetime.strptime(date_str, "%Y-%m-%d").isocalendar()
    return (y, w)


def build_primary_test_set(test_rows):
    seen = set()
    primary = []
    for r in test_rows:
        key = (r["ticker"], iso_week_key(r["obs_date"]))
        if key in seen:
            continue
        seen.add(key)
        primary.append(r)
    return primary


def to_xy(rows, horizon):
    X = np.array([[r[f] for f in FEATURES] for r in rows], dtype=float)
    y = np.array([r[TARGET_COL_BY_HORIZON[horizon]] for r in rows], dtype=float)
    return X, y


def tune_and_fit_ridge(X_train, y_train, seed):
    tscv = TimeSeriesSplit(n_splits=5)
    best_alpha, best_score = None, np.inf
    for alpha in RIDGE_ALPHA_GRID:
        fold_errs = []
        for tr_idx, va_idx in tscv.split(X_train):
            m = Ridge(alpha=alpha, random_state=seed)
            m.fit(X_train[tr_idx], y_train[tr_idx])
            pred = m.predict(X_train[va_idx])
            fold_errs.append(float(np.mean(np.abs(y_train[va_idx] - pred))))
        mean_err = float(np.mean(fold_errs))
        if mean_err < best_score:
            best_score, best_alpha = mean_err, alpha
    final_model = Ridge(alpha=best_alpha, random_state=seed)
    final_model.fit(X_train, y_train)
    return final_model, {"alpha": best_alpha}, best_score


def tune_and_fit_rf(X_train, y_train, seed):
    tscv = TimeSeriesSplit(n_splits=5)
    best_params, best_score = None, np.inf
    for params in RF_GRID:
        fold_errs = []
        for tr_idx, va_idx in tscv.split(X_train):
            m = RandomForestRegressor(n_estimators=300, random_state=TUNING_SEED, **params)
            m.fit(X_train[tr_idx], y_train[tr_idx])
            pred = m.predict(X_train[va_idx])
            fold_errs.append(float(np.mean(np.abs(y_train[va_idx] - pred))))
        mean_err = float(np.mean(fold_errs))
        if mean_err < best_score:
            best_score, best_params = mean_err, params
    final_model = RandomForestRegressor(n_estimators=300, random_state=seed, **best_params)
    final_model.fit(X_train, y_train)
    return final_model, best_params, best_score


def tune_and_fit_xgb(X_train, y_train, seed):
    tscv = TimeSeriesSplit(n_splits=5)
    best_params, best_score = None, np.inf
    for params in XGB_GRID:
        fold_errs = []
        for tr_idx, va_idx in tscv.split(X_train):
            m = xgb.XGBRegressor(n_estimators=200, learning_rate=0.05, random_state=TUNING_SEED, **params)
            m.fit(X_train[tr_idx], y_train[tr_idx])
            pred = m.predict(X_train[va_idx])
            fold_errs.append(float(np.mean(np.abs(y_train[va_idx] - pred))))
        mean_err = float(np.mean(fold_errs))
        if mean_err < best_score:
            best_score, best_params = mean_err, params
    final_model = xgb.XGBRegressor(n_estimators=200, learning_rate=0.05, random_state=seed, **best_params)
    final_model.fit(X_train, y_train)
    return final_model, best_params, best_score


def abs_err(y_true, y_pred):
    return np.abs(y_true - y_pred)


def wilcoxon_b_beats_a(err_a, err_b):
    diffs = err_a - err_b
    if len(diffs) < 10 or not np.any(diffs != 0):
        return None, None
    stat, p = wilcoxon(diffs, alternative="greater")
    return float(stat), float(p)


def main():
    report = {}
    log("Loading data...")
    data = load_rows()
    report["total_rows"] = len(data)
    log(f"Loaded {len(data)} rows")

    train, val, test, train_end, val_end = chronological_split(data)
    train_val = train + val
    report["split"] = {
        "train_n": len(train), "val_n": len(val), "test_n": len(test),
        "train_start": data[0]["obs_date"], "train_end": train_end, "val_end": val_end, "test_end": data[-1]["obs_date"],
    }
    log(f"Split: train={len(train)} ({data[0]['obs_date']}..{train_end}), val={len(val)} (..{val_end}), test={len(test)} (..{data[-1]['obs_date']})")
    log(f"Sanity check vs. pre-registration's cited boundaries (2023-10-02/2025-06-16/2025-12-30/2026-07-15): "
        f"{'MATCH' if (train_end == '2025-06-16' and val_end == '2025-12-30' and data[-1]['obs_date'] == '2026-07-15') else 'MISMATCH -- INVESTIGATE'}")

    primary_test = build_primary_test_set(test)
    report["primary_test_n"] = len(primary_test)
    log(f"Primary (thinned) test set: {len(primary_test)} observations")

    tickers = sorted(set(r["ticker"] for r in data))

    X_trainval_raw, y_trainval = to_xy(train_val, PRIMARY_HORIZON)
    scaler = StandardScaler().fit(X_trainval_raw)
    X_trainval = scaler.transform(X_trainval_raw)
    X_primary_raw, y_primary = to_xy(primary_test, PRIMARY_HORIZON)
    X_primary = scaler.transform(X_primary_raw)
    X_test_raw, y_test_full = to_xy(test, PRIMARY_HORIZON)
    X_test_full = scaler.transform(X_test_raw)

    log("Tuning + fitting Model A (Ridge)...")
    model_a, ridge_params, ridge_cv = tune_and_fit_ridge(X_trainval, y_trainval, seed=42)
    log(f"Model A (Ridge) best params: {ridge_params} (mean CV MAE {ridge_cv:.6f})")

    log("Tuning + fitting Model B (Random Forest)...")
    model_b, rf_params, rf_cv = tune_and_fit_rf(X_trainval, y_trainval, seed=42)
    log(f"Model B (Random Forest) best params: {rf_params} (mean CV MAE {rf_cv:.6f})")

    report["model_a_params"] = ridge_params
    report["model_b_params"] = rf_params

    model_a_43 = Ridge(alpha=ridge_params["alpha"], random_state=43).fit(X_trainval, y_trainval)
    model_b_43 = RandomForestRegressor(n_estimators=300, random_state=43, **rf_params).fit(X_trainval, y_trainval)

    primary_result = {}
    for seed, ma, mb in [(42, model_a, model_b), (43, model_a_43, model_b_43)]:
        pa = ma.predict(X_primary)
        pb = mb.predict(X_primary)
        err_a = abs_err(y_primary, pa)
        err_b = abs_err(y_primary, pb)
        r2_a = r2_score(y_primary, pa)
        r2_b = r2_score(y_primary, pb)
        stat, p = wilcoxon_b_beats_a(err_a, err_b)
        primary_result[f"seed{seed}"] = {
            "r2_a": float(r2_a), "r2_b": float(r2_b), "r2_delta": float(r2_b - r2_a),
            "mae_a": float(np.mean(err_a)), "mae_b": float(np.mean(err_b)),
            "wilcoxon_stat": stat, "wilcoxon_p_one_sided": p,
        }
        log(f"PRIMARY seed={seed}: R2_A={r2_a:.4f} R2_B={r2_b:.4f} delta={r2_b-r2_a:+.4f} MAE_A={np.mean(err_a):.6f} MAE_B={np.mean(err_b):.6f} p={p}")
    report["primary_result"] = primary_result

    pa_full = model_a.predict(X_test_full)
    pb_full = model_b.predict(X_test_full)
    report["full_test_set_descriptive"] = {
        "n": len(test), "r2_a": float(r2_score(y_test_full, pa_full)), "r2_b": float(r2_score(y_test_full, pb_full)),
    }
    log(f"Full test set (descriptive): n={len(test)} R2_A={report['full_test_set_descriptive']['r2_a']:.4f} R2_B={report['full_test_set_descriptive']['r2_b']:.4f}")

    # ---- Robustness 1: alternate_model:xgboost (swapped role) ----
    log("Robustness 1/5: alternate_model:xgboost...")
    xgb_model, xgb_params, xgb_cv = tune_and_fit_xgb(X_trainval, y_trainval, seed=42)
    xgb_pred = xgb_model.predict(X_primary)
    xgb_err = abs_err(y_primary, xgb_pred)
    pa42 = model_a.predict(X_primary)
    err_a42 = abs_err(y_primary, pa42)
    xgb_r2 = r2_score(y_primary, xgb_pred)
    r2_a42 = r2_score(y_primary, pa42)
    xgb_stat, xgb_p = wilcoxon_b_beats_a(err_a42, xgb_err)
    report["robustness_alternate_model_xgboost"] = {
        "params": xgb_params, "r2": float(xgb_r2), "r2_delta_vs_a": float(xgb_r2 - r2_a42),
        "wilcoxon_p": xgb_p, "direction_positive": bool((xgb_r2 - r2_a42) > 0),
    }
    log(f"  XGBoost: R2={xgb_r2:.4f} (vs Ridge {r2_a42:.4f}, delta={xgb_r2-r2_a42:+.4f}) p={xgb_p}")

    # ---- Robustness 2: leave_one_ticker_out (MANDATORY, watching for AMD/SMCI repeat) ----
    log("Robustness 2/5: leave_one_ticker_out (mandatory -- watching specifically for an AMD/SMCI repeat)...")
    loto = {}
    for excl in tickers:
        tv_sub = [r for r in train_val if r["ticker"] != excl]
        primary_sub = [r for r in primary_test if r["ticker"] != excl]
        if len(primary_sub) < 5:
            loto[excl] = {"note": "too few primary obs after exclusion", "n": len(primary_sub)}
            continue
        Xtv_sub_raw, ytv_sub = to_xy(tv_sub, PRIMARY_HORIZON)
        scaler_sub = StandardScaler().fit(Xtv_sub_raw)
        Xtv_sub = scaler_sub.transform(Xtv_sub_raw)
        Xp_sub_raw, yp_sub = to_xy(primary_sub, PRIMARY_HORIZON)
        Xp_sub = scaler_sub.transform(Xp_sub_raw)
        ma_sub = Ridge(alpha=ridge_params["alpha"], random_state=42).fit(Xtv_sub, ytv_sub)
        mb_sub = RandomForestRegressor(n_estimators=300, random_state=42, **rf_params).fit(Xtv_sub, ytv_sub)
        pa_sub = ma_sub.predict(Xp_sub)
        pb_sub = mb_sub.predict(Xp_sub)
        err_a_sub = abs_err(yp_sub, pa_sub)
        err_b_sub = abs_err(yp_sub, pb_sub)
        r2a_sub = r2_score(yp_sub, pa_sub)
        r2b_sub = r2_score(yp_sub, pb_sub)
        stat_sub, p_sub = wilcoxon_b_beats_a(err_a_sub, err_b_sub)
        loto[excl] = {"n": len(primary_sub), "r2_a": float(r2a_sub), "r2_b": float(r2b_sub), "r2_delta": float(r2b_sub - r2a_sub), "wilcoxon_p": p_sub}
        log(f"  excl {excl}: n={len(primary_sub)} R2_A={r2a_sub:.4f} R2_B={r2b_sub:.4f} delta={r2b_sub-r2a_sub:+.4f} p={p_sub}")
    report["robustness_leave_one_ticker_out"] = loto

    # ---- Robustness 3&4: alternate_horizon 10day, 50day ----
    log("Robustness 3-4/5: alternate_horizon 10day, 50day...")
    alt_horizon_results = {}
    for h in (10, 50):
        Xtv_h_raw, ytv_h = to_xy(train_val, h)
        scaler_h = StandardScaler().fit(Xtv_h_raw)
        Xtv_h = scaler_h.transform(Xtv_h_raw)
        Xp_h_raw, yp_h = to_xy(primary_test, h)
        Xp_h = scaler_h.transform(Xp_h_raw)
        ma_h, _, _ = tune_and_fit_ridge(Xtv_h, ytv_h, seed=42)
        mb_h, _, _ = tune_and_fit_rf(Xtv_h, ytv_h, seed=42)
        pa_h = ma_h.predict(Xp_h)
        pb_h = mb_h.predict(Xp_h)
        err_a_h = abs_err(yp_h, pa_h)
        err_b_h = abs_err(yp_h, pb_h)
        r2a_h = r2_score(yp_h, pa_h)
        r2b_h = r2_score(yp_h, pb_h)
        stat_h, p_h = wilcoxon_b_beats_a(err_a_h, err_b_h)
        alt_horizon_results[f"{h}day"] = {"r2_a": float(r2a_h), "r2_b": float(r2b_h), "r2_delta": float(r2b_h - r2a_h), "wilcoxon_p": p_h}
        log(f"  {h}-day: R2_A={r2a_h:.4f} R2_B={r2b_h:.4f} delta={r2b_h-r2a_h:+.4f} p={p_h}")
    report["robustness_alternate_horizon"] = alt_horizon_results

    # ---- Robustness 5: shuffled_target_placebo ----
    log("Robustness 5/5: shuffled_target_placebo...")
    rng = np.random.RandomState(42)
    y_trainval_shuf = y_trainval.copy()
    rng.shuffle(y_trainval_shuf)
    ma_shuf = Ridge(alpha=ridge_params["alpha"], random_state=42).fit(X_trainval, y_trainval_shuf)
    mb_shuf = RandomForestRegressor(n_estimators=300, random_state=42, **rf_params).fit(X_trainval, y_trainval_shuf)
    pa_shuf = ma_shuf.predict(X_primary)
    pb_shuf = mb_shuf.predict(X_primary)
    err_a_shuf = abs_err(y_primary, pa_shuf)
    err_b_shuf = abs_err(y_primary, pb_shuf)
    r2a_shuf = r2_score(y_primary, pa_shuf)
    r2b_shuf = r2_score(y_primary, pb_shuf)
    stat_shuf, p_shuf = wilcoxon_b_beats_a(err_a_shuf, err_b_shuf)
    placebo_significant = bool(p_shuf is not None and p_shuf < 0.05)
    report["robustness_shuffled_target_placebo"] = {
        "r2_a_shuffled": float(r2a_shuf), "r2_b_shuffled": float(r2b_shuf), "r2_delta_shuffled": float(r2b_shuf - r2a_shuf),
        "wilcoxon_p_shuffled": p_shuf, "significant_at_0.05": placebo_significant,
    }
    log(f"  SHUFFLED: R2_A={r2a_shuf:.4f} R2_B={r2b_shuf:.4f} delta={r2b_shuf-r2a_shuf:+.4f} p={p_shuf} (expect: NOT significant)")

    # ---- Concentration check ----
    log("Concentration check...")
    per_ticker = {}
    pa42_full = model_a.predict(X_primary)
    pb42_full = model_b.predict(X_primary)
    for t in tickers:
        idx = [i for i, r in enumerate(primary_test) if r["ticker"] == t]
        if len(idx) < 3:
            per_ticker[t] = {"n": len(idx), "note": "too few"}
            continue
        mean_diff = float(np.mean(abs_err(y_primary[idx], pa42_full[idx]) - abs_err(y_primary[idx], pb42_full[idx])))
        per_ticker[t] = {"n": len(idx), "mean_abs_err_diff_a_minus_b": mean_diff}
    report["concentration_check"] = {"per_ticker": per_ticker}
    for t, v in per_ticker.items():
        log(f"  {t}: {v}")

    # ---- Decision rules (Stage 1 only) ----
    log("\nApplying Stage 1 decision rules...")
    primary_n = len(primary_test)
    p42 = primary_result["seed42"]["wilcoxon_p_one_sided"]
    p43 = primary_result["seed43"]["wilcoxon_p_one_sided"]
    d42 = primary_result["seed42"]["r2_delta"]
    d43 = primary_result["seed43"]["r2_delta"]

    primary_significant = (p42 is not None and p42 < PRIMARY_ALPHA_CORRECTED) and (p43 is not None and p43 < PRIMARY_ALPHA_CORRECTED)
    effect_met = (d42 >= EFFECT_SIZE_THRESHOLD_R2) and (d43 >= EFFECT_SIZE_THRESHOLD_R2)
    xgb_ok = report["robustness_alternate_model_xgboost"]["direction_positive"]
    loto_ok = all(v.get("r2_delta", -1) > 0 for v in loto.values() if "r2_delta" in v)
    amd_smci_repeat = (loto.get("AMD", {}).get("r2_delta", 1) < 0) or (loto.get("SMCI", {}).get("r2_delta", 1) < 0)
    horizon_ok = all(v["r2_delta"] > 0 for v in alt_horizon_results.values())
    placebo_leaked = placebo_significant

    all_four_ok = xgb_ok and loto_ok and horizon_ok
    all_five_ok = all_four_ok and not placebo_leaked

    report["decision_inputs"] = {
        "primary_n": primary_n, "n_meets_floor": primary_n >= MIN_N_PRIMARY,
        "primary_significant_both_seeds": primary_significant, "effect_met_both_seeds": effect_met,
        "xgb_ok": xgb_ok, "loto_ok": loto_ok, "amd_smci_repeat_detected": amd_smci_repeat,
        "horizon_ok": horizon_ok, "placebo_leaked": placebo_leaked, "all_five_ok": all_five_ok,
    }

    if primary_n < MIN_N_PRIMARY:
        stage1_verdict, reason = "INCONCLUSIVE", f"Primary N={primary_n} < {MIN_N_PRIMARY}"
    elif primary_significant and effect_met and all_five_ok:
        stage1_verdict, reason = "VALIDATED (Stage 1 only -- overall status still requires Stage 2)", "All Stage 1 criteria met at both seeds, all 5 robustness checks pass, placebo clean, no AMD/SMCI repeat"
    else:
        reasons = []
        if placebo_leaked:
            reasons.append("PIPELINE/LEAKAGE FLAG: shuffled_target_placebo showed a significant effect")
        if not primary_significant:
            reasons.append(f"primary test not significant at corrected alpha={PRIMARY_ALPHA_CORRECTED} (both seeds)")
        if not effect_met:
            reasons.append("effect size (R2 delta) below 0.05 threshold (both seeds)")
        if not xgb_ok:
            reasons.append("alternate_model:xgboost: no positive effect / disagreement")
        if not loto_ok:
            reasons.append("leave_one_ticker_out: at least one exclusion reverses direction" + (" -- AMD/SMCI REPEAT DETECTED, matching the closed XGBoost experiment's own finding" if amd_smci_repeat else ""))
        if not horizon_ok:
            reasons.append("alternate_horizon: at least one horizon reverses direction")
        stage1_verdict = "REJECTED (pipeline/leakage flag)" if placebo_leaked else "REJECTED"
        reason = "; ".join(reasons)

    report["stage1_verdict"] = stage1_verdict
    report["stage1_verdict_reason"] = reason
    report["overall_status"] = "Stage 2 not yet run (currently 0 rows) -- overall VALIDATED/REJECTED/INCONCLUSIVE per the pre-registration's own rules requires Stage 2 regardless of this Stage 1 outcome"

    log("\n" + "=" * 100)
    log(f"STAGE 1 VERDICT: {stage1_verdict}")
    log(f"REASON: {reason}")
    log("OVERALL STATUS: Stage 2 not yet run -- see pre-registration's decision rules")
    log("=" * 100)

    with open("randomforest_volatility_stage1_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log("\nFull results written to randomforest_volatility_stage1_results.json")


if __name__ == "__main__":
    main()

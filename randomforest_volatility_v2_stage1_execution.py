from dotenv import load_dotenv
load_dotenv()

"""
Stage 1 execution for randomforest_volatility_prediction_v2_20260925
(CLAUDE.md Section 48, preregister_randomforest_volatility_v2_experiment.py,
config_hash 472bf091313098dadbb89b28a6ff039503f7232c1e34e7b7cfee497d563b1fc5).

Reuses xgboost_volatility_dataset.db's existing 4,027-row dataset, zero
new data collection. Does NOT call preregister_experiment() or
run_experiment(). Does NOT touch or reopen v1
(randomforest_volatility_prediction_v1_20260925, CLOSED/REJECTED).

Model A = Ridge, Model B = Random Forest, identical to v1. 6 declared
robustness checks (not 5): leave_one_ticker_out (AMD reported explicitly),
stability_across_seeds_and_hyperparameters (NEW), overfitting_diagnostic_
train_test_gap (NEW), shuffled_target_placebo, alternate_horizon:10day,
alternate_horizon:50day.
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
STABILITY_SEEDS = list(range(42, 49))  # 42-48, matching the diagnostic's own range


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

    # ---- Check 1/6: leave_one_ticker_out, AMD tracked explicitly ----
    log("Check 1/6: leave_one_ticker_out (AMD tracked and reported explicitly)...")
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
    report["check_leave_one_ticker_out"] = loto
    log(f"  >>> AMD-SPECIFIC RESULT (explicitly reported, not folded into the average): {loto.get('AMD')}")

    # ---- Check 2/6: stability_across_seeds_and_hyperparameters ----
    log("Check 2/6: stability_across_seeds_and_hyperparameters (7 seeds x tuned hparams, + 12 hparam combos x seed 42)...")
    stability = {"seeds": {}, "hyperparams": {}}
    for seed in STABILITY_SEEDS:
        ma_s = Ridge(alpha=ridge_params["alpha"], random_state=seed).fit(X_trainval, y_trainval)
        mb_s = RandomForestRegressor(n_estimators=300, random_state=seed, **rf_params).fit(X_trainval, y_trainval)
        pa_s = ma_s.predict(X_primary)
        pb_s = mb_s.predict(X_primary)
        r2a_s = r2_score(y_primary, pa_s)
        r2b_s = r2_score(y_primary, pb_s)
        stability["seeds"][seed] = {"r2_a": float(r2a_s), "r2_b": float(r2b_s), "r2_delta": float(r2b_s - r2a_s)}
        log(f"  seed={seed}: R2_A={r2a_s:+.4f} R2_B={r2b_s:+.4f} delta={r2b_s-r2a_s:+.4f}")
    for i, params in enumerate(RF_GRID):
        mb_h = RandomForestRegressor(n_estimators=300, random_state=42, **params).fit(X_trainval, y_trainval)
        pb_h = mb_h.predict(X_primary)
        r2b_h = r2_score(y_primary, pb_h)
        r2a_ref = primary_result["seed42"]["r2_a"]
        stability["hyperparams"][str(params)] = {"r2_b": float(r2b_h), "r2_delta": float(r2b_h - r2a_ref)}
        log(f"  hparams={params}: R2_B={r2b_h:+.4f} delta_vs_ridge={r2b_h-r2a_ref:+.4f}")
    all_seed_deltas_positive = all(v["r2_delta"] > 0 for v in stability["seeds"].values())
    all_hparam_deltas_positive = all(v["r2_delta"] > 0 for v in stability["hyperparams"].values())
    stability["all_seed_deltas_positive"] = all_seed_deltas_positive
    stability["all_hparam_deltas_positive"] = all_hparam_deltas_positive
    stability["pass"] = bool(all_seed_deltas_positive and all_hparam_deltas_positive)
    report["check_stability_across_seeds_and_hyperparameters"] = stability
    log(f"  >>> STABILITY CHECK: all_seed_deltas_positive={all_seed_deltas_positive} all_hparam_deltas_positive={all_hparam_deltas_positive} PASS={stability['pass']}")

    # ---- Check 3/6: overfitting_diagnostic_train_test_gap ----
    log("Check 3/6: overfitting_diagnostic_train_test_gap (RF gap vs Ridge gap, same split)...")
    pa_train = model_a.predict(X_trainval)
    pb_train = model_b.predict(X_trainval)
    r2a_train = r2_score(y_trainval, pa_train)
    r2b_train = r2_score(y_trainval, pb_train)
    r2a_test = report["full_test_set_descriptive"]["r2_a"]
    r2b_test = report["full_test_set_descriptive"]["r2_b"]
    gap_a = r2a_train - r2a_test
    gap_b = r2b_train - r2b_test
    overfitting_check = {
        "r2_a_train": float(r2a_train), "r2_a_test": float(r2a_test), "gap_a": float(gap_a),
        "r2_b_train": float(r2b_train), "r2_b_test": float(r2b_test), "gap_b": float(gap_b),
        "pass": bool(gap_b <= gap_a),
    }
    report["check_overfitting_diagnostic_train_test_gap"] = overfitting_check
    log(f"  Ridge: R2_train={r2a_train:.4f} R2_test={r2a_test:.4f} gap={gap_a:.4f}")
    log(f"  RF:    R2_train={r2b_train:.4f} R2_test={r2b_test:.4f} gap={gap_b:.4f}")
    log(f"  >>> OVERFITTING CHECK: RF_gap({gap_b:.4f}) <= Ridge_gap({gap_a:.4f}) = PASS={overfitting_check['pass']}")

    # ---- Check 4/6: alternate_horizon 10day, 50day ----
    log("Check 4-5/6: alternate_horizon 10day, 50day...")
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
    report["check_alternate_horizon"] = alt_horizon_results

    # ---- Check 6/6: shuffled_target_placebo ----
    log("Check 6/6: shuffled_target_placebo...")
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
    report["check_shuffled_target_placebo"] = {
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

    # ---- Decision rules ----
    log("\nApplying Stage 1 decision rules (6 declared checks, no isolated-failure carve-out)...")
    primary_n = len(primary_test)
    p42 = primary_result["seed42"]["wilcoxon_p_one_sided"]
    p43 = primary_result["seed43"]["wilcoxon_p_one_sided"]
    d42 = primary_result["seed42"]["r2_delta"]
    d43 = primary_result["seed43"]["r2_delta"]

    primary_significant = (p42 is not None and p42 < PRIMARY_ALPHA_CORRECTED) and (p43 is not None and p43 < PRIMARY_ALPHA_CORRECTED)
    effect_met = (d42 >= EFFECT_SIZE_THRESHOLD_R2) and (d43 >= EFFECT_SIZE_THRESHOLD_R2)

    loto_ok = all(v.get("r2_delta", -1) > 0 for v in loto.values() if "r2_delta" in v)
    amd_ok = loto.get("AMD", {}).get("r2_delta", -1) > 0
    stability_ok = stability["pass"]
    overfitting_ok = overfitting_check["pass"]
    horizon_ok = all(v["r2_delta"] > 0 for v in alt_horizon_results.values())
    placebo_leaked = placebo_significant

    all_six_ok = loto_ok and stability_ok and overfitting_ok and horizon_ok and not placebo_leaked

    report["decision_inputs"] = {
        "primary_n": primary_n, "n_meets_floor": primary_n >= MIN_N_PRIMARY,
        "primary_significant_both_seeds": primary_significant, "effect_met_both_seeds": effect_met,
        "loto_ok": loto_ok, "amd_ok": amd_ok, "stability_ok": stability_ok, "overfitting_ok": overfitting_ok,
        "horizon_ok": horizon_ok, "placebo_leaked": placebo_leaked, "all_six_ok": all_six_ok,
    }

    if primary_n < MIN_N_PRIMARY:
        stage1_verdict, reason = "INCONCLUSIVE", f"Primary N={primary_n} < {MIN_N_PRIMARY}"
    elif primary_significant and effect_met and all_six_ok:
        stage1_verdict, reason = "VALIDATED (Stage 1 only -- overall status still requires Stage 2)", "All Stage 1 criteria met at both seeds, all 6 robustness checks pass, placebo clean"
    else:
        reasons = []
        if placebo_leaked:
            reasons.append("PIPELINE/LEAKAGE FLAG: shuffled_target_placebo showed a significant effect")
        if not primary_significant:
            reasons.append(f"primary test not significant at corrected alpha={PRIMARY_ALPHA_CORRECTED} (both seeds)")
        if not effect_met:
            reasons.append("effect size (R2 delta) below 0.05 threshold (both seeds)")
        if not loto_ok:
            reasons.append("leave_one_ticker_out: at least one exclusion reverses direction" + (" (AMD specifically failed)" if not amd_ok else ""))
        if not stability_ok:
            reasons.append(f"stability_across_seeds_and_hyperparameters: FAILED (all_seed_positive={stability['all_seed_deltas_positive']}, all_hparam_positive={stability['all_hparam_deltas_positive']})")
        if not overfitting_ok:
            reasons.append(f"overfitting_diagnostic_train_test_gap: FAILED (RF gap {gap_b:.4f} > Ridge gap {gap_a:.4f})")
        if not horizon_ok:
            reasons.append("alternate_horizon: at least one horizon reverses direction")
        stage1_verdict = "REJECTED (pipeline/leakage flag)" if placebo_leaked else "REJECTED"
        reason = "; ".join(reasons)

    report["stage1_verdict"] = stage1_verdict
    report["stage1_verdict_reason"] = reason
    report["overall_status"] = "Stage 2 not yet run (currently 0 rows, shared state with v1) -- overall status requires Stage 2 regardless of this Stage 1 outcome, UNLESS Stage 1 is REJECTED (in which case Stage 2 is moot, same precedent as v1/GEX)"

    log("\n" + "=" * 100)
    log(f"STAGE 1 VERDICT: {stage1_verdict}")
    log(f"REASON: {reason}")
    log("=" * 100)

    with open("randomforest_volatility_v2_stage1_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log("\nFull results written to randomforest_volatility_v2_stage1_results.json")


if __name__ == "__main__":
    main()

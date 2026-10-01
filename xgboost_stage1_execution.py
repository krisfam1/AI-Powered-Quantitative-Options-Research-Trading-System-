from dotenv import load_dotenv
load_dotenv()

"""
Stage 1 execution for the XGBoost feature-interaction pre-registration
(CLAUDE.md Section 44, preregister_xgboost_interaction_experiment.py,
config_hash 35b5e9b722d3f87928819a29dd0c72584c3d9d0d9b696e135a34f555409fd31f).

Reads the already-generated, already-verified 2,599-row dataset from
ml_xgboost_interaction_data.db (2026-09-25 generation pass). Does NOT
call preregister_experiment() or run_experiment() -- consistent with how
every other GEX/IV/strike-family "Stage 1 EXECUTED" section in this
project was actually run (a direct analysis script + CLAUDE.md record,
not the heavier gates/verdict framework, which only ML Experiment 1 has
ever gone through).

Model A = XGBoost on the 13 base features only.
Model B = XGBoost on the 13 base features + the 3 named interaction
features. THERE IS NO RIDGE BASELINE IN THIS DESIGN -- the locked
pre-registration's own text is explicit: "This is testing the specific
interaction terms, not 'XGBoost is generally better than Ridge' -- the
comparison holds model class constant (XGBoost vs. XGBoost)." Ridge was
ML Experiment 1's baseline, a different, already-REJECTED experiment.
"""

import json
import sqlite3
import warnings
from datetime import datetime

import numpy as np
from scipy.stats import wilcoxon
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
import xgboost as xgb

warnings.filterwarnings("ignore")

DB_PATH = "ml_xgboost_interaction_data.db"

BASE_FEATURES = [
    "delta", "gamma", "theta", "charm", "vega_per_1pct_iv",
    "realized_volatility", "realized_vol_percentile", "relative_volume",
    "breakout_magnitude_score", "trend_strength_score", "momentum_score",
    "moneyness", "dte",
]
INTERACTIONS = [
    "realized_volatility_x_relative_volume", "gamma_x_moneyness",
    "breakout_magnitude_score_x_trend_strength_score",
]
ALL_FEATURES = BASE_FEATURES + INTERACTIONS

RANDOM_SEEDS = [42, 43]  # matches this project's established seed pair
TUNING_SEED = 42  # used for the nested-CV grid search itself; both seeds re-confirmed on the final refit below

PRIMARY_ALPHA = 0.05
EFFECT_SIZE_THRESHOLD = 0.05
MIN_N_PRIMARY = 100

XGB_GRID = [
    {"max_depth": md, "min_child_weight": mcw, "reg_alpha": ra, "reg_lambda": rl,
     "subsample": ss, "colsample_bytree": cb}
    for md in (2, 3)
    for mcw in (5, 10)
    for ra in (0.1, 1.0)
    for rl in (1.0, 5.0)
    for ss in (0.7, 0.8)
    for cb in (0.7, 0.8)
]  # 64 combos -- max_depth<=3, min_child_weight>=5, L1/L2 nonzero, subsample/colsample<=0.8, all per the locked family

RF_GRID = [
    {"max_depth": md, "min_samples_leaf": msl, "max_features": mf}
    for md in (4, 6, 8)
    for msl in (5, 10)
    for mf in ("sqrt", "log2")
]  # 12 combos, a comparably real (not default) regularized grid for the alternate-model robustness check


def log(msg: str) -> None:
    print(f"[{datetime.now().isoformat()}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Data loading, QC, chronological split, primary-test-set thinning
# ---------------------------------------------------------------------------

def load_rows():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, ticker, entry_date, exit_date, exit_reason, pnl_dollars, won, features_json "
        "FROM xgboost_training_examples ORDER BY entry_date, ticker, id"
    ).fetchall()
    conn.close()

    data = []
    incomplete = 0
    for r in rows:
        feats = json.loads(r["features_json"])
        rec = {
            "id": r["id"], "ticker": r["ticker"], "entry_date": r["entry_date"],
            "exit_date": r["exit_date"], "exit_reason": r["exit_reason"],
            "pnl_dollars": r["pnl_dollars"], "won": int(r["won"]),
        }
        ok = True
        for f in ALL_FEATURES:
            v = feats.get(f)
            if v is None:
                ok = False
                break
            rec[f] = float(v)
        if not ok:
            incomplete += 1
            continue
        data.append(rec)
    return data, incomplete


def chronological_split(data):
    """60/20/20 by REAL trade count (not the pre-registration's placeholder
    calendar literals -- per its own explicit instruction: 're-verify and
    adjust proportionally once real N is known'). Purged: every trade on a
    given calendar date goes to the same split, so no date straddles a
    boundary."""
    dates_sorted = sorted(set(r["entry_date"] for r in data))
    counts_by_date = {}
    for r in data:
        counts_by_date[r["entry_date"]] = counts_by_date.get(r["entry_date"], 0) + 1

    total = len(data)
    cum = 0
    train_end_date = None
    val_end_date = None
    for d in dates_sorted:
        cum += counts_by_date[d]
        if train_end_date is None and cum / total >= 0.60:
            train_end_date = d
        if val_end_date is None and cum / total >= 0.80:
            val_end_date = d
            break

    train = [r for r in data if r["entry_date"] <= train_end_date]
    val = [r for r in data if train_end_date < r["entry_date"] <= val_end_date]
    test = [r for r in data if r["entry_date"] > val_end_date]
    return train, val, test, train_end_date, val_end_date


def iso_week_key(date_str):
    y, w, _ = datetime.strptime(date_str, "%Y-%m-%d").isocalendar()
    return (y, w)


def build_primary_test_set(test_rows):
    """First qualifying trade per (ticker, calendar week) within the test
    period -- exactly the pre-registration's locked mechanism. test_rows
    must already be sorted by entry_date (load_rows()/filters preserve this)."""
    seen = set()
    primary = []
    for r in test_rows:
        key = (r["ticker"], iso_week_key(r["entry_date"]))
        if key in seen:
            continue
        seen.add(key)
        primary.append(r)
    return primary


def to_xy(rows, feature_list):
    X = np.array([[r[f] for f in feature_list] for r in rows], dtype=float)
    y = np.array([r["won"] for r in rows], dtype=int)
    return X, y


# ---------------------------------------------------------------------------
# Nested CV tuning + fitting
# ---------------------------------------------------------------------------

def tune_and_fit_xgb(X_train, y_train, seed):
    """Inner-loop grid search via TimeSeriesSplit on the train+val portion,
    selecting by mean CV log-loss. Returns the best params and a model
    refit on the FULL X_train/y_train passed in."""
    tscv = TimeSeriesSplit(n_splits=5)
    best_params, best_score = None, np.inf

    for params in XGB_GRID:
        fold_losses = []
        for tr_idx, va_idx in tscv.split(X_train):
            if len(np.unique(y_train[tr_idx])) < 2 or len(np.unique(y_train[va_idx])) < 2:
                continue
            model = xgb.XGBClassifier(
                n_estimators=200, learning_rate=0.05, eval_metric="logloss",
                random_state=TUNING_SEED, **params,
            )
            model.fit(X_train[tr_idx], y_train[tr_idx])
            p = model.predict_proba(X_train[va_idx])[:, 1]
            fold_losses.append(log_loss(y_train[va_idx], p, labels=[0, 1]))
        if not fold_losses:
            continue
        mean_loss = float(np.mean(fold_losses))
        if mean_loss < best_score:
            best_score = mean_loss
            best_params = params

    final_model = xgb.XGBClassifier(
        n_estimators=200, learning_rate=0.05, eval_metric="logloss",
        random_state=seed, **best_params,
    )
    final_model.fit(X_train, y_train)
    return final_model, best_params, best_score


def tune_and_fit_rf(X_train, y_train, seed):
    tscv = TimeSeriesSplit(n_splits=5)
    best_params, best_score = None, np.inf

    for params in RF_GRID:
        fold_losses = []
        for tr_idx, va_idx in tscv.split(X_train):
            if len(np.unique(y_train[tr_idx])) < 2 or len(np.unique(y_train[va_idx])) < 2:
                continue
            model = RandomForestClassifier(
                n_estimators=300, random_state=TUNING_SEED, **params,
            )
            model.fit(X_train[tr_idx], y_train[tr_idx])
            p = model.predict_proba(X_train[va_idx])[:, 1]
            fold_losses.append(log_loss(y_train[va_idx], p, labels=[0, 1]))
        if not fold_losses:
            continue
        mean_loss = float(np.mean(fold_losses))
        if mean_loss < best_score:
            best_score = mean_loss
            best_params = params

    final_model = RandomForestClassifier(n_estimators=300, random_state=seed, **best_params)
    final_model.fit(X_train, y_train)
    return final_model, best_params, best_score


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def per_obs_log_loss(y_true, p_pred):
    eps = 1e-15
    p = np.clip(p_pred, eps, 1 - eps)
    return -(y_true * np.log(p) + (1 - y_true) * np.log(1 - p))


def evaluate_pair(model_a, model_b, X_test, y_test):
    pa = model_a.predict_proba(X_test)[:, 1]
    pb = model_b.predict_proba(X_test)[:, 1]
    loss_a = per_obs_log_loss(y_test, pa)
    loss_b = per_obs_log_loss(y_test, pb)
    auc_a = roc_auc_score(y_test, pa) if len(np.unique(y_test)) > 1 else float("nan")
    auc_b = roc_auc_score(y_test, pb) if len(np.unique(y_test)) > 1 else float("nan")

    result = {
        "n": len(y_test), "auc_a": auc_a, "auc_b": auc_b, "auc_delta": auc_b - auc_a,
        "mean_loss_a": float(np.mean(loss_a)), "mean_loss_b": float(np.mean(loss_b)),
    }
    diffs = loss_a - loss_b  # positive means B has lower loss (better)
    if len(y_test) >= 10 and np.any(diffs != 0):
        try:
            stat, p = wilcoxon(diffs, alternative="greater")
            result["wilcoxon_stat"] = float(stat)
            result["wilcoxon_p_one_sided"] = float(p)
        except ValueError as exc:
            result["wilcoxon_stat"] = None
            result["wilcoxon_p_one_sided"] = None
            result["wilcoxon_error"] = str(exc)
    else:
        result["wilcoxon_stat"] = None
        result["wilcoxon_p_one_sided"] = None
        result["wilcoxon_note"] = "N too small or all diffs zero"
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    report = {}

    log("Loading data...")
    data, incomplete = load_rows()
    report["total_rows_in_db"] = len(data) + incomplete
    report["incomplete_rows_dropped"] = incomplete
    report["complete_rows_used"] = len(data)
    log(f"Loaded {len(data)} complete rows ({incomplete} dropped for missing feature values, e.g. realized_vol_percentile=None on early-history bars)")

    train, val, test, train_end, val_end = chronological_split(data)
    train_val = train + val
    report["split"] = {
        "train_n": len(train), "val_n": len(val), "test_n": len(test),
        "train_pct": round(len(train) / len(data) * 100, 1),
        "val_pct": round(len(val) / len(data) * 100, 1),
        "test_pct": round(len(test) / len(data) * 100, 1),
        "train_start": data[0]["entry_date"], "train_end": train_end,
        "val_end": val_end, "test_end": data[-1]["entry_date"],
    }
    log(f"Split: train={len(train)} ({train[0]['entry_date']}..{train_end}), val={len(val)} (..{val_end}), test={len(test)} (..{data[-1]['entry_date']})")

    primary_test = build_primary_test_set(test)
    report["primary_test_n"] = len(primary_test)
    log(f"Primary (thinned, non-overlapping) test set: {len(primary_test)} observations (first trade per ticker per ISO week within the test period)")

    X_trainval_a, y_trainval = to_xy(train_val, BASE_FEATURES)
    X_trainval_b, _ = to_xy(train_val, ALL_FEATURES)
    X_primary_a, y_primary = to_xy(primary_test, BASE_FEATURES)
    X_primary_b, _ = to_xy(primary_test, ALL_FEATURES)
    X_full_test_a, y_full_test = to_xy(test, BASE_FEATURES)
    X_full_test_b, _ = to_xy(test, ALL_FEATURES)

    # ---- Primary XGBoost models (tuning seed 42, refit under both seeds) ----
    log("Tuning + fitting Model A (XGBoost, 13 base features)...")
    model_a, params_a, cv_loss_a = tune_and_fit_xgb(X_trainval_a, y_trainval, seed=42)
    log(f"Model A best params: {params_a} (mean CV log-loss {cv_loss_a:.4f})")

    log("Tuning + fitting Model B (XGBoost, 13 base + 3 interaction features)...")
    model_b, params_b, cv_loss_b = tune_and_fit_xgb(X_trainval_b, y_trainval, seed=42)
    log(f"Model B best params: {params_b} (mean CV log-loss {cv_loss_b:.4f})")

    report["model_a_tuned_params"] = params_a
    report["model_b_tuned_params"] = params_b
    report["model_a_cv_log_loss"] = cv_loss_a
    report["model_b_cv_log_loss"] = cv_loss_b

    # seed-43 refit for reproducibility confirmation
    model_a_seed43 = xgb.XGBClassifier(n_estimators=200, learning_rate=0.05, eval_metric="logloss", random_state=43, **params_a)
    model_a_seed43.fit(X_trainval_a, y_trainval)
    model_b_seed43 = xgb.XGBClassifier(n_estimators=200, learning_rate=0.05, eval_metric="logloss", random_state=43, **params_b)
    model_b_seed43.fit(X_trainval_b, y_trainval)

    log("Evaluating on PRIMARY test set (seed 42)...")
    # Model A predicts on its own 13-feature matrix, Model B on its own 16-feature
    # matrix -- each model gets exactly the feature set it was trained on.
    pa42 = model_a.predict_proba(X_primary_a)[:, 1]
    pb42 = model_b.predict_proba(X_primary_b)[:, 1]
    loss_a42 = per_obs_log_loss(y_primary, pa42)
    loss_b42 = per_obs_log_loss(y_primary, pb42)
    auc_a42 = roc_auc_score(y_primary, pa42) if len(np.unique(y_primary)) > 1 else float("nan")
    auc_b42 = roc_auc_score(y_primary, pb42) if len(np.unique(y_primary)) > 1 else float("nan")
    diffs42 = loss_a42 - loss_b42
    wil42 = wilcoxon(diffs42, alternative="greater") if len(y_primary) >= 10 and np.any(diffs42 != 0) else (None, None)

    pa43 = model_a_seed43.predict_proba(X_primary_a)[:, 1]
    pb43 = model_b_seed43.predict_proba(X_primary_b)[:, 1]
    loss_a43 = per_obs_log_loss(y_primary, pa43)
    loss_b43 = per_obs_log_loss(y_primary, pb43)
    auc_a43 = roc_auc_score(y_primary, pa43) if len(np.unique(y_primary)) > 1 else float("nan")
    auc_b43 = roc_auc_score(y_primary, pb43) if len(np.unique(y_primary)) > 1 else float("nan")
    diffs43 = loss_a43 - loss_b43
    wil43 = wilcoxon(diffs43, alternative="greater") if len(y_primary) >= 10 and np.any(diffs43 != 0) else (None, None)

    report["primary_result"] = {
        "n": len(primary_test),
        "seed42": {
            "auc_a": float(auc_a42), "auc_b": float(auc_b42), "auc_delta": float(auc_b42 - auc_a42),
            "mean_loss_a": float(np.mean(loss_a42)), "mean_loss_b": float(np.mean(loss_b42)),
            "wilcoxon_p_one_sided": (float(wil42[1]) if wil42[1] is not None else None),
        },
        "seed43": {
            "auc_a": float(auc_a43), "auc_b": float(auc_b43), "auc_delta": float(auc_b43 - auc_a43),
            "mean_loss_a": float(np.mean(loss_a43)), "mean_loss_b": float(np.mean(loss_b43)),
            "wilcoxon_p_one_sided": (float(wil43[1]) if wil43[1] is not None else None),
        },
    }
    log(f"PRIMARY (seed42): AUC_A={auc_a42:.4f} AUC_B={auc_b42:.4f} delta={auc_b42-auc_a42:+.4f} loss_A={np.mean(loss_a42):.4f} loss_B={np.mean(loss_b42):.4f} p={wil42[1]}")
    log(f"PRIMARY (seed43): AUC_A={auc_a43:.4f} AUC_B={auc_b43:.4f} delta={auc_b43-auc_a43:+.4f} loss_A={np.mean(loss_a43):.4f} loss_B={np.mean(loss_b43):.4f} p={wil43[1]}")

    # descriptive: full (untinned) test set
    pa_full = model_a.predict_proba(X_full_test_a)[:, 1]
    pb_full = model_b.predict_proba(X_full_test_b)[:, 1]
    auc_a_full = roc_auc_score(y_full_test, pa_full)
    auc_b_full = roc_auc_score(y_full_test, pb_full)
    report["full_test_set_descriptive"] = {
        "n": len(test), "auc_a": float(auc_a_full), "auc_b": float(auc_b_full),
        "auc_delta": float(auc_b_full - auc_a_full),
    }
    log(f"Full (untinned) test set, DESCRIPTIVE ONLY: n={len(test)} AUC_A={auc_a_full:.4f} AUC_B={auc_b_full:.4f} delta={auc_b_full-auc_a_full:+.4f}")

    # ---- Robustness check 1: alternate_model:random_forest ----
    log("Robustness 1/5: alternate_model:random_forest...")
    rf_a, rf_a_params, _ = tune_and_fit_rf(X_trainval_a, y_trainval, seed=42)
    rf_b, rf_b_params, _ = tune_and_fit_rf(X_trainval_b, y_trainval, seed=42)
    rfa_p = rf_a.predict_proba(X_primary_a)[:, 1]
    rfb_p = rf_b.predict_proba(X_primary_b)[:, 1]
    rf_loss_a = per_obs_log_loss(y_primary, rfa_p)
    rf_loss_b = per_obs_log_loss(y_primary, rfb_p)
    rf_auc_a = roc_auc_score(y_primary, rfa_p) if len(np.unique(y_primary)) > 1 else float("nan")
    rf_auc_b = roc_auc_score(y_primary, rfb_p) if len(np.unique(y_primary)) > 1 else float("nan")
    rf_diffs = rf_loss_a - rf_loss_b
    rf_wil = wilcoxon(rf_diffs, alternative="greater") if len(y_primary) >= 10 and np.any(rf_diffs != 0) else (None, None)
    report["robustness_random_forest"] = {
        "params_a": rf_a_params, "params_b": rf_b_params,
        "auc_a": float(rf_auc_a), "auc_b": float(rf_auc_b), "auc_delta": float(rf_auc_b - rf_auc_a),
        "wilcoxon_p_one_sided": (float(rf_wil[1]) if rf_wil[1] is not None else None),
        "direction_matches_xgboost": bool((rf_auc_b - rf_auc_a) > 0) == bool((auc_b42 - auc_a42) > 0),
    }
    log(f"  RF: AUC_A={rf_auc_a:.4f} AUC_B={rf_auc_b:.4f} delta={rf_auc_b-rf_auc_a:+.4f} p={rf_wil[1]}")

    # ---- Robustness check 2: leave_one_interaction_out ----
    log("Robustness 2/5: leave_one_interaction_out...")
    loio_results = {}
    for dropped in INTERACTIONS:
        feats_sub = BASE_FEATURES + [f for f in INTERACTIONS if f != dropped]
        Xtv_sub, _ = to_xy(train_val, feats_sub)
        Xp_sub, _ = to_xy(primary_test, feats_sub)
        m_sub = xgb.XGBClassifier(n_estimators=200, learning_rate=0.05, eval_metric="logloss", random_state=42, **params_b)
        m_sub.fit(Xtv_sub, y_trainval)
        p_sub = m_sub.predict_proba(Xp_sub)[:, 1]
        auc_sub = roc_auc_score(y_primary, p_sub) if len(np.unique(y_primary)) > 1 else float("nan")
        loss_sub = per_obs_log_loss(y_primary, p_sub)
        diffs_sub = loss_a42 - loss_sub
        wil_sub = wilcoxon(diffs_sub, alternative="greater") if len(y_primary) >= 10 and np.any(diffs_sub != 0) else (None, None)
        loio_results[dropped] = {
            "auc_without_this_interaction": float(auc_sub),
            "auc_delta_vs_model_a": float(auc_sub - auc_a42),
            "wilcoxon_p_vs_model_a": (float(wil_sub[1]) if wil_sub[1] is not None else None),
        }
        log(f"  dropping {dropped}: AUC={auc_sub:.4f} (vs Model A {auc_a42:.4f}, full Model B {auc_b42:.4f})")
    report["robustness_leave_one_interaction_out"] = loio_results

    # ---- Robustness check 3: leave_one_ticker_out ----
    log("Robustness 3/5: leave_one_ticker_out...")
    loto_results = {}
    tickers = sorted(set(r["ticker"] for r in data))
    for excl_ticker in tickers:
        tv_sub = [r for r in train_val if r["ticker"] != excl_ticker]
        primary_sub = [r for r in primary_test if r["ticker"] != excl_ticker]
        if len(primary_sub) < 5:
            loto_results[excl_ticker] = {"note": "primary test subset too small after exclusion", "n": len(primary_sub)}
            continue
        Xtv_a_sub, ytv_sub = to_xy(tv_sub, BASE_FEATURES)
        Xtv_b_sub, _ = to_xy(tv_sub, ALL_FEATURES)
        Xp_a_sub, yp_sub = to_xy(primary_sub, BASE_FEATURES)
        Xp_b_sub, _ = to_xy(primary_sub, ALL_FEATURES)
        ma_sub = xgb.XGBClassifier(n_estimators=200, learning_rate=0.05, eval_metric="logloss", random_state=42, **params_a)
        ma_sub.fit(Xtv_a_sub, ytv_sub)
        mb_sub = xgb.XGBClassifier(n_estimators=200, learning_rate=0.05, eval_metric="logloss", random_state=42, **params_b)
        mb_sub.fit(Xtv_b_sub, ytv_sub)
        pa_sub = ma_sub.predict_proba(Xp_a_sub)[:, 1]
        pb_sub = mb_sub.predict_proba(Xp_b_sub)[:, 1]
        auc_a_sub = roc_auc_score(yp_sub, pa_sub) if len(np.unique(yp_sub)) > 1 else float("nan")
        auc_b_sub = roc_auc_score(yp_sub, pb_sub) if len(np.unique(yp_sub)) > 1 else float("nan")
        loss_a_sub = per_obs_log_loss(yp_sub, pa_sub)
        loss_b_sub = per_obs_log_loss(yp_sub, pb_sub)
        diffs_sub = loss_a_sub - loss_b_sub
        wil_sub = wilcoxon(diffs_sub, alternative="greater") if len(yp_sub) >= 10 and np.any(diffs_sub != 0) else (None, None)
        loto_results[excl_ticker] = {
            "n": len(primary_sub), "auc_a": float(auc_a_sub), "auc_b": float(auc_b_sub),
            "auc_delta": float(auc_b_sub - auc_a_sub),
            "wilcoxon_p_one_sided": (float(wil_sub[1]) if wil_sub[1] is not None else None),
        }
        log(f"  excluding {excl_ticker}: n={len(primary_sub)} AUC_A={auc_a_sub:.4f} AUC_B={auc_b_sub:.4f} delta={auc_b_sub-auc_a_sub:+.4f} p={wil_sub[1]}")
    report["robustness_leave_one_ticker_out"] = loto_results

    # ---- Robustness check 4: alternate_horizon:exit_reason_stratified ----
    log("Robustness 4/5: alternate_horizon:exit_reason_stratified (stratifying the already-fit primary-set predictions)...")
    stratified = {}
    exit_reasons = sorted(set(r["exit_reason"] for r in primary_test))
    for reason in exit_reasons:
        idx = [i for i, r in enumerate(primary_test) if r["exit_reason"] == reason]
        if len(idx) < 5:
            stratified[reason] = {"note": "too few primary-test observations", "n": len(idx)}
            continue
        y_sub = y_primary[idx]
        loss_a_sub = loss_a42[idx]
        loss_b_sub = loss_b42[idx]
        auc_a_sub = roc_auc_score(y_sub, pa42[idx]) if len(np.unique(y_sub)) > 1 else float("nan")
        auc_b_sub = roc_auc_score(y_sub, pb42[idx]) if len(np.unique(y_sub)) > 1 else float("nan")
        diffs_sub = loss_a_sub - loss_b_sub
        wil_sub = wilcoxon(diffs_sub, alternative="greater") if len(y_sub) >= 10 and np.any(diffs_sub != 0) else (None, None)
        stratified[reason] = {
            "n": len(idx), "auc_a": float(auc_a_sub), "auc_b": float(auc_b_sub),
            "auc_delta": float(auc_b_sub - auc_a_sub),
            "wilcoxon_p_one_sided": (float(wil_sub[1]) if wil_sub[1] is not None else None),
        }
        log(f"  {reason}: n={len(idx)} AUC_A={auc_a_sub:.4f} AUC_B={auc_b_sub:.4f} delta={auc_b_sub-auc_a_sub:+.4f} p={wil_sub[1]}")
    report["robustness_exit_reason_stratified"] = stratified

    # ---- Robustness check 5: shuffled_target_placebo ----
    log("Robustness 5/5: shuffled_target_placebo...")
    rng = np.random.RandomState(42)
    y_trainval_shuffled = y_trainval.copy()
    rng.shuffle(y_trainval_shuffled)
    ma_shuf = xgb.XGBClassifier(n_estimators=200, learning_rate=0.05, eval_metric="logloss", random_state=42, **params_a)
    ma_shuf.fit(X_trainval_a, y_trainval_shuffled)
    mb_shuf = xgb.XGBClassifier(n_estimators=200, learning_rate=0.05, eval_metric="logloss", random_state=42, **params_b)
    mb_shuf.fit(X_trainval_b, y_trainval_shuffled)
    pa_shuf = ma_shuf.predict_proba(X_primary_a)[:, 1]
    pb_shuf = mb_shuf.predict_proba(X_primary_b)[:, 1]
    auc_a_shuf = roc_auc_score(y_primary, pa_shuf) if len(np.unique(y_primary)) > 1 else float("nan")
    auc_b_shuf = roc_auc_score(y_primary, pb_shuf) if len(np.unique(y_primary)) > 1 else float("nan")
    loss_a_shuf = per_obs_log_loss(y_primary, pa_shuf)
    loss_b_shuf = per_obs_log_loss(y_primary, pb_shuf)
    diffs_shuf = loss_a_shuf - loss_b_shuf
    wil_shuf = wilcoxon(diffs_shuf, alternative="greater") if len(y_primary) >= 10 and np.any(diffs_shuf != 0) else (None, None)
    report["robustness_shuffled_target_placebo"] = {
        "auc_a_shuffled": float(auc_a_shuf), "auc_b_shuffled": float(auc_b_shuf),
        "auc_delta_shuffled": float(auc_b_shuf - auc_a_shuf),
        "wilcoxon_p_one_sided_shuffled": (float(wil_shuf[1]) if wil_shuf[1] is not None else None),
        "significant_at_0.05": bool(wil_shuf[1] is not None and wil_shuf[1] < 0.05),
    }
    log(f"  SHUFFLED: AUC_A={auc_a_shuf:.4f} AUC_B={auc_b_shuf:.4f} delta={auc_b_shuf-auc_a_shuf:+.4f} p={wil_shuf[1]} (expect: NO significant effect)")

    # ---- Concentration check ----
    log("Concentration check: per-ticker and chronological-half contribution to the primary effect...")
    per_ticker_delta = {}
    for t in tickers:
        idx = [i for i, r in enumerate(primary_test) if r["ticker"] == t]
        if len(idx) < 3:
            per_ticker_delta[t] = {"n": len(idx), "note": "too few observations"}
            continue
        mean_diff = float(np.mean(loss_a42[idx] - loss_b42[idx]))
        per_ticker_delta[t] = {"n": len(idx), "mean_log_loss_diff_a_minus_b": mean_diff}
    half = len(primary_test) // 2
    first_half_diff = float(np.mean(loss_a42[:half] - loss_b42[:half])) if half > 0 else None
    second_half_diff = float(np.mean(loss_a42[half:] - loss_b42[half:])) if half > 0 else None
    report["concentration_check"] = {
        "per_ticker_mean_loss_diff": per_ticker_delta,
        "first_half_mean_loss_diff": first_half_diff,
        "second_half_mean_loss_diff": second_half_diff,
    }
    log(f"  first-half mean(A-B) diff={first_half_diff}, second-half={second_half_diff}")
    for t, v in per_ticker_delta.items():
        log(f"  {t}: {v}")

    # ---- Apply the pre-registration's LITERAL decision rules ----
    log("\nApplying decision rules...")
    primary_n = len(primary_test)
    primary_sig_42 = report["primary_result"]["seed42"]["wilcoxon_p_one_sided"]
    primary_sig_43 = report["primary_result"]["seed43"]["wilcoxon_p_one_sided"]
    auc_delta_42 = report["primary_result"]["seed42"]["auc_delta"]
    auc_delta_43 = report["primary_result"]["seed43"]["auc_delta"]

    primary_significant = (primary_sig_42 is not None and primary_sig_42 < PRIMARY_ALPHA) and \
                           (primary_sig_43 is not None and primary_sig_43 < PRIMARY_ALPHA)
    effect_size_met = (auc_delta_42 >= EFFECT_SIZE_THRESHOLD) and (auc_delta_43 >= EFFECT_SIZE_THRESHOLD)

    rf_direction_ok = report["robustness_random_forest"]["direction_matches_xgboost"] and report["robustness_random_forest"]["auc_delta"] > 0
    loio_direction_ok = all(v["auc_delta_vs_model_a"] > 0 for v in loio_results.values())
    loto_direction_ok = all(
        (v.get("auc_delta", -1) > 0) for v in loto_results.values() if "auc_delta" in v
    )
    stratified_direction_ok = all(
        (v.get("auc_delta", -1) > 0) for v in stratified.values() if "auc_delta" in v
    )
    placebo_clean = not report["robustness_shuffled_target_placebo"]["significant_at_0.05"]

    all_four_robustness_ok = rf_direction_ok and loio_direction_ok and loto_direction_ok and stratified_direction_ok
    all_five_robustness_ok = all_four_robustness_ok and placebo_clean

    report["decision_inputs"] = {
        "primary_n": primary_n, "n_meets_floor": primary_n >= MIN_N_PRIMARY,
        "primary_significant_both_seeds": primary_significant,
        "effect_size_met_both_seeds": effect_size_met,
        "rf_direction_ok": rf_direction_ok, "loio_direction_ok": loio_direction_ok,
        "loto_direction_ok": loto_direction_ok, "stratified_direction_ok": stratified_direction_ok,
        "placebo_clean": placebo_clean,
        "all_four_robustness_ok": all_four_robustness_ok,
        "all_five_robustness_ok": all_five_robustness_ok,
    }

    placebo_leaked = report["robustness_shuffled_target_placebo"]["significant_at_0.05"]

    if primary_n < MIN_N_PRIMARY:
        verdict = "INCONCLUSIVE"
        reason = f"Primary test-set N={primary_n} < required {MIN_N_PRIMARY}"
    elif primary_significant and effect_size_met and all_five_robustness_ok and not placebo_leaked:
        verdict = "VALIDATED"
        reason = "Primary N sufficient, primary test significant both seeds, effect size met both seeds, all 5 robustness checks pass in the expected direction, placebo clean"
    else:
        # N is sufficient but at least one VALIDATED criterion failed -- determine
        # whether this is a clean REJECTED or a pipeline-integrity flag, per the
        # pre-registration's own text distinguishing the two.
        reasons = []
        if placebo_leaked:
            reasons.append(
                "PIPELINE/LEAKAGE FLAG: shuffled_target_placebo showed a significant effect on "
                "randomly-permuted training labels -- per the pre-registration's own text, this "
                "indicates a pipeline/leakage problem rather than the interactions themselves "
                "being non-predictive, and should be root-caused before trusting any other result here."
            )
        if not primary_significant:
            reasons.append("primary test not significant at alpha=0.05 (both seeds)")
        if not effect_size_met:
            reasons.append("effect size (AUC delta) below 0.05 threshold (both seeds)")
        if not rf_direction_ok:
            reasons.append("Random Forest robustness check direction/positive-effect failed -- XGBoost and Random Forest DISAGREE")
        if not loio_direction_ok:
            reasons.append("leave_one_interaction_out: at least one interaction removal reverses direction")
        if not loto_direction_ok:
            reasons.append("leave_one_ticker_out: at least one exclusion reverses direction")
        if not stratified_direction_ok:
            reasons.append("exit_reason_stratified: at least one subgroup reverses direction")

        if placebo_leaked:
            verdict = "REJECTED (pipeline/leakage flag)"
        else:
            verdict = "REJECTED"
        reason = "; ".join(reasons)

    report["verdict"] = verdict
    report["verdict_reason"] = reason

    log("\n" + "=" * 100)
    log(f"VERDICT: {verdict}")
    log(f"REASON: {reason}")
    log("=" * 100)

    with open("xgboost_stage1_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log("\nFull results written to xgboost_stage1_results.json")


if __name__ == "__main__":
    main()

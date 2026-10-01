from dotenv import load_dotenv
load_dotenv()

"""
Extracts the exact Wilcoxon test statistics (W) that xgboost_stage1_execution.py
computed but didn't save to the results JSON (only p-values were kept). Reuses
the EXACT already-discovered hyperparameters from xgboost_stage1_results.json --
no re-tuning, just deterministic refits (fixed random_state) to recover the
missing statistic values and print a fully itemized breakdown.
"""

import json
import warnings
from datetime import datetime

import numpy as np
from scipy.stats import wilcoxon
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
import xgboost as xgb

warnings.filterwarnings("ignore")

from xgboost_stage1_execution import (
    load_rows, chronological_split, build_primary_test_set, to_xy,
    per_obs_log_loss, BASE_FEATURES, ALL_FEATURES, INTERACTIONS,
)

with open("xgboost_stage1_results.json") as f:
    prior = json.load(f)

params_a = prior["model_a_tuned_params"]
params_b = prior["model_b_tuned_params"]
rf_params_a = prior["robustness_random_forest"]["params_a"]
rf_params_b = prior["robustness_random_forest"]["params_b"]

data, incomplete = load_rows()
assert incomplete == 0, f"expected 0 incomplete rows, got {incomplete}"
assert len(data) == 2599, f"expected 2599 rows, got {len(data)} -- DATA HAS DRIFTED, STOP"

train, val, test, train_end, val_end = chronological_split(data)
train_val = train + val
primary_test = build_primary_test_set(test)
print(f"n_train_val={len(train_val)} n_primary_test={len(primary_test)}")

X_trainval_a, y_trainval = to_xy(train_val, BASE_FEATURES)
X_trainval_b, _ = to_xy(train_val, ALL_FEATURES)
X_primary_a, y_primary = to_xy(primary_test, BASE_FEATURES)
X_primary_b, _ = to_xy(primary_test, ALL_FEATURES)

def fit_xgb(X, y, params, seed):
    m = xgb.XGBClassifier(n_estimators=200, learning_rate=0.05, eval_metric="logloss", random_state=seed, **params)
    m.fit(X, y)
    return m

def fit_rf(X, y, params, seed):
    m = RandomForestClassifier(n_estimators=300, random_state=seed, **params)
    m.fit(X, y)
    return m

print("\n=== PRIMARY RESULT, both seeds, full Wilcoxon stat+p ===")
for seed in (42, 43):
    ma = fit_xgb(X_trainval_a, y_trainval, params_a, seed)
    mb = fit_xgb(X_trainval_b, y_trainval, params_b, seed)
    pa = ma.predict_proba(X_primary_a)[:, 1]
    pb = mb.predict_proba(X_primary_b)[:, 1]
    loss_a = per_obs_log_loss(y_primary, pa)
    loss_b = per_obs_log_loss(y_primary, pb)
    diffs = loss_a - loss_b
    n_nonzero = int(np.sum(diffs != 0))
    n_positive = int(np.sum(diffs > 0))  # B better than A
    n_negative = int(np.sum(diffs < 0))  # A better than B
    stat, p = wilcoxon(diffs, alternative="greater")
    auc_a = roc_auc_score(y_primary, pa)
    auc_b = roc_auc_score(y_primary, pb)
    print(f"seed={seed}: N={len(y_primary)} nonzero_diffs={n_nonzero} (B_better_on={n_positive}, A_better_on={n_negative}) "
          f"W_stat={stat:.4f} p_one_sided={p:.6f} AUC_A={auc_a:.6f} AUC_B={auc_b:.6f} AUC_delta={auc_b-auc_a:+.6f} "
          f"mean_loss_A={np.mean(loss_a):.6f} mean_loss_B={np.mean(loss_b):.6f}")

print("\n=== RANDOM FOREST robustness, exact ===")
rfa = fit_rf(X_trainval_a, y_trainval, rf_params_a, 42)
rfb = fit_rf(X_trainval_b, y_trainval, rf_params_b, 42)
rfa_p = rfa.predict_proba(X_primary_a)[:, 1]
rfb_p = rfb.predict_proba(X_primary_b)[:, 1]
rf_loss_a = per_obs_log_loss(y_primary, rfa_p)
rf_loss_b = per_obs_log_loss(y_primary, rfb_p)
rf_diffs = rf_loss_a - rf_loss_b
rf_n_nonzero = int(np.sum(rf_diffs != 0))
rf_n_pos = int(np.sum(rf_diffs > 0))
rf_n_neg = int(np.sum(rf_diffs < 0))
rf_stat, rf_p = wilcoxon(rf_diffs, alternative="greater")
rf_auc_a = roc_auc_score(y_primary, rfa_p)
rf_auc_b = roc_auc_score(y_primary, rfb_p)
print(f"RF params_a={rf_params_a} params_b={rf_params_b}")
print(f"N={len(y_primary)} nonzero_diffs={rf_n_nonzero} (B_better_on={rf_n_pos}, A_better_on={rf_n_neg}) "
      f"W_stat={rf_stat:.4f} p_one_sided={rf_p:.6f} AUC_A={rf_auc_a:.6f} AUC_B={rf_auc_b:.6f} AUC_delta={rf_auc_b-rf_auc_a:+.6f}")

print("\n=== LEAVE_ONE_INTERACTION_OUT, exact, with reference to full Model B and Model A ===")
ma42 = fit_xgb(X_trainval_a, y_trainval, params_a, 42)
mb42 = fit_xgb(X_trainval_b, y_trainval, params_b, 42)
pa42_full = ma42.predict_proba(X_primary_a)[:, 1]
pb42_full = mb42.predict_proba(X_primary_b)[:, 1]
loss_a42_full = per_obs_log_loss(y_primary, pa42_full)
auc_a_ref = roc_auc_score(y_primary, pa42_full)
auc_b_ref = roc_auc_score(y_primary, pb42_full)
print(f"reference: Model A AUC={auc_a_ref:.6f}, full Model B AUC={auc_b_ref:.6f}")
for dropped in INTERACTIONS:
    feats_sub = BASE_FEATURES + [f for f in INTERACTIONS if f != dropped]
    Xtv_sub, _ = to_xy(train_val, feats_sub)
    Xp_sub, _ = to_xy(primary_test, feats_sub)
    m_sub = fit_xgb(Xtv_sub, y_trainval, params_b, 42)
    p_sub = m_sub.predict_proba(Xp_sub)[:, 1]
    loss_sub = per_obs_log_loss(y_primary, p_sub)
    auc_sub = roc_auc_score(y_primary, p_sub)
    diffs_sub = loss_a42_full - loss_sub
    n_nonzero = int(np.sum(diffs_sub != 0))
    stat_sub, p_sub_val = wilcoxon(diffs_sub, alternative="greater") if n_nonzero > 0 else (None, None)
    print(f"drop {dropped}: AUC_without={auc_sub:.6f} (full_B={auc_b_ref:.6f}, A={auc_a_ref:.6f}) "
          f"delta_vs_A={auc_sub-auc_a_ref:+.6f} delta_vs_full_B={auc_sub-auc_b_ref:+.6f} "
          f"W_stat_vs_A={stat_sub} p_vs_A={p_sub_val}")

print("\n=== LEAVE_ONE_TICKER_OUT, exact, all 6 ===")
tickers = sorted(set(r["ticker"] for r in data))
for excl in tickers:
    tv_sub = [r for r in train_val if r["ticker"] != excl]
    primary_sub = [r for r in primary_test if r["ticker"] != excl]
    Xtv_a_sub, ytv_sub = to_xy(tv_sub, BASE_FEATURES)
    Xtv_b_sub, _ = to_xy(tv_sub, ALL_FEATURES)
    Xp_a_sub, yp_sub = to_xy(primary_sub, BASE_FEATURES)
    Xp_b_sub, _ = to_xy(primary_sub, ALL_FEATURES)
    ma_sub = fit_xgb(Xtv_a_sub, ytv_sub, params_a, 42)
    mb_sub = fit_xgb(Xtv_b_sub, ytv_sub, params_b, 42)
    pa_sub = ma_sub.predict_proba(Xp_a_sub)[:, 1]
    pb_sub = mb_sub.predict_proba(Xp_b_sub)[:, 1]
    loss_a_sub = per_obs_log_loss(yp_sub, pa_sub)
    loss_b_sub = per_obs_log_loss(yp_sub, pb_sub)
    diffs_sub = loss_a_sub - loss_b_sub
    n_nonzero = int(np.sum(diffs_sub != 0))
    stat_sub, p_sub_val = wilcoxon(diffs_sub, alternative="greater") if n_nonzero > 0 else (None, None)
    auc_a_sub = roc_auc_score(yp_sub, pa_sub)
    auc_b_sub = roc_auc_score(yp_sub, pb_sub)
    print(f"exclude {excl}: n={len(primary_sub)} AUC_A={auc_a_sub:.6f} AUC_B={auc_b_sub:.6f} "
          f"delta={auc_b_sub-auc_a_sub:+.6f} W_stat={stat_sub} p={p_sub_val}")

print("\n=== SHUFFLED_TARGET_PLACEBO, exact, compared side-by-side with real-label primary result ===")
rng = np.random.RandomState(42)
y_shuf = y_trainval.copy()
rng.shuffle(y_shuf)
ma_shuf = fit_xgb(X_trainval_a, y_shuf, params_a, 42)
mb_shuf = fit_xgb(X_trainval_b, y_shuf, params_b, 42)
pa_shuf = ma_shuf.predict_proba(X_primary_a)[:, 1]
pb_shuf = mb_shuf.predict_proba(X_primary_b)[:, 1]
loss_a_shuf = per_obs_log_loss(y_primary, pa_shuf)
loss_b_shuf = per_obs_log_loss(y_primary, pb_shuf)
diffs_shuf = loss_a_shuf - loss_b_shuf
n_nonzero = int(np.sum(diffs_shuf != 0))
stat_shuf, p_shuf = wilcoxon(diffs_shuf, alternative="greater") if n_nonzero > 0 else (None, None)
auc_a_shuf = roc_auc_score(y_primary, pa_shuf)
auc_b_shuf = roc_auc_score(y_primary, pb_shuf)
print(f"SHUFFLED: N={len(y_primary)} W_stat={stat_shuf} p_one_sided={p_shuf} AUC_A={auc_a_shuf:.6f} AUC_B={auc_b_shuf:.6f} AUC_delta={auc_b_shuf-auc_a_shuf:+.6f}")
print(f"REAL (seed42, for comparison): AUC_delta={auc_b_ref-auc_a_ref:+.6f}, p={None}  (see primary block above for exact p)")

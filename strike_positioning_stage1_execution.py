from dotenv import load_dotenv
load_dotenv()

"""
Stage 1 execution for strike_positioning_oi_skew_v1_20260922 (CLAUDE.md
Section 39, preregister_strike_positioning_experiment.py, config_hash
ae3b3a7df686159c0e3dcad1556f6433c64bee2828a1d2c4bee5cd3b71cded33 --
re-verified unchanged before this script was written).

Loads the already-generated, already integrity-checked 605-row Stage 1
dataset (strike_positioning_oi_skew_dataset.db) plus the two alternate-
parameter oi_skew variants (oi_skew_variants table, fetch_oi_skew_
variants.py) needed for the alternate_moneyness_band/alternate_dte_window
robustness checks. Does NOT refetch or regenerate any data itself.

TEST CONSTRUCTION -- disclosed explicitly, since the pre-registration
named the test FAMILY ("monte_carlo_day_clustered_one_sided", |correlation|
effect-size threshold) but not the literal statistic/permutation formula,
same discipline as every other "Stage 1 EXECUTED" section in this project
(e.g. GEX call-wall-distance, CLAUDE.md Section 32):

  - Test statistic: pooled Pearson correlation between oi_skew and the
    forward-return horizon under test, across all (ticker, day) rows.
  - Null distribution: DAY-CLUSTERED permutation -- a random permutation
    of the set of unique calendar DAYS is drawn (not individual rows),
    and each row's oi_skew is re-paired with the target return that same
    TICKER had on the PERMUTED day (if that ticker has no data on the
    permuted day -- a rare edge case given only 1 of 606 candidate rows
    was ever excluded -- that row is dropped from that one replicate
    only). This preserves each day's real cross-ticker correlation
    structure (the reason Phase 6/GEX/IV-term-structure all cluster by
    day, CLAUDE.md Section 22) while breaking the temporal link between
    the signal and the outcome under the null.
  - One-sided empirical p-value in the HYPOTHESIZED direction (positive
    correlation -- elevated put skew predicts HIGHER forward returns,
    contrarian, per the pre-registration's own stated mechanism) --
    p = fraction of the 1000-replicate null distribution with a
    correlation >= the real, observed correlation.
  - 1000 replicates x 2 seeds (42, 43), matching this project's standard
    convention throughout (Phase 6, GEX, IV term structure).

DECISION-RULE TEXT, quoted directly, not paraphrased, since it matters for
how "survives a robustness check" is scored: "VALIDATED requires ALL of:
... 4. Survives ALL 5 declared robustness checks in the SAME DIRECTION."
Unlike IV term structure's ambiguous 50-day-horizon case (CLAUDE.md
Section 33), THIS pre-registration's literal text ties "surviving" a
robustness check explicitly to direction-consistency, not independent
significance -- honored here as written, not reinterpreted either way.
Both direction AND significance are still reported per check, so the
distinction is visible, not hidden.

Does NOT call preregister_experiment()/run_experiment() -- this is a
direct analysis script, same category as every other "Stage 1 EXECUTED"
section in this project (only ml_experiment1 has ever gone through the
real framework).
"""

import json
import sqlite3
from datetime import datetime

import numpy as np

DB_PATH = "strike_positioning_oi_skew_dataset.db"

PRIMARY_HORIZON = 20
HORIZON_TARGET_COL = {10: "target_return_10d", 20: "target_return_20d", 50: "target_return_50d"}
BONFERRONI_FAMILY = 3
ALPHA_UNCORRECTED = 0.05
ALPHA_CORRECTED = ALPHA_UNCORRECTED / BONFERRONI_FAMILY
EFFECT_SIZE_THRESHOLD = 0.15
MC_REPLICATES = 1000
SEEDS = [42, 43]
MIN_N = 100
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]


def log(msg):
    print(msg, flush=True)


def load_primary_rows():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT ticker, obs_date, oi_skew, target_return_10d, target_return_20d, target_return_50d "
        "FROM oi_skew_training_examples ORDER BY obs_date, ticker"
    ).fetchall()
    conn.close()
    return rows


def load_variant_rows():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT ticker, obs_date, oi_skew_primary_recomputed, oi_skew_band15, oi_skew_dte730 "
        "FROM oi_skew_variants ORDER BY obs_date, ticker"
    ).fetchall()
    conn.close()
    return rows


def pearson_r(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def day_clustered_test(quads, seed, n_replicates=MC_REPLICATES, direction="positive"):
    """quads: list of (ticker, obs_date, oi_skew, target). See module
    docstring for the full construction."""
    oi_vals = [q[2] for q in quads]
    target_vals = [q[3] for q in quads]
    r_obs = pearson_r(oi_vals, target_vals)
    n = len(quads)

    by_ticker_target = {}
    for ticker, dt, oi, target in quads:
        by_ticker_target.setdefault(ticker, {})[dt] = target

    unique_days = sorted(set(q[1] for q in quads))
    days_arr = np.array(unique_days, dtype=object)
    rng = np.random.RandomState(seed)
    null_rs = np.empty(n_replicates)

    for rep in range(n_replicates):
        perm_idx = rng.permutation(len(days_arr))
        day_map = dict(zip(unique_days, days_arr[perm_idx]))
        perm_oi, perm_target = [], []
        for ticker, dt, oi, target in quads:
            perm_date = day_map[dt]
            t = by_ticker_target[ticker].get(perm_date)
            if t is None:
                continue
            perm_oi.append(oi)
            perm_target.append(t)
        null_rs[rep] = pearson_r(perm_oi, perm_target) if len(perm_oi) >= 10 else 0.0

    if direction == "positive":
        p = float(np.mean(null_rs >= r_obs))
    else:
        p = float(np.mean(null_rs <= r_obs))
    return r_obs, p, n


def build_quads(rows, oi_col_idx, target_col_idx, exclude_ticker=None):
    out = []
    for r in rows:
        ticker, dt = r[0], r[1]
        if exclude_ticker is not None and ticker == exclude_ticker:
            continue
        oi = r[oi_col_idx]
        target = r[target_col_idx]
        if oi is None or target is None:
            continue
        out.append((ticker, dt, oi, target))
    return out


def main():
    report = {}
    log("Loading Stage 1 primary dataset (already integrity-checked)...")
    rows = load_primary_rows()
    n_total = len(rows)
    log(f"Loaded {n_total} rows")
    report["n_total"] = n_total
    report["n_meets_floor"] = n_total >= MIN_N

    # target_col_idx in the raw row tuple: 0=ticker,1=obs_date,2=oi_skew,3=ret10,4=ret20,5=ret50
    HORIZON_IDX = {10: 3, 20: 4, 50: 5}

    # ---- PRIMARY TEST (20-day horizon) ----
    log("\n=== PRIMARY TEST (20-day horizon) ===")
    primary_quads = build_quads(rows, oi_col_idx=2, target_col_idx=HORIZON_IDX[PRIMARY_HORIZON])
    primary_result = {}
    for seed in SEEDS:
        r_obs, p, n = day_clustered_test(primary_quads, seed)
        primary_result[f"seed{seed}"] = {"r": r_obs, "p_one_sided": p, "n": n}
        log(f"  seed={seed}: r={r_obs:+.4f} p={p:.4f} n={n}")
    report["primary_result"] = primary_result
    r_obs_primary = primary_result["seed42"]["r"]  # deterministic given data, identical both seeds

    # ---- Robustness 1: leave_one_ticker_out ----
    log("\n=== Robustness 1/5: leave_one_ticker_out ===")
    loto = {}
    for excl in TICKERS:
        quads = build_quads(rows, oi_col_idx=2, target_col_idx=HORIZON_IDX[PRIMARY_HORIZON], exclude_ticker=excl)
        per_seed = {}
        for seed in SEEDS:
            r_obs, p, n = day_clustered_test(quads, seed)
            per_seed[f"seed{seed}"] = {"r": r_obs, "p_one_sided": p, "n": n}
        loto[excl] = per_seed
        log(f"  excl {excl}: seed42 r={per_seed['seed42']['r']:+.4f} p={per_seed['seed42']['p_one_sided']:.4f} n={per_seed['seed42']['n']} "
            f"| seed43 r={per_seed['seed43']['r']:+.4f} p={per_seed['seed43']['p_one_sided']:.4f}")
    report["robustness_leave_one_ticker_out"] = loto

    # ---- Robustness 2/3: alternate_horizon 10d, 50d ----
    log("\n=== Robustness 2-3/5: alternate_horizon 10d, 50d ===")
    alt_horizon = {}
    for h in (10, 50):
        quads = build_quads(rows, oi_col_idx=2, target_col_idx=HORIZON_IDX[h])
        per_seed = {}
        for seed in SEEDS:
            r_obs, p, n = day_clustered_test(quads, seed)
            per_seed[f"seed{seed}"] = {"r": r_obs, "p_one_sided": p, "n": n}
        alt_horizon[f"{h}day"] = per_seed
        log(f"  {h}-day: seed42 r={per_seed['seed42']['r']:+.4f} p={per_seed['seed42']['p_one_sided']:.4f} "
            f"| seed43 r={per_seed['seed43']['r']:+.4f} p={per_seed['seed43']['p_one_sided']:.4f}")
    report["robustness_alternate_horizon"] = alt_horizon

    # ---- Robustness 4/5: alternate_moneyness_band:15pct, alternate_dte_window:7-30dte ----
    log("\n=== Robustness 4-5/5: alternate_moneyness_band (15%), alternate_dte_window (7-30 DTE) ===")
    variant_rows = load_variant_rows()
    report["n_variant_rows"] = len(variant_rows)
    log(f"Loaded {len(variant_rows)} variant rows")

    # Sanity check: primary_recomputed should match the stored primary oi_skew (join by ticker,obs_date)
    primary_by_key = {(r[0], r[1]): r[2] for r in rows}
    mismatches = 0
    for ticker, obs_date, primary_recomputed, band15, dte730 in variant_rows:
        stored = primary_by_key.get((ticker, obs_date))
        if stored is not None and primary_recomputed is not None and abs(primary_recomputed - stored) > 1e-9:
            mismatches += 1
    log(f"  Consistency check (recomputed primary vs. stored primary): {mismatches} mismatches out of {len(variant_rows)}")
    report["variant_consistency_check_mismatches"] = mismatches

    # Build (ticker, obs_date) -> target_return_20d lookup from the primary rows
    target20_by_key = {(r[0], r[1]): r[HORIZON_IDX[PRIMARY_HORIZON]] for r in rows}

    def build_variant_quads(variant_col_idx):
        out = []
        for r in variant_rows:
            ticker, obs_date = r[0], r[1]
            oi = r[variant_col_idx]
            target = target20_by_key.get((ticker, obs_date))
            if oi is None or target is None:
                continue
            out.append((ticker, obs_date, oi, target))
        return out

    alt_param = {}
    for label, col_idx in [("alternate_moneyness_band:15pct", 3), ("alternate_dte_window:7-30dte", 4)]:
        quads = build_variant_quads(col_idx)
        per_seed = {}
        for seed in SEEDS:
            r_obs, p, n = day_clustered_test(quads, seed)
            per_seed[f"seed{seed}"] = {"r": r_obs, "p_one_sided": p, "n": n}
        alt_param[label] = per_seed
        log(f"  {label}: n={per_seed['seed42']['n']} seed42 r={per_seed['seed42']['r']:+.4f} p={per_seed['seed42']['p_one_sided']:.4f} "
            f"| seed43 r={per_seed['seed43']['r']:+.4f} p={per_seed['seed43']['p_one_sided']:.4f}")
    report["robustness_alternate_parameters"] = alt_param

    # ---- Decision rules, applied literally ----
    log("\n=== Applying decision rules (literal text quoted in module docstring) ===")

    n_ok = n_total >= MIN_N
    p42 = primary_result["seed42"]["p_one_sided"]
    p43 = primary_result["seed43"]["p_one_sided"]
    primary_significant = (p42 < ALPHA_CORRECTED) and (p43 < ALPHA_CORRECTED)
    effect_met = abs(r_obs_primary) >= EFFECT_SIZE_THRESHOLD
    direction_positive = r_obs_primary > 0

    # Robustness "survives... in the same direction" -- literal text, direction-consistency is the bar
    robustness_directions = {}
    robustness_directions["leave_one_ticker_out"] = {t: loto[t]["seed42"]["r"] > 0 for t in TICKERS}
    robustness_directions["alternate_horizon:10day"] = alt_horizon["10day"]["seed42"]["r"] > 0
    robustness_directions["alternate_horizon:50day"] = alt_horizon["50day"]["seed42"]["r"] > 0
    robustness_directions["alternate_moneyness_band:15pct"] = alt_param["alternate_moneyness_band:15pct"]["seed42"]["r"] > 0
    robustness_directions["alternate_dte_window:7-30dte"] = alt_param["alternate_dte_window:7-30dte"]["seed42"]["r"] > 0

    loto_all_positive = all(robustness_directions["leave_one_ticker_out"].values())
    all_five_direction_ok = (
        loto_all_positive
        and robustness_directions["alternate_horizon:10day"]
        and robustness_directions["alternate_horizon:50day"]
        and robustness_directions["alternate_moneyness_band:15pct"]
        and robustness_directions["alternate_dte_window:7-30dte"]
    )

    report["decision_inputs"] = {
        "n_total": n_total, "n_ok": n_ok,
        "primary_r": r_obs_primary, "primary_p42": p42, "primary_p43": p43,
        "primary_significant_both_seeds": primary_significant,
        "effect_size_met": effect_met, "direction_positive": direction_positive,
        "robustness_directions": robustness_directions,
        "all_five_robustness_direction_ok": all_five_direction_ok,
    }

    if not n_ok:
        verdict, reason = "INCONCLUSIVE", f"Stage 1 N={n_total} < {MIN_N}"
    elif primary_significant and effect_met and direction_positive and all_five_direction_ok:
        verdict = "STAGE 1 VALIDATED (pending Stage 2 -- Stage 2 has zero rows, not yet built/run, per this project's established RF-v2/IV-term-structure precedent: Stage-1-VALIDATED is not overall-VALIDATED until Stage 2 independently replicates)"
        reason = "Primary significant at corrected alpha both seeds, effect size >=0.15 met, direction positive as hypothesized, all 5 robustness checks direction-consistent (positive)"
    else:
        reasons = []
        if not primary_significant:
            reasons.append(f"primary test not significant at corrected alpha={ALPHA_CORRECTED:.4f} at both seeds (p42={p42:.4f}, p43={p43:.4f})")
        if not effect_met:
            reasons.append(f"effect size |r|={abs(r_obs_primary):.4f} below threshold {EFFECT_SIZE_THRESHOLD}")
        if not direction_positive:
            reasons.append(f"primary correlation is NEGATIVE (r={r_obs_primary:+.4f}) -- direction reversed from the hypothesized positive/contrarian direction")
        if not loto_all_positive:
            reversed_tickers = [t for t, ok in robustness_directions["leave_one_ticker_out"].items() if not ok]
            reasons.append(f"leave_one_ticker_out: direction reverses excluding {reversed_tickers}")
        if not robustness_directions["alternate_horizon:10day"]:
            reasons.append("alternate_horizon:10day reverses direction")
        if not robustness_directions["alternate_horizon:50day"]:
            reasons.append("alternate_horizon:50day reverses direction")
        if not robustness_directions["alternate_moneyness_band:15pct"]:
            reasons.append("alternate_moneyness_band:15pct reverses direction")
        if not robustness_directions["alternate_dte_window:7-30dte"]:
            reasons.append("alternate_dte_window:7-30dte reverses direction")
        verdict = "REJECTED"
        reason = "; ".join(reasons)

    report["stage1_verdict"] = verdict
    report["stage1_verdict_reason"] = reason

    log("\n" + "=" * 100)
    log(f"STAGE 1 VERDICT: {verdict}")
    log(f"REASON: {reason}")
    log("=" * 100)

    with open("strike_positioning_stage1_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log("\nFull results written to strike_positioning_stage1_results.json")


if __name__ == "__main__":
    main()

"""
Stage 1 execution for trial #13, vix_termstructure_vrp_index_timing_v1_20261002
(registered 2026-10-02T18:36:18Z, hash 188828a66ad359c28692d923a8c7c57d8d91cdd507b1932f6427acb38e488d09;
CLAUDE.md Section 63). Implements the registered plan exactly; every rule below cites the config.

  python vrp_timing_stage1_execution.py --selftest   # synthetic data with a planted effect; no real returns used
  python vrp_timing_stage1_execution.py              # THE run: once, on the verified snapshot

Writes vrp_timing_stage1_results.json (real run only). Does not touch research_database.db.
"""
import json
import sqlite3
import sys
from datetime import date

import numpy as np
from scipy import stats

import preregister_vix_termstructure_vrp_experiment as prereg
from build_vrp_timing_dataset import load_cycles, verify, VIX6M_FIRST_SIGNAL

SEEDS = [42, 43]
N_PERM = 10_000
ALPHA = 0.05
RHO_FLOOR = 0.15
REGISTERED_HASH = "188828a66ad359c28692d923a8c7c57d8d91cdd507b1932f6427acb38e488d09"
BURN_IN = 36            # nonlinearity + economic check: first 36 cycles are burn-in
OOS_START = 60          # "from cycle 61 on" -> zero-based index 60


# ---------------------------------------------------------------- statistics
def rank(a):
    return stats.rankdata(a)


def pearson(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a - a.mean(), b - b.mean()
    return float((a @ b) / np.sqrt((a @ a) * (b @ b)))


def perm_p(x, y, obs, seed, n=None):
    """One-sided: share of permuted Pearson(x, perm(y)) >= obs (registered definition)."""
    n = n or N_PERM
    rng = np.random.default_rng(seed)
    x = np.asarray(x, float); y = np.asarray(y, float)
    x = (x - x.mean()) / np.linalg.norm(x - x.mean())
    yc = y - y.mean(); yc /= np.linalg.norm(yc)
    P = np.array([rng.permutation(yc) for _ in range(n)])
    null = P @ x
    return float(np.mean(null >= obs)), null


def spearman_test(x, y, seeds=SEEDS):
    rx, ry = rank(x), rank(y)
    rho = pearson(rx, ry)
    ps = {s: perm_p(rx, ry, rho, s)[0] for s in seeds}
    return rho, ps


def residualize(v, controls):
    X = np.column_stack([np.ones(len(v))] + [np.asarray(c, float) for c in controls])
    beta, *_ = np.linalg.lstsq(X, np.asarray(v, float), rcond=None)
    return np.asarray(v, float) - X @ beta


def partial_spearman(x, y, controls, seeds=SEEDS):
    rc = [rank(c) for c in controls]
    ex, ey = residualize(rank(x), rc), residualize(rank(y), rc)
    r = pearson(ex, ey)
    ps = {s: perm_p(ex, ey, r, s)[0] for s in seeds}
    return r, ps


def stationary_bootstrap_p(x, y, obs, seed, n=None, mean_block=6):
    n = n or N_PERM
    rng = np.random.default_rng(seed)
    T = len(y); rx = rank(x); y = np.asarray(y, float)
    out = np.empty(n)
    for b in range(n):
        idx = np.empty(T, int); i = rng.integers(T)
        for t in range(T):
            if t > 0:
                i = rng.integers(T) if rng.random() < 1 / mean_block else (i + 1) % T
            idx[t] = i
        out[b] = pearson(rx, rank(y[idx]))
    return float(np.mean(out >= obs))


def expanding_cutoffs(slope):
    """cutoff_k = 20th percentile of slopes 0..k-1, for k >= BURN_IN (past slopes only)."""
    return {k: float(np.percentile(slope[:k], 20)) for k in range(BURN_IN, len(slope))}


def oos_r2(x, y):
    sse_m = sse_b = 0.0
    for k in range(OOS_START, len(y)):
        X = np.column_stack([np.ones(k), x[:k]])
        b, *_ = np.linalg.lstsq(X, y[:k], rcond=None)
        sse_m += (y[k] - (b[0] + b[1] * x[k])) ** 2
        sse_b += (y[k] - y[:k].mean()) ** 2
    return 1 - sse_m / sse_b


def amihud_hurvich(x, x_next, y):
    n = len(x)
    A = np.column_stack([np.ones(n), x])
    (a_hat, rho_hat), *_ = np.linalg.lstsq(A, x_next, rcond=None)
    rho_c = rho_hat + (1 + 3 * rho_hat) / n + 3 * (1 + 3 * rho_hat) / n ** 2
    a_c = x_next.mean() - rho_c * x.mean()
    v_c = x_next - a_c - rho_c * x
    B = np.column_stack([np.ones(n), x, v_c])
    coef, *_ = np.linalg.lstsq(B, y, rcond=None)
    ols, *_ = np.linalg.lstsq(A, y, rcond=None)
    return {"beta_corrected": float(coef[1]), "beta_ols": float(ols[1]),
            "ar1_rho_hat": float(rho_hat), "ar1_rho_corrected": float(rho_c)}


# ---------------------------------------------------------------- economic check
def economic(rows, slope, cut):
    ks = list(range(BURN_IN, len(rows)))
    held = np.array([slope[k] >= cut[k] for k in ks])
    xs_A = np.array([rows[k]["CNDR_xs"] for k in ks]); raw_A = np.array([rows[k]["CNDR_raw"] for k in ks])
    rf = np.array([rows[k]["rf"] for k in ks])
    xs_T = np.where(held, xs_A, 0.0); raw_T = np.where(held, raw_A, rf)

    def summ(xs, raw):
        wealth = np.cumprod(1 + raw)
        dd = 1 - wealth / np.maximum.accumulate(wealth)
        return {"mean_excess_per_cycle": float(xs.mean()), "ann_excess_return": float(xs.mean() * 12),
                "ann_vol": float(xs.std(ddof=1) * np.sqrt(12)),
                "sharpe": float(xs.mean() / xs.std(ddof=1) * np.sqrt(12)),
                "max_drawdown": float(dd.max()), "worst_cycle_raw": float(raw.min()),
                "total_growth_of_1": float(wealth[-1])}
    A, T = summ(xs_A, raw_A), summ(xs_T, raw_T)
    f = float(held.mean())
    mA, mT = A["mean_excess_per_cycle"], T["mean_excess_per_cycle"]
    out = {"cycles": len(ks), "first_cycle_signal": str(rows[ks[0]]["signal_date"]),
           "fraction_held": f, "cycles_in_tbills": int((~held).sum()),
           "switches": int(np.sum(held[1:] != held[:-1])),
           "always_on_CNDR": A, "timed": T,
           "breakeven_cost_per_roll_timed_excess_zero": (mT / f) if f > 0 else None,
           "breakeven_cost_per_roll_always_on_excess_zero": mA}
    if mT >= mA:
        out["timed_vs_always_on"] = ("timed mean excess >= always-on at zero cost; costs (paid only in held "
                                     "cycles) widen the gap, so no break-even exists")
        out["breakeven_cost_per_roll_timed_advantage_vanishes"] = None
    else:
        out["timed_vs_always_on"] = "timed mean excess < always-on at zero cost; costs narrow the gap"
        out["breakeven_cost_per_roll_timed_advantage_vanishes"] = (mA - mT) / (1 - f) if f < 1 else None
    return out


def spy_cost_estimate():
    """Entry cost of a CNDR-like SPY condor from real EODHD end-of-day quotes (Section 26 source),
    as % of a CNDR-style account (10x max loss) and of max loss alone. Held to expiry: entry only."""
    rolls = [("2026-06-18", "2026-07-17"), ("2026-07-17", "2026-08-21"), ("2026-08-21", "2026-09-18")]
    try:
        g = sqlite3.connect("file:gex_data_cache.db?mode=ro", uri=True)
    except sqlite3.Error as e:
        return {"error": str(e)}
    est = []
    for d, exp in rolls:
        recs = [json.loads(r[0]) for r in g.execute(
            "SELECT raw_json FROM raw_records WHERE ticker='SPY' AND requested_date=? AND matches_requested_date=1", (d,))]
        recs = [r for r in recs if r.get("exp_date") == exp and r.get("delta") is not None
                and r.get("bid") is not None and r.get("ask") is not None and r["ask"] > 0]
        if not recs:
            est.append({"date": d, "expiry": exp, "error": "no quotes"}); continue
        def pick(typ, target):
            c = [r for r in recs if r["type"] == typ]
            return min(c, key=lambda r: abs(abs(r["delta"]) - target)) if c else None
        sp, sc, lp, lc = pick("put", .20), pick("call", .20), pick("put", .05), pick("call", .05)
        if None in (sp, sc, lp, lc):
            est.append({"date": d, "expiry": exp, "error": "missing leg"}); continue
        mid = lambda r: (r["bid"] + r["ask"]) / 2
        half = sum((r["ask"] - r["bid"]) / 2 for r in (sp, sc, lp, lc))
        credit = mid(sp) + mid(sc) - mid(lp) - mid(lc)
        max_loss = max(lc["strike"] - sc["strike"], sp["strike"] - lp["strike"]) - credit
        est.append({"date": d, "expiry": exp,
                    "legs": {k: {"strike": r["strike"], "delta": r["delta"], "bid": r["bid"], "ask": r["ask"]}
                             for k, r in (("short_put", sp), ("short_call", sc), ("long_put", lp), ("long_call", lc))},
                    "sum_half_spreads": half, "credit_mid": credit, "max_loss": max_loss,
                    "cost_pct_of_cndr_account": half / (10 * max_loss),
                    "cost_pct_of_max_loss": half / max_loss})
    ok = [e for e in est if "cost_pct_of_cndr_account" in e]
    return {"source": "gex_data_cache.db raw_records, SPY, EODHD end-of-day bid/ask, id-date matched",
            "caveat": "SPY options (American, physically settled) as a proxy for SPX/XSP; 3 recent rolls only; "
                      "end-of-day quotes, not 11:00 ET",
            "per_roll": est,
            "median_cost_pct_of_cndr_account": float(np.median([e["cost_pct_of_cndr_account"] for e in ok])) if ok else None,
            "median_cost_pct_of_max_loss": float(np.median([e["cost_pct_of_max_loss"] for e in ok])) if ok else None}


# ---------------------------------------------------------------- the run
def run(rows, rows6, selftest=False):
    R = {}
    y = np.array([r["CNDR_xs"] for r in rows]); x = np.array([r["slope"] for r in rows])
    n = len(rows); R["n_cycles"] = n
    R["window"] = [str(rows[0]["signal_date"]), str(rows[-1]["end_date"])]

    # integrity (no relationship): stale index values at endpoints
    R["integrity"] = {p: int(sum(1 for r in rows if r[f"{p}_raw"] == 0.0)) for p in ("CNDR", "BFLY", "PUT", "BXM")}
    R["descriptive"] = {"slope_mean": float(x.mean()), "slope_min": float(x.min()), "slope_max": float(x.max()),
                        "share_inverted_slope_lt_0": float(np.mean(x < 0)),
                        "CNDR_xs_mean": float(y.mean()), "CNDR_xs_sd": float(y.std(ddof=1)),
                        "CNDR_xs_min": float(y.min()), "CNDR_xs_max": float(y.max())}

    # 1. primary
    rho, ps = spearman_test(x, y)
    R["primary"] = {"spearman_rho": rho, "p_one_sided": ps, "n": n,
                    "significant_both_seeds": all(p < ALPHA for p in ps.values()), "rho_ge_floor": rho >= RHO_FLOOR}

    # 2. gate
    pr, pps = partial_spearman(x, y, [[r["ln_vix"] for r in rows], [r["vrp_proxy"] for r in rows]])
    R["vrp_control_gate"] = {"partial_rho": pr, "p_one_sided": pps,
                             "pass": pr > 0 and all(p < ALPHA for p in pps.values())}

    # 3. the 13 sign checks
    chk = {}
    def sp_sign(name, xx, yy, extra=None, seed_p=True):
        r_ = pearson(rank(xx), rank(yy))
        d = {"statistic": "spearman_rho", "value": r_, "n": len(yy), "hypothesized_sign": "+", "pass": r_ > 0}
        if seed_p:
            d["p_one_sided_seed42_info_only"] = perm_p(rank(xx), rank(yy), r_, 42)[0]
        if extra:
            d.update(extra)
        chk[name] = d
    for p in ("BFLY", "PUT", "BXM"):
        sp_sign(f"alternate_payoff:{p}", x, [r[f"{p}_xs"] for r in rows])
    pe = pearson(x, y)
    chk["alternate_statistic:pearson"] = {"statistic": "pearson_r", "value": pe, "n": n, "hypothesized_sign": "+",
                                          "pass": pe > 0, "p_one_sided_seed42_info_only": perm_p(x, y, pe, 42)[0]}
    sp_sign("alternate_signal:ln_vix6m_over_vix_from_2008", [r["slope"] for r in rows6], [r["CNDR_xs"] for r in rows6],
            {"window": [str(rows6[0]["signal_date"]), str(rows6[-1]["end_date"])]})
    for name, d0 in (("subsample:post_johnson_sample_2014plus", date(2014, 1, 1)),
                     ("subsample:post_index_launch_2015_08plus", date(2015, 8, 3))):
        m = np.array([r["signal_date"] >= d0 for r in rows])
        sp_sign(name, x[m], y[m])
    cut = expanding_cutoffs(x)
    ks = range(BURN_IN, n)
    bottom = np.array([x[k] < cut[k] for k in ks]); yk = y[BURN_IN:]
    diff = float(yk[bottom].mean() - yk[~bottom].mean())
    chk["nonlinearity:bottom_quintile"] = {"statistic": "mean_xs_bottom_minus_rest", "value": diff,
                                           "n_bottom": int(bottom.sum()), "n_rest": int((~bottom).sum()),
                                           "mean_bottom": float(yk[bottom].mean()), "mean_rest": float(yk[~bottom].mean()),
                                           "hypothesized_sign": "-", "pass": diff < 0}
    o = oos_r2(x, y)
    chk["oos_r2_vs_historical_mean"] = {"statistic": "oos_r2", "value": float(o), "n_forecasts": n - OOS_START,
                                        "pass_condition": "> 0", "pass": o > 0}
    ah = amihud_hurvich(x, np.array([r["slope_next"] for r in rows]), y)
    chk["stambaugh_bias_corrected"] = {"statistic": "amihud_hurvich_beta", "value": ah["beta_corrected"], **ah,
                                       "hypothesized_sign": "+", "pass": ah["beta_corrected"] > 0}
    lr, lps = partial_spearman(x, y, [[r["CNDR_xs_lag"] for r in rows]], seeds=[42])
    chk["partial_control:lagged_own_return"] = {"statistic": "partial_spearman", "value": lr,
                                                "p_one_sided_seed42_info_only": lps[42],
                                                "hypothesized_sign": "+", "pass": lr > 0}
    keep = np.argsort(-np.abs(y))[5:]; keep.sort()
    sp_sign("drop_top5_abs_return_cycles", x[keep], y[keep],
            {"dropped_signal_dates": [str(rows[i]["signal_date"]) for i in sorted(np.argsort(-np.abs(y))[:5])]})
    bp = {s: stationary_bootstrap_p(x, y, rho, s) for s in SEEDS}
    chk["alternate_null:stationary_block_bootstrap"] = {"statistic": "spearman_rho (primary)", "value": rho,
                                                        "p_one_sided": bp, "hypothesized_sign": "+", "pass": rho > 0}
    assert len(chk) == 13, len(chk)
    R["sign_checks"] = chk
    fails = [k for k, v in chk.items() if not v["pass"]]
    R["sign_check_failures"] = fails

    # 4. verdict (registered DECISION_RULES)
    reasons = []
    if n < 180:
        verdict = "INCONCLUSIVE"; reasons.append("N < 180")
    else:
        if not R["primary"]["significant_both_seeds"]:
            reasons.append("primary not significant at 0.05 (both seeds required)")
        if rho < RHO_FLOOR:
            reasons.append(f"rho {rho:.3f} < floor 0.15")
        if not R["vrp_control_gate"]["pass"]:
            reasons.append("vrp_control_gate failed (automatic REJECTED)")
        if "subsample:post_johnson_sample_2014plus" in fails:
            reasons.append("post-2014 subsample has the wrong sign (automatic REJECTED)")
        if len(fails) >= 2:
            reasons.append(f"{len(fails)} sign checks failed (max 1 allowed)")
        verdict = "REJECTED" if reasons else "SUGGESTIVE"
    R["verdict"] = verdict; R["verdict_reasons"] = reasons

    # 5. economic check (reported whatever the verdict)
    R["economic_check"] = economic(rows, x, cut)
    if not selftest:
        R["economic_check"]["cost_estimate_spy_eod"] = spy_cost_estimate()
    return R


def selftest():
    """Synthetic: real slope dates/values replaced by a simulated AR(1) slope and a planted effect."""
    _, _, rows = load_cycles()
    _, _, rows6 = load_cycles("VIX6M", first_signal=VIX6M_FIRST_SIGNAL)
    rng = np.random.default_rng(7)
    for rs in (rows, rows6):
        s = 0.0
        for r in rs:
            s = 0.7 * s + rng.standard_normal() * 0.7
            r["slope"] = s; r["ln_vix"] = rng.standard_normal(); r["vrp_proxy"] = rng.standard_normal()
            for p in ("CNDR", "BFLY", "PUT", "BXM"):
                r[f"{p}_xs"] = 0.004 * s + rng.standard_normal() * 0.01
                r[f"{p}_raw"] = r[f"{p}_xs"] + r["rf"]
            r["CNDR_xs_lag"] = rng.standard_normal()
        for a, b in zip(rs, rs[1:]):
            a["slope_next"] = b["slope"]
        rs[-1]["slope_next"] = 0.7 * rs[-1]["slope"]
    global N_PERM
    N_PERM = 500
    R = run(rows, rows6, selftest=True)
    print("SELFTEST (synthetic planted effect, rho should be clearly > 0):")
    print(" primary", R["primary"]); print(" gate", R["vrp_control_gate"])
    print(" fails", R["sign_check_failures"], "verdict", R["verdict"], R["verdict_reasons"])
    print(" economic keys", list(R["economic_check"]))
    print(" cost estimate (real SPY quotes, not returns):", json.dumps(spy_cost_estimate(), default=str)[:600])


def main():
    if prereg.config.config_hash != REGISTERED_HASH:
        raise SystemExit("config hash differs from the registered hash; refusing to run")
    verify()
    snap, manifest, rows = load_cycles()
    _, _, rows6 = load_cycles("VIX6M", first_signal=VIX6M_FIRST_SIGNAL)
    R = run(rows, rows6)
    R["experiment_id"] = prereg.config.experiment_id; R["config_hash"] = REGISTERED_HASH
    R["snapshot"] = snap.name
    R["snapshot_sha256"] = {k: v["sha256"] for k, v in manifest["files"].items()}
    with open("vrp_timing_stage1_results.json", "w", encoding="utf-8") as f:
        json.dump(R, f, indent=1, default=str)
    print(json.dumps({k: R[k] for k in ("n_cycles", "window", "integrity", "descriptive", "primary",
                                        "vrp_control_gate", "sign_check_failures", "verdict", "verdict_reasons")},
                     indent=1, default=str))
    print("full results: vrp_timing_stage1_results.json")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()

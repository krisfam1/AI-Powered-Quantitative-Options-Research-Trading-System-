"""Stage 3: descriptive regime map of the SPX volatility-premium gap (stage3_protocol.md, commit 764fa3a).

Development years only (dev_guard). Five labelings L1-L5; per-regime distribution of
G = VIX^2 - forward 21d realized variance. Descriptive: no tests, no pass/fail.
Every real labeling run appends one search-ledger row.
"""
import json
import uuid
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression

import search_ledger
from common import RESULTS, dev_guard
from features import _pct_rank
from stage2 import build_inputs, load

BLOCK, N_BOOT, SEED, SEARCH_REPS = 42, 2000, 42, 20


def _fit(endog, k, search_reps):
    """Fit with the protocol's random-start search. If statsmodels' EM step crashes (degenerate
    transition probabilities), retry once with EM skipped (em_iter=0) from default start values.
    A retry is recorded in the returned convergence flag."""
    model = MarkovRegression(endog, k_regimes=k, trend="c", switching_variance=True)
    for attempt in ({"search_reps": search_reps}, {"search_reps": 0, "em_iter": 0}):
        np.random.seed(SEED)
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                res = model.fit(disp=False, **attempt)
        except (RuntimeError, np.linalg.LinAlgError):
            if "em_iter" in attempt:
                raise
            continue
        conv = not any("converge" in str(x.message).lower() for x in w)
        return res, (conv if "em_iter" not in attempt else f"retried_no_em;converged={conv}")


def _means(res, k):
    names = list(res.model.param_names)
    return np.array([np.asarray(res.params)[names.index(f"const[{i}]")] for i in range(k)])


def _order(res, k):
    """Map model regime index -> rank by fitted mean (0 = lowest)."""
    return {int(m): r for r, m in enumerate(np.argsort(_means(res, k)))}


def _labels_from_filtered(probs, order):
    raw = np.asarray(probs).argmax(axis=1)
    return np.array([order[int(x)] for x in raw])


def label_full(lv, k, search_reps=SEARCH_REPS):
    """L1/L2: one full-dev fit (parameter look-ahead disclosed); filtered-probability labels."""
    dev_guard(lv.index, "label_full")
    res, conv = _fit(lv.to_numpy(), k, search_reps)
    lab = pd.Series(_labels_from_filtered(res.filtered_marginal_probabilities, _order(res, k)), index=lv.index)
    return lab, {"bic": float(res.bic), "converged": conv, "means_lnvix": sorted(map(float, _means(res, k)))}


def label_expanding(lv, k, search_reps=SEARCH_REPS, first_year=2010):
    """L3/L4: refit on the first session of each year from first_year on data before it; causal filtering."""
    dev_guard(lv.index, "label_expanding")
    out = pd.Series(np.nan, index=lv.index)
    meta = []
    for yr in range(first_year, lv.index.max().year + 1):
        in_year = lv.index.year == yr
        if not in_year.any():
            continue
        start = lv.index[in_year][0]
        train = lv[lv.index < start]
        res, conv = _fit(train.to_numpy(), k, search_reps)
        upto = lv[lv.index <= lv.index[in_year][-1]]
        filt = MarkovRegression(upto.to_numpy(), k_regimes=k, trend="c",
                                switching_variance=True).filter(res.params)
        lab = _labels_from_filtered(filt.filtered_marginal_probabilities, _order(res, k))
        out[in_year] = lab[-in_year.sum():]
        meta.append({"year": yr, "n_train": int(len(train)), "converged": conv, "bic": float(res.bic)})
    return out.dropna().astype(int), {"refits": meta}


def label_rule(vix):
    """L5: rolling 252-day VIX percentile terciles (Stage 1 vix__pct252 formula)."""
    dev_guard(vix.index, "label_rule")
    p = _pct_rank(vix, 252)
    lab = pd.Series(np.where(p < 1 / 3, 0, np.where(p > 2 / 3, 2, 1)), index=vix.index)
    return lab[p.notna()], {}


def _boot_mean_ci(x, seed=SEED):
    x = np.asarray(x)
    n = len(x)
    if n < BLOCK:
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / BLOCK))
    idx = ((rng.integers(0, n, (N_BOOT, nb))[:, :, None] + np.arange(BLOCK)) % n).reshape(N_BOOT, -1)[:, :n]
    m = x[idx].mean(axis=1)
    return [float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]


def describe(lab, d):
    """Per-regime distribution of G plus context; descriptive only."""
    dev_guard(lab.index, "describe")
    df = pd.DataFrame({"lab": lab}).join(d[["G", "vix", "rvfwd"]], how="inner").dropna()
    df["fwdvol"] = np.sqrt(df["rvfwd"])
    spells = (df["lab"] != df["lab"].shift()).cumsum()
    per = {}
    for r, g in df.groupby("lab"):
        G = g["G"]
        per[int(r)] = {
            "days": int(len(g)), "spells": int(spells[g.index].nunique()),
            "mean_spell_days": float(len(g) / spells[g.index].nunique()),
            "first": str(g.index.min().date()), "last": str(g.index.max().date()),
            "mean_vix": float(g["vix"].mean()), "mean_fwd_vol": float(g["fwdvol"].mean()),
            "G_mean": float(G.mean()), "G_mean_ci95": _boot_mean_ci(G.to_numpy()),
            "G_median": float(G.median()), "G_sd": float(G.std()),
            "G_p05_p25_p75_p95": [float(G.quantile(q)) for q in (0.05, 0.25, 0.75, 0.95)],
            "share_G_negative": float((G < 0).mean()),
            "days_by_year": {str(k): int(v) for k, v in g.groupby(g.index.year).size().items()}}
    l = lab.to_numpy()
    k = int(lab.max()) + 1
    T = np.zeros((k, k))
    for a, b in zip(l[:-1], l[1:]):
        T[a, b] += 1
    rs = T.sum(axis=1, keepdims=True)
    T = np.divide(T, rs, out=np.zeros_like(T), where=rs > 0).round(4).tolist()
    pos = {t: i for i, t in enumerate(lab.index)}
    chg = [bool(len(set(l[pos[t]:pos[t] + 22])) > 1) for t in df.index]
    G = df["G"]
    return {"n_days": int(len(df)), "first": str(df.index.min().date()), "last": str(df.index.max().date()),
            "per_regime": per, "transition_matrix": T,
            "share_forward_window_has_regime_change": float(np.mean(chg)),
            "unconditional": {"G_mean": float(G.mean()), "G_median": float(G.median()),
                              "share_G_negative": float((G < 0).mean()), "G_mean_ci95": _boot_mean_ci(G.to_numpy())}}


def run(d, log=True, search_reps=SEARCH_REPS):
    dev_guard(d.index, "stage3.run")
    lv = np.log(d["vix"].dropna())
    jobs = {"L1": lambda: label_full(lv, 2, search_reps), "L2": lambda: label_full(lv, 3, search_reps),
            "L3": lambda: label_expanding(lv, 2, search_reps), "L4": lambda: label_expanding(lv, 3, search_reps),
            "L5": lambda: label_rule(d["vix"].dropna())}
    out = {"created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "protocol_commit": "764fa3a", "labelings": {}}
    for lid, job in jobs.items():
        lab, meta = job()
        desc = describe(lab, d)
        k = {"L1": 2, "L2": 3, "L3": 2, "L4": 3, "L5": 3}[lid]
        present = sorted(desc["per_regime"])
        spread = desc["per_regime"][present[-1]]["G_mean"] - desc["per_regime"][present[0]]["G_mean"]
        meta["regimes_present"] = present
        rec = {"meta": meta, "k": k, "desc": desc, "high_minus_low_mean_G": spread, "run_id": uuid.uuid4().hex[:12]}
        out["labelings"][lid] = rec
        if log:
            search_ledger.log(
                stage="stage3_regime_map", data_block="dev_2004_2016", value=spread,
                params={"run_id": rec["run_id"], "protocol_commit": "764fa3a", "labeling": lid, "k": k,
                        "meta": meta},
                feature_set="ln_vix" if lid != "L5" else "vix__pct252", transform=lid,
                regime_method="markov_switching" if lid != "L5" else "rule_terciles",
                window="full" if lid in ("L1", "L2") else ("expanding_annual" if lid in ("L3", "L4") else "252"),
                target="G_vix2_minus_fwd21_rv", horizon="21", metric="high_minus_low_mean_G_descriptive")
    return out


if __name__ == "__main__":
    spx, vol, vx = load("2016-12-30", dev_guard)
    d = build_inputs(spx, vol, vx)
    res = run(d, log=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "stage3_regime_map.json").write_text(json.dumps(res, indent=1, default=str))
    for lid, r in res["labelings"].items():
        print(lid, "k", r["k"], "meta", json.dumps(r["meta"])[:300])
        print("   uncond", r["desc"]["unconditional"], "fwd-window-change", round(r["desc"]["share_forward_window_has_regime_change"], 3))
        for reg, p in r["desc"]["per_regime"].items():
            print(f"   regime {reg}: days {p['days']} spells {p['spells']} meanVIX {p['mean_vix']:.1f} fwdvol {p['mean_fwd_vol']:.1f} "
                  f"G mean {p['G_mean']:.1f} {[round(x, 1) for x in p['G_mean_ci95']]} median {p['G_median']:.1f} "
                  f"G<0 {p['share_G_negative']:.2f} q {[round(x) for x in p['G_p05_p25_p75_p95']]} years {p['days_by_year']}")
        print("   transitions", r["desc"]["transition_matrix"])

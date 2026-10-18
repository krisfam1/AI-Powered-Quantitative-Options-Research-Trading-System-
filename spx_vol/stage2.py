"""Stage 2: do 3 pre-chosen state features predict the SPX volatility-premium gap? (stage2_protocol.md)

Protocol committed first: ebdd22d (2026-10-17 22:42:25 ET).
Development: dev_run() on 2008-2016 only (dev_guard). Validation: run_validation(), the ONLY code
allowed to read up to 2020-12-31 (val_guard); 2021+ raises in every step (lock_guard).
Every real run appends exactly one search-ledger row.
"""
import json
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import search_ledger
from common import CLEAN, RESULTS, dev_guard, val_guard
from features import build_curve, read_dev_csv

FEATURES3 = ("fut_slope__raw", "vvix_over_vix__raw", "skew__raw")
H, GAP, MIN_TRAIN = 21, 42, 756          # target horizon; purge 21 + embargo 21; 3 years
BLOCK, N_BOOT, SEED = 42, 10_000, 42
LEVEL_DEV = 1 - 0.05 / 3
LEVEL_VAL = 0.95


def load(last_date, guard):
    spx = read_dev_csv(CLEAN / "spx_daily.csv", "date", last_date, guard).set_index("date")
    vol = read_dev_csv(CLEAN / "vol_indices.csv", "date", last_date, guard).set_index("date")
    vx = read_dev_csv(CLEAN / "vx_futures.csv", "trade_date", last_date, guard)
    return spx, vol, vx


def build_inputs(spx, vol, vx, guard=dev_guard):
    """Baseline inputs, the 3 features (Stage 1 formulas) and targets G and G'; data through t only."""
    guard(spx.index, "build_inputs")
    idx = spx.index
    r2 = np.log(spx["close"] / spx["close"].shift(1)) ** 2
    curve = build_curve(vx, idx, guard)
    vix = vol["vix"].reindex(idx)
    d = pd.DataFrame(index=idx)
    d["vix"] = vix
    d["rvtrail"] = 1e4 * (252 / H) * r2.rolling(H, min_periods=H).sum()
    d["fut_slope__raw"] = curve["cm60"] - curve["cm30"]
    d["vvix_over_vix__raw"] = vol["vvix"].reindex(idx) / vix
    d["skew__raw"] = vol["skew"].reindex(idx)
    fwd = 1e4 * (252 / H) * r2[::-1].rolling(H, min_periods=H).sum()[::-1].shift(-1)  # r_{t+1..t+21}
    d["rvfwd"] = fwd
    d["G"] = vix ** 2 - fwd
    d["Gprime"] = np.log(vix ** 2 / fwd)
    return d


def refit_positions(index):
    """Position of the first session of each calendar month."""
    m = index.to_period("M")
    return np.flatnonzero(np.r_[True, m[1:] != m[:-1]])


def _ols(X, y):
    A = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    return beta


def oos(d, feature, eval_from, eval_to, exclude=None):
    """Expanding-window OOS forecasts of G for baseline and baseline+feature.

    Returns DataFrame of eval rows (y, f_base, f_aug) and the list of refits used.
    """
    cols_b, cols_a = ["vix", "rvtrail"], ["vix", "rvtrail", feature]
    usable = d[cols_a + ["G"]].notna().all(axis=1).to_numpy()
    if exclude is not None:
        usable = usable & ~exclude
    pos_use = np.flatnonzero(usable)
    Xb, Xa, y = d[cols_b].to_numpy(float), d[cols_a].to_numpy(float), d["G"].to_numpy(float)
    refits, fb, fa = [], np.full(len(d), np.nan), np.full(len(d), np.nan)
    rp = refit_positions(d.index)
    origin_ok = usable & (d.index >= eval_from) & (d.index <= eval_to)
    for k, T in enumerate(rp):
        tr = pos_use[pos_use <= T - GAP]
        nxt = rp[k + 1] if k + 1 < len(rp) else len(d)
        seg = np.flatnonzero(origin_ok[T:nxt]) + T
        if len(tr) < MIN_TRAIN:
            continue
        bb, ba = _ols(Xb[tr], y[tr]), _ols(Xa[tr], y[tr])
        refits.append({"refit_date": str(d.index[T].date()), "refit_pos": int(T), "n_train": int(len(tr)),
                       "max_train_pos": int(tr.max()), "beta_base": bb.tolist(), "beta_aug": ba.tolist()})
        if len(seg):
            fb[seg] = bb[0] + Xb[seg] @ bb[1:]
            fa[seg] = ba[0] + Xa[seg] @ ba[1:]
    ev = pd.DataFrame({"y": y, "f_base": fb, "f_aug": fa}, index=d.index).dropna()
    return ev, refits


def boot_improvement(ev, level, n_boot=N_BOOT, seed=SEED):
    eb, ea = (ev["y"] - ev["f_base"]).to_numpy() ** 2, (ev["y"] - ev["f_aug"]).to_numpy() ** 2
    n = len(eb)
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / BLOCK))
    imp = np.empty(n_boot)
    for i in range(n_boot):
        idx = ((rng.integers(0, n, nb)[:, None] + np.arange(BLOCK)[None, :]) % n).ravel()[:n]
        imp[i] = 1 - ea[idx].sum() / eb[idx].sum()
    a = (1 - level) / 2
    return {"improvement_pct": 100 * float(1 - ea.sum() / eb.sum()),
            "ci_pct": [100 * float(np.quantile(imp, a)), 100 * float(np.quantile(imp, 1 - a))],
            "level": level, "n_eval": int(n), "first": str(ev.index[0].date()), "last": str(ev.index[-1].date())}


def dev_run(d, feature, log=True, ledger_note=""):
    dev_guard(d.index, "dev_run")
    eval_to = d.index[-1]
    ev, refits = oos(d, feature, d.index[0], eval_to)
    res = {"feature": feature, "a": boot_improvement(ev, LEVEL_DEV), "refits": len(refits),
           "first_refit": refits[0]["refit_date"], "final_refit": refits[-1]}
    final = refits[-1]
    dev_sign = int(np.sign(final["beta_aug"][3]))
    res["dev_sign"], res["final_coef"] = dev_sign, final["beta_aug"]
    res["a"]["pass"] = res["a"]["improvement_pct"] > 0 and res["a"]["ci_pct"][0] > 0
    # (b) halves, in-sample
    cols = ["vix", "rvtrail", feature]
    u = d[cols + ["G"]].dropna()
    mid = u.index[len(u) // 2]
    h1, h2 = u[u.index < mid].iloc[:-H], u[u.index >= mid]
    c1, c2 = _ols(h1[cols].to_numpy(), h1["G"].to_numpy())[3], _ols(h2[cols].to_numpy(), h2["G"].to_numpy())[3]
    res["b"] = {"split_date": str(mid.date()), "c_half1": float(c1), "c_half2": float(c2),
                "pass": bool(np.sign(c1) == np.sign(c2) != 0)}
    # (c) drop 2008-2009 from training and evaluation
    excl = (d.index <= "2009-12-31")
    ev_c, ref_c = oos(d, feature, d.index[0], eval_to, exclude=np.asarray(excl))
    imp_c = 100 * float(1 - ((ev_c["y"] - ev_c["f_aug"]) ** 2).sum() / ((ev_c["y"] - ev_c["f_base"]) ** 2).sum())
    res["c"] = {"improvement_pct_ex_2008_09": imp_c, "n_eval": int(len(ev_c)),
                "first": str(ev_c.index[0].date()), "pass": imp_c > 0}
    # (d) alternative target G' on the final refit's training rows
    usable = d[cols + ["G"]].notna().all(axis=1).to_numpy()
    tr = np.flatnonzero(usable)
    tr = tr[tr <= final["refit_pos"] - GAP]
    gp = d["Gprime"].to_numpy()[tr]
    ok = np.isfinite(gp)
    cd = _ols(d[cols].to_numpy(float)[tr][ok], gp[ok])[3]
    res["d"] = {"c_Gprime": float(cd), "pass": bool(np.sign(cd) == dev_sign != 0)}
    res["passes_all"] = bool(res["a"]["pass"] and res["b"]["pass"] and res["c"]["pass"] and res["d"]["pass"])
    res["descriptive_mean_G_dev"] = float(d["G"].dropna().mean())
    res["run_id"] = uuid.uuid4().hex[:12]
    if log:
        search_ledger.log(
            stage="stage2_dev", data_block="dev_2004_2016", value=res["a"]["improvement_pct"],
            params={"run_id": res["run_id"], "protocol_commit": "ebdd22d", "feature": feature,
                    "baseline": "G ~ VIX + RVtrail21", "scheme": "expanding OLS, monthly refit, gap 42, min 756",
                    "ci_pct": res["a"]["ci_pct"], "pass_a": res["a"]["pass"], "pass_b": res["b"]["pass"],
                    "pass_c": res["c"]["pass"], "pass_d": res["d"]["pass"], "passes_all": res["passes_all"]},
            feature_set=feature, transform="raw", window="expanding", target="G_vix2_minus_fwd21_rv",
            horizon="21", metric="oos_sse_improvement_pct", notes=ledger_note or None)
    return res


def run_validation(feature, dev_result, log=True, data=None):
    """THE ONLY validation entry point. Reads 2008..2020 (val_guard); 2021+ raises. One run per feature."""
    if data is None:
        spx, vol, vx = load("2020-12-31", val_guard)
        data = build_inputs(spx, vol, vx, guard=val_guard)
    d = data
    val_guard(d.index, "run_validation")
    ev, refits = oos(d, feature, pd.Timestamp("2017-01-03"), d.index[-1])
    res = {"feature": feature, "boot": boot_improvement(ev, LEVEL_VAL), "refits_in_val": sum(
        r["refit_date"] >= "2017-01-01" for r in refits)}
    last_sign = int(np.sign(refits[-1]["beta_aug"][3]))
    res["last_refit_coef"], res["sign_matches_dev"] = refits[-1]["beta_aug"], last_sign == dev_result["dev_sign"]
    first_val = next(r for r in refits if r["refit_date"] >= "2017-01-01")
    res["first_val_refit_trained_through"] = str(d.index[first_val["max_train_pos"]].date())
    fb_, fa_ = dev_result["final_refit"]["beta_base"], dev_result["final_refit"]["beta_aug"]
    Xb, Xa = d.loc[ev.index, ["vix", "rvtrail"]].to_numpy(), d.loc[ev.index, ["vix", "rvtrail", feature]].to_numpy()
    eb = ((ev["y"] - (fb_[0] + Xb @ fb_[1:])) ** 2).sum()
    ea = ((ev["y"] - (fa_[0] + Xa @ fa_[1:])) ** 2).sum()
    res["frozen_2016_coef_improvement_pct_descriptive"] = 100 * float(1 - ea / eb)
    b = res["boot"]
    res["passes"] = bool(b["improvement_pct"] > 0 and res["sign_matches_dev"] and b["ci_pct"][0] > 0)
    res["run_id"] = uuid.uuid4().hex[:12]
    if log:
        search_ledger.log(
            stage="stage2_validation", data_block="val_2017_2020", value=b["improvement_pct"],
            params={"run_id": res["run_id"], "protocol_commit": "ebdd22d", "feature": feature,
                    "ci_pct": b["ci_pct"], "sign_matches_dev": res["sign_matches_dev"], "passes": res["passes"]},
            feature_set=feature, transform="raw", window="expanding", target="G_vix2_minus_fwd21_rv",
            horizon="21", metric="oos_sse_improvement_pct")
    return res


def main():
    spx, vol, vx = load("2016-12-30", dev_guard)
    d = build_inputs(spx, vol, vx)
    out = {"created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "protocol_commit": "ebdd22d", "dev": {}, "validation": {}}
    for f in FEATURES3:
        out["dev"][f] = r = dev_run(d, f, log=True)
        print(f, json.dumps({k: r[k] for k in ("a", "b", "c", "d", "passes_all", "dev_sign")}))
    print("mean G dev (VIX^2 points):", out["dev"][FEATURES3[0]]["descriptive_mean_G_dev"])
    passed = [f for f in FEATURES3 if out["dev"][f]["passes_all"]]
    out["passed_dev"] = passed
    if not passed:
        out["validation"] = "SKIPPED: no feature passed development"
        print("No feature passed development; validation skipped.")
    for f in passed:
        out["validation"][f] = v = run_validation(f, out["dev"][f], log=True)
        print("VALIDATION", f, json.dumps({k: v[k] for k in ("boot", "sign_matches_dev", "passes")}))
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "stage2_results.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()

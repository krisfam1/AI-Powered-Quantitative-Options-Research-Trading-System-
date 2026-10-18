"""Stage 1, Task C: out-of-sample estimator comparison (stage1_protocol.md, Section 3).

Development years only. Target: forward close-to-close realized variance of SPX.
Every real run appends one search-ledger row per (model, horizon); synthetic/test runs never log.
"""
import json
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import search_ledger
from common import RESULTS, dev_guard
from estimators import ESTIMATORS, daily_components, window_estimate

HORIZONS = (21, 5)
FIRST_ORIGIN = pd.Timestamp("2010-01-04")
REFIT_EVERY = 21
FLOOR = 1e-6
N_BOOT, SEED = 2000, 42
BENCHMARKS = ("CC_raw21", "VIX_raw", "VIX_cal", "EWMA")


def forward_target(spx, h):
    """y_h(t) = (252/h) * sum_{i=1..h} r_{t+i}^2; NaN when t+h is beyond the loaded (dev) data."""
    r2 = np.log(spx["close"] / spx["close"].shift(1)) ** 2
    fwd = r2[::-1].rolling(h, min_periods=h).sum()[::-1].shift(-1)
    return 252.0 * fwd / h


def ewma(spx, lam=0.94):
    x = 252.0 * np.log(spx["close"] / spx["close"].shift(1)) ** 2
    out = pd.Series(np.nan, index=spx.index)
    vals = x.to_numpy()
    first = np.flatnonzero(~np.isnan(vals))
    start = first[20]  # seed with the mean of the first 21 values
    s = np.nanmean(vals[first[0]:start + 1])
    out.iloc[start] = s
    for i in range(start + 1, len(vals)):
        if not np.isnan(vals[i]):
            s = lam * s + (1 - lam) * vals[i]
        out.iloc[i] = s
    return out


def inputs(spx, vol):
    """Regressors and raw forecasts, all known at the close of t."""
    comp = daily_components(spx)
    X = {}
    for e in ESTIMATORS:
        for w in (5, 21, 63):
            X[f"{e}_{w}"] = window_estimate(spx, e, w, comp)
    X = pd.DataFrame(X)
    X["vix2"] = (vol["vix"].reindex(spx.index) / 100.0) ** 2
    X["ewma"] = ewma(spx)
    return X, comp


def model_specs():
    specs = {}
    for e in ESTIMATORS:
        specs[f"{e}_raw21"] = ("raw", [f"{e}_21"])
        specs[f"{e}_har"] = ("ols", [f"{e}_5", f"{e}_21", f"{e}_63"])
    specs["VIX_raw"] = ("raw", ["vix2"])
    specs["VIX_cal"] = ("ols", ["vix2"])
    specs["EWMA"] = ("raw", ["ewma"])
    return specs


def training_rows(pos_T, h, ok_positions):
    """Positions s usable for a fit at refit position T: s <= T - 2h (purge h + embargo h)."""
    return ok_positions[ok_positions <= pos_T - 2 * h]


def oos_forecasts(X, y, h, kind, cols, origins_pos):
    n = len(X)
    f = np.full(n, np.nan)
    Xv = X[cols].to_numpy(float)
    if kind == "raw":
        f[origins_pos] = Xv[origins_pos, 0]
        return f, 0, []
    yv = y.to_numpy(float)
    ok = np.flatnonzero(~np.isnan(Xv).any(axis=1) & ~np.isnan(yv))
    refits = origins_pos[::REFIT_EVERY]
    coefs = []
    for k, T in enumerate(refits):
        tr = training_rows(T, h, ok)
        A = np.column_stack([np.ones(len(tr)), Xv[tr]])
        beta, *_ = np.linalg.lstsq(A, yv[tr], rcond=None)
        coefs.append({"refit_pos": int(T), "n_train": int(len(tr)), "max_train_pos": int(tr.max()),
                      "beta": beta.tolist()})
        seg = origins_pos[(origins_pos >= T) & (origins_pos < (refits[k + 1] if k + 1 < len(refits) else n))]
        f[seg] = beta[0] + Xv[seg] @ beta[1:]
    return f, len(refits), coefs


def qlike(y, f):
    q = y / f
    return q - np.log(q) - 1.0


def block_indices(n, block, reps, seed):
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / block))
    starts = rng.integers(0, n, size=(reps, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % n
    return idx.reshape(reps, -1)[:, :n]


def ci(a):
    return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]


def run(spx, vol, log=False, out_name="stage1_estimator_comparison.json"):
    dev_guard(spx.index, "compare.run")
    dev_guard(vol.index, "compare.run(vol)")
    X, comp = inputs(spx, vol)
    specs = model_specs()
    run_id = uuid.uuid4().hex[:12]
    results = {"run_id": run_id, "fallback_days": int(comp["fallback"].sum()),
               "fallback_days_from_2010": int(comp.loc[comp.index >= FIRST_ORIGIN, "fallback"].sum()),
               "horizons": {}}
    for h in HORIZONS:
        y = forward_target(spx, h)
        start = int(np.searchsorted(spx.index, FIRST_ORIGIN))
        cand = np.arange(start, len(spx))
        cand = cand[~np.isnan(y.to_numpy()[cand])]
        F, meta = {}, {}
        for name, (kind, cols) in specs.items():
            f, nref, coefs = oos_forecasts(X, y, h, kind, cols, cand)
            F[name], meta[name] = f, {"kind": kind, "inputs": cols, "refits": nref,
                                      "first_coef": coefs[0] if coefs else None,
                                      "last_coef": coefs[-1] if coefs else None,
                                      "purge_ok": all(c["max_train_pos"] <= c["refit_pos"] - 2 * h for c in coefs)}
        Fm = pd.DataFrame(F, index=spx.index)
        common = Fm.index[cand][Fm.iloc[cand].notna().all(axis=1).to_numpy()]
        yy = y.loc[common].to_numpy()
        losses_q, losses_m, floors = {}, {}, {}
        for name in specs:
            f = Fm.loc[common, name].to_numpy().copy()
            floors[name] = int((f <= FLOOR).sum())
            f[f <= FLOOR] = FLOOR
            losses_q[name] = qlike(yy, f)
            losses_m[name] = (yy - f) ** 2
        block = 42 if h == 21 else 21
        B = block_indices(len(common), block, N_BOOT, SEED)
        hres = {"n_eval": int(len(common)), "first_eval": str(common[0].date()),
                "last_eval": str(common[-1].date()), "block": block, "models": {}}
        for name in specs:
            q, m = losses_q[name], losses_m[name]
            hres["models"][name] = {
                "qlike": float(q.mean()), "qlike_ci": ci(q[B].mean(axis=1)),
                "mse": float(m.mean()), "mse_ci": ci(m[B].mean(axis=1)),
                "floors": floors[name], **meta[name]}

        def diff(a, b, L):
            d = L[a] - L[b]
            return {"mean": float(d.mean()), "ci": ci(d[B].mean(axis=1))}

        har = [f"{e}_har" for e in ESTIMATORS]
        best_har = min(har, key=lambda k: hres["models"][k]["qlike"])
        est_models = [f"{e}_{t}" for e in ESTIMATORS for t in ("raw21", "har")]
        best_any = min(est_models, key=lambda k: hres["models"][k]["qlike"])
        hres["rule_A"] = {"best_har": best_har,
                          "vs_CC_har_qlike": diff(best_har, "CC_har", losses_q) if best_har != "CC_har" else None}
        a = hres["rule_A"]["vs_CC_har_qlike"]
        hres["rule_A"]["adopted_estimator"] = best_har.split("_")[0] if (a and a["ci"][1] < 0) else "CC"
        hres["rule_B"] = {"best_estimator_model": best_any,
                          "vs": {bm: {"qlike": diff(best_any, bm, losses_q), "mse": diff(best_any, bm, losses_m)}
                                 for bm in BENCHMARKS if bm != best_any}}
        for bm, v in hres["rule_B"]["vs"].items():
            v["beats_beyond_noise_qlike"] = v["qlike"]["ci"][1] < 0
        hres["all_pairs_vs_CC_har_qlike"] = {k: diff(k, "CC_har", losses_q) for k in specs if k != "CC_har"}
        results["horizons"][str(h)] = hres
        if log:
            for name in specs:
                mres = hres["models"][name]
                est = name.split("_")[0] if name.split("_")[0] in ESTIMATORS else name
                search_ledger.log(
                    stage="stage1_estimator_comparison", data_block="dev_2004_2016", value=mres["qlike"],
                    params={"run_id": run_id, "model": name, "kind": mres["kind"], "inputs": mres["inputs"],
                            "scheme": "expanding OLS, refit 21, purge h + embargo h, origins 2010-01-04+",
                            "eval_n": hres["n_eval"], "eval_dates": [hres["first_eval"], hres["last_eval"]]},
                    feature_set=est, transform=name, window="5/21/63" if mres["kind"] == "ols" else "21",
                    target="fwd_cc_realized_variance_spx", horizon=str(h), metric="QLIKE",
                    notes=json.dumps({"mse": mres["mse"]}))
    results["chosen_estimator_rule_A_h21"] = results["horizons"]["21"]["rule_A"]["adopted_estimator"]
    results["ledger_rows_logged"] = len(specs) * len(HORIZONS) if log else 0
    results["created_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if log:
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / out_name).write_text(json.dumps(results, indent=1, default=str))
    return results


if __name__ == "__main__":
    from features import load_dev
    spx, vol, _ = load_dev()
    res = run(spx, vol, log=True)
    for h, hr in res["horizons"].items():
        print(f"h={h} n={hr['n_eval']} {hr['first_eval']}..{hr['last_eval']}")
        for k, v in sorted(hr["models"].items(), key=lambda kv: kv[1]["qlike"]):
            print(f"  {k:10s} QLIKE {v['qlike']:.4f} {v['qlike_ci']}  MSE {v['mse']:.3e}  floors {v['floors']}")
        print("  rule A:", hr["rule_A"])
        print("  rule B:", json.dumps(hr["rule_B"]))
    print("chosen estimator:", res["chosen_estimator_rule_A_h21"], "ledger rows:", res["ledger_rows_logged"])

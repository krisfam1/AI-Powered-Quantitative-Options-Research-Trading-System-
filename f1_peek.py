"""ONE-TIME EXPLORATORY look at the F1 dataset (user-approved 2026-10-06). EXPLORATORY, 20% POWER, NOT A VERDICT.
Definitions are the study's (Sections 15, 17, 18): S = AvgEA4 - IM; r_mid; r_net(c) for c = 0.5, 1.0;
intrinsic exit fallback with h_exit = h_entry; per-ISO-week quintiles; week-blocked resampling.
    python f1_peek.py --selftest   # synthetic data only (checks the statistics code)
    python f1_peek.py              # THE single real run
"""
import sqlite3, sys
from datetime import date, timedelta
import numpy as np
from scipy import stats

DB = r"C:\Users\fmkri\Downloads\Python-Backend\Python-Backend\earnings_event_dataset.db"
EXPIRY_MAX_DAYS, N_RES, SEEDS = 7, 10_000, (42, 43)


# --- copied verbatim in logic from earnings_event_pipeline.py (not imported: that module loads .env) ---
def select_contract(c, event_id, kind, obs, R_or_next, spot):
    q = c.execute("SELECT option_type, strike, exp_date, bid, ask FROM option_quotes WHERE event_id=? AND kind=? AND obs_date=?",
                  (event_id, kind, obs)).fetchall()
    lo, hi = R_or_next, (date.fromisoformat(R_or_next) + timedelta(days=EXPIRY_MAX_DAYS)).isoformat()
    exps = sorted({e for _, _, e, _, _ in q if lo <= e <= hi})
    for e in exps[:1]:
        legs = {}
        for typ, k, ex, b, a in q:
            if ex == e and b is not None and a is not None and b > 0 and a > b:
                legs.setdefault(k, {})[typ] = (b, a)
        both = [k for k, v in legs.items() if "call" in v and "put" in v]
        if both:
            k = min(both, key=lambda s: (abs(s - spot), s))
            if abs(k / spot - 1) <= 0.05:
                return e, k, legs[k]["call"], legs[k]["put"]
    return None


def screen(call, put):
    mid = (call[0] + call[1]) / 2 + (put[0] + put[1]) / 2
    spread = (call[1] - call[0]) + (put[1] - put[0])
    return mid >= 1.00 and spread <= 0.10 * mid, mid, spread


def load():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = []
    for eid, t, t0, R, s0, avgea4, spl in c.execute(
            "SELECT event_id, ticker, entry_session, reaction_session, raw_close_t0, avgea4, split_in_window "
            "FROM events WHERE status='candidate'").fetchall():
        if spl == 1 or s0 is None or s0 < 10:
            continue
        sel = select_contract(c, eid, "entry", t0, R, s0)
        if not sel:
            continue
        ok, v0, spread0 = screen(sel[2], sel[3])
        if not ok:
            continue
        e, k = sel[0], sel[1]
        h0 = spread0 / 2
        ex = {typ: (b, a) for typ, b, a in c.execute(
            "SELECT option_type, bid, ask FROM option_quotes WHERE event_id=? AND kind='exit' AND strike=? AND exp_date=?",
            (eid, k, e)) if b is not None and a is not None and a >= b}
        if "call" in ex and "put" in ex:
            vR = (sum(ex["call"]) + sum(ex["put"])) / 2
            hR = ((ex["call"][1] - ex["call"][0]) + (ex["put"][1] - ex["put"][0])) / 2
            fb = 0
        else:                                   # study fallback: intrinsic on the raw R close, h_exit = h_entry
            sR = c.execute("SELECT raw FROM closes WHERE ticker=? AND d=?", (t, R)).fetchone()
            if sR is None:
                continue
            vR, hR, fb = abs(sR[0] - k), h0, 1
        S = avgea4 - v0 / s0
        week = date.fromisoformat(R).isocalendar()[:2]
        rows.append((eid, week, S, vR / v0 - 1, ((vR - .5 * hR) - (v0 + .5 * h0)) / (v0 + .5 * h0),
                     ((vR - 1.0 * hR) - (v0 + 1.0 * h0)) / (v0 + 1.0 * h0), fb))
    return rows


# --- statistics ---
def spearman(x, y):
    return stats.spearmanr(x, y)[0]


def blocks(weeks):
    out = {}
    for i, w in enumerate(weeks):
        out.setdefault(w, []).append(i)
    return [np.array(v) for v in out.values()]


def perm_p(S, r, blk, seed):
    rng, obs, cnt = np.random.default_rng(seed), spearman(S, r), 0
    for _ in range(N_RES):
        Sp = S.copy()
        for b in blk:
            Sp[b] = S[rng.permutation(b)]
        cnt += spearman(Sp, r) >= obs
    return cnt / N_RES


def week_boot(blk, stat, seed):
    rng, vals = np.random.default_rng(seed), []
    for _ in range(N_RES):
        idx = np.concatenate([blk[j] for j in rng.integers(0, len(blk), len(blk))])
        vals.append(stat(idx))
    return np.percentile(vals, [2.5, 97.5])


def top_quintile(S, blk):
    top = np.zeros(len(S), bool)                # per ISO week: within-week percentile rank > 0.8
    for b in blk:
        rk = stats.rankdata(S[b], method="ordinal") / len(b)
        top[b[rk > 0.8]] = True
    return top


def analyze(rows):
    S = np.array([r[2] for r in rows]); rmid = np.array([r[3] for r in rows])
    n05 = np.array([r[4] for r in rows]); n10 = np.array([r[5] for r in rows])
    blk = blocks([r[1] for r in rows]); top = top_quintile(S, blk)
    rho = spearman(S, rmid)
    out = {"n_events": len(rows), "fallback_used": int(sum(r[6] for r in rows)), "n_weeks": len(blk),
           "n_top_quintile": int(top.sum()), "rho": rho,
           "rho_ci95": week_boot(blk, lambda i: spearman(S[i], rmid[i]), 42),
           "p_one_sided": {s: perm_p(S, rmid, blk, s) for s in SEEDS}}
    for lab, v in (("c0.5", n05), ("c1.0", n10)):
        out[f"top_mean_{lab}"] = v[top].mean()
        out[f"top_ci95_{lab}"] = week_boot(blk, lambda i: v[i][top[i]].mean() if top[i].any() else np.nan, 42)
        out[f"all_mean_{lab}"] = v.mean()
        out[f"all_ci95_{lab}"] = week_boot(blk, lambda i: v[i].mean(), 42)
    return out


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        global_rng = np.random.default_rng(7)
        n = 1200; weeks = [(2024, w % 60) for w in range(n)]
        S = global_rng.normal(size=n); r = 0.3 * S + global_rng.normal(size=n)
        rows = [(i, weeks[i], S[i], r[i], r[i] - .05, r[i] - .1, 0) for i in range(n)]
        N_RES = 300
        o = analyze(rows)
        print("SELFTEST (planted positive effect):", {k: (np.round(v, 3) if not isinstance(v, dict) else v) for k, v in o.items()})
    else:
        o = analyze(load())
        print("EXPLORATORY, 20% POWER, NOT A VERDICT")
        for k, v in o.items():
            print(k, np.round(v, 4) if not isinstance(v, dict) else {s: round(p, 4) for s, p in v.items()})

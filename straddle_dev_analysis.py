"""
DEV-window pipeline validation for the cross-sectional straddle hypothesis (CLAUDE.md Section 62).

*** PIPELINE VALIDATION, NOT EVIDENCE. *** It checks that the pipeline reproduces the DIRECTION of a
published result (Goyal & Saretto 2009) on the development window, and measures return noise for a power
analysis. It is not a test of the hypothesis, decides nothing, and touches no BLIND-window data.

Reads straddle_backtest.db:trades (written by straddle_backtester.run('dev')).
Portfolio per cycle: eligible names only; rank on signal = HV - IV; quintiles if >= 25 names, else
terciles; cycles with < 6 eligible names are skipped. Equal weight within each group.
Writes straddle_dev_analysis_results.json and prints a summary.
"""
import json, math, os, random, sqlite3
from collections import defaultdict
from statistics import mean, stdev

import straddle_backtester as sb

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "straddle_dev_analysis_results.json")
Z_A, Z_B = 1.645, 0.842         # one-sided alpha 0.05, power 0.80


def load():
    c = sqlite3.connect(sb.OUT_DB); c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute("SELECT * FROM trades WHERE window='dev'")]
    c.close()
    assert all(r["window"] == "dev" for r in rows)
    return rows


def by_cycle(rows):
    g = defaultdict(list)
    for r in rows:
        if r["excluded"] is None and r.get("eligible") == 1 and r.get("signal") is not None \
                and r.get("long_exp_f000") is not None:
            g[r["entry"]].append(r)
    return {k: v for k, v in sorted(g.items()) if len(v) >= 6}


def split(names, key="signal"):
    s = sorted(names, key=lambda r: r[key])
    k = len(s) // sb.group_sizes(len(s))
    return s[-k:], s[:k]          # top (highest HV-IV -> long), bottom (short)


def series(cycles, long_col, short_col, combine, key="signal"):
    """Per-cycle return of long-top + short-bottom.
    combine='sum': Goyal-Saretto spread (long-top return + short-bottom return; at mid = top - bottom).
    combine='avg': implementable book with capital split equally between the two legs."""
    out = []
    for names in cycles.values():
        top, bot = split(names, key)
        lt = [r[long_col] for r in top if r.get(long_col) is not None]
        st = [r[short_col] for r in bot if r.get(short_col) is not None]
        if lt and st:
            out.append(mean(lt) + mean(st) if combine == "sum" else (mean(lt) + mean(st)) / 2)
    return out


def stats(xs):
    if len(xs) < 2:
        return {"n": len(xs)}
    m, s = mean(xs), stdev(xs)
    return {"n": len(xs), "mean": m, "sd": s, "t": m / (s / math.sqrt(len(xs))) if s else None}


def placebo(cycles, reps=1000, seed=42):
    rng = random.Random(seed)
    real = mean(gs_mid(cycles))
    hits = 0
    for _ in range(reps):
        shuffled = {}
        for k, names in cycles.items():
            sig = [r["signal"] for r in names]
            rng.shuffle(sig)
            shuffled[k] = [dict(r, signal=s) for r, s in zip(names, sig)]
        if mean(gs_mid(shuffled)) >= real:
            hits += 1
    return {"real_mean": real, "p_one_sided": (hits + 1) / (reps + 1), "reps": reps}


def gs_mid(cycles):
    """Goyal-Saretto straddle basis at mid: top-group straddle return minus bottom-group straddle return."""
    out = []
    for names in cycles.values():
        top, bot = split(names)
        out.append(mean(r["long_exp_f000"] for r in top) - mean(r["long_exp_f000"] for r in bot))
    return out


def ticker_fe(cycles):
    """Two-way (cycle and ticker) demeaned correlation of signal with straddle return at mid."""
    rows = [r for names in cycles.values() for r in names]
    y = [r["long_exp_f000"] for r in rows]; x = [r["signal"] for r in rows]
    for _ in range(50):
        for key in ("entry", "ticker"):
            for vec in (y, x):
                grp = defaultdict(list)
                for i, r in enumerate(rows):
                    grp[r[key]].append(vec[i])
                means = {k: mean(v) for k, v in grp.items()}
                for i, r in enumerate(rows):
                    vec[i] -= means[r[key]]
    raw_x = [r["signal"] for r in rows]; raw_y = [r["long_exp_f000"] for r in rows]
    return {"n_rows": len(rows), "corr_raw": corr(raw_x, raw_y), "corr_two_way_demeaned": corr(x, y),
            "n_tickers": len({r["ticker"] for r in rows})}


def corr(a, b):
    ma, mb = mean(a), mean(b)
    num = sum((p - ma) * (q - mb) for p, q in zip(a, b))
    den = math.sqrt(sum((p - ma) ** 2 for p in a) * sum((q - mb) ** 2 for q in b))
    return num / den if den else None


def power(sd, n_avail):
    need = {f"{int(mu * 100)}pct_per_cycle": math.ceil(((Z_A + Z_B) * sd / mu) ** 2) for mu in (0.01, 0.02, 0.03, 0.05)}
    mde = {f"n={n}": (Z_A + Z_B) * sd / math.sqrt(n) for n in n_avail}
    return {"cycles_needed_for_80pct_power": need, "min_detectable_mean_per_cycle": mde}


def main():
    rows = load()
    cyc = by_cycle(rows)
    elig_counts = [len(v) for v in cyc.values()]
    res = {"LABEL": "PIPELINE VALIDATION ON THE DEV WINDOW -- NOT EVIDENCE, NOT A TEST",
           "ticker_cycles": len(rows), "evaluated": sum(r["excluded"] is None for r in rows),
           "exclusions": {k: sum(r["excluded"] == k for r in rows) for k in {r["excluded"] for r in rows} if k},
           "cycles_used": len(cyc), "eligible_names_per_cycle": {"min": min(elig_counts, default=0),
           "median": sorted(elig_counts)[len(elig_counts) // 2] if elig_counts else 0, "max": max(elig_counts, default=0)},
           "eligible_tickers": sorted({r["ticker"] for v in cyc.values() for r in v})}
    res["gs_straddle_basis"] = {f: stats(series(cyc, f"long_exp_{f}", f"shortstrad_exp_{f}", "sum")) for f in ("f000", "f050", "f100")}
    res["gs_mid_top_minus_bottom"] = stats(gs_mid(cyc))
    res["implementable_long_straddle_plus_iron_fly"] = {f: stats(series(cyc, f"long_exp_{f}", f"fly_exp_{f}", "avg")) for f in ("f000", "f050", "f100")}
    res["long_leg_only"] = {f: stats([mean(r[f"long_exp_{f}"] for r in split(v)[0]) for v in cyc.values()]) for f in ("f000", "f100")}
    res["short_leg_iron_fly_only"] = {f: stats([mean(x) for v in cyc.values()
                                               if (x := [r[f"fly_exp_{f}"] for r in split(v)[1] if r.get(f"fly_exp_{f}") is not None])])
                                      for f in ("f000", "f100")}
    res["implementable_day_before_exit_long_only"] = {f: stats([mean(r[f"long_db_{f}"] for r in split(v)[0] if r.get(f"long_db_{f}") is not None)
                                                               for v in cyc.values()]) for f in ("f000", "f100")}
    res["long_top_hedged_f100"] = stats([mean(r["long_exp_hedged_f100"] for r in split(v)[0]) for v in cyc.values()])
    res["secondary_term_slope"] = "not computed in this pass (needs near/far ATM IV; secondary, robustness only)"
    res["placebo_within_cycle_shuffle"] = placebo(cyc)
    res["ticker_fixed_effects"] = ticker_fe(cyc)
    e = defaultdict(list)
    for v in cyc.values():
        for r in v:
            e[str(r["earnings_in_window"])].append(r["long_exp_f000"])
    res["mean_straddle_return_mid_by_earnings_flag"] = {k: stats(v) for k, v in e.items()}
    main_sd = res["implementable_long_straddle_plus_iron_fly"]["f100"].get("sd")
    if main_sd:
        res["power_implementable_f100"] = power(main_sd, (len(cyc), 36, 192))
    gs_sd = res["gs_straddle_basis"]["f100"].get("sd")
    if gs_sd:
        res["power_gs_straddle_basis_f100"] = power(gs_sd, (len(cyc), 36, 192))
    with open(OUT, "w") as f:
        json.dump(res, f, indent=2, default=float)
    print(json.dumps(res, indent=2, default=float))


if __name__ == "__main__":
    main()

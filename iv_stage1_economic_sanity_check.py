"""
IV term-structure Stage 1 -- ECONOMIC SANITY CHECK (2026-10-01). EXPLORATORY / DESCRIPTIVE ONLY.

NOT a pre-registered test and NOT a re-test of iv_term_structure_slope_v2_20261001. It does not touch
the pre-registration files, the registry, or any Stage 2 date (>= 2026-09-10): every date used here is
before 2026-09-10. No EODHD calls are made; it reads only local databases.

Question: could a signal of IV Stage 1's size (slope vs 20-day forward realized vol, r ~ -0.28) pay for
real bid/ask costs on a tradeable volatility position (straddle / variance-style)?

Two parts:
 (a) EDGE. A straddle (or variance swap) pays the gap between realized and implied vol, not realized vol
     itself. So the question is whether the slope predicts (RV - IV), not RV. Data: xgboost_volatility_
     dataset.db (6 tickers, 2023-10-30..2026-07-21, the same near/far slope construction). Proxy for
     delta-hedged straddle return on premium: (RV20 - IV) / IV, with IV = far_iv (30-45 DTE, the horizon
     closest to 20 trading days).
 (b) COST. Real EODHD end-of-day bid/ask for ATM straddles, from gex_data_cache.db raw_records,
     2026-06-10..2026-09-09 (the only historical chains stored locally; Stage 1's own window,
     2026-01-15..06-10, has no stored bid/ask). Round trip = one full relative spread of the straddle
     (buy at ask, sell at bid); hold to expiry = half of that.
"""
import json, os, sqlite3, sys
from collections import defaultdict
from datetime import date
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
STAGE1 = ("2026-01-15", "2026-06-10")
SPREAD_WINDOW = ("2026-06-10", "2026-09-09")   # strictly before Stage 2's 2026-09-10 start
OUT = os.path.join(ROOT, "iv_stage1_economic_sanity_check_results.json")
rng = np.random.default_rng(42)


def block_bootstrap_mean(dates, values, block=20, reps=2000):
    """CI for a pooled mean, resampling blocks of consecutive trading dates (overlapping 20d targets)."""
    ud = sorted(set(dates))
    by = defaultdict(list)
    for d, v in zip(dates, values):
        by[d].append(v)
    nb = max(1, len(ud) // block)
    starts = np.arange(0, max(1, len(ud) - block + 1))
    out = []
    for _ in range(reps):
        vals = []
        for s in rng.choice(starts, nb):
            for d in ud[s:s + block]:
                vals.extend(by[d])
        out.append(np.mean(vals) if vals else np.nan)
    return float(np.nanpercentile(out, 2.5)), float(np.nanpercentile(out, 97.5))


# ---------------------------------------------------------------- (a) edge
def load_edge_rows():
    c = sqlite3.connect(os.path.join(ROOT, "xgboost_volatility_dataset.db"))
    rows = c.execute(
        "SELECT ticker, obs_date, term_structure_slope_pct, near_iv, far_iv, near_strike, spot_price, "
        "trailing_realized_vol_20d, target_realized_vol_20d FROM volatility_training_examples "
        "WHERE obs_date < '2026-09-10' AND target_realized_vol_20d IS NOT NULL AND far_iv > 0 AND near_iv > 0"
    ).fetchall()
    c.close()
    return rows


def edge_block(rows, label):
    t, d, slope, niv, fiv, k, s, trv, rv = map(np.array, zip(*rows))
    slope = slope.astype(float); fiv = fiv.astype(float); niv = niv.astype(float)
    rv = rv.astype(float); trv = trv.astype(float)
    ret = (rv - fiv) / fiv                      # long delta-hedged straddle, return on premium (proxy)
    res = {"label": label, "n_rows": len(rows), "n_days": len(set(d)),
           "corr_slope_rv20": float(np.corrcoef(slope, rv)[0, 1]),
           "corr_slope_rv_minus_iv_over_iv": float(np.corrcoef(slope, ret)[0, 1]),
           "corr_slope_far_iv": float(np.corrcoef(slope, fiv)[0, 1]),
           "median_abs_moneyness_of_matched_strike": float(np.median(np.abs(k.astype(float) / s.astype(float) - 1))),
           "unconditional_long_straddle_return_mean": float(ret.mean()),
           "unconditional_long_straddle_return_ci95": block_bootstrap_mean(list(d), list(ret))}
    # partial: does slope predict RV once the IV level (far_iv) and trailing RV are known?
    X = np.column_stack([np.ones(len(rv)), fiv, trv])
    r_rv = rv - X @ np.linalg.lstsq(X, rv, rcond=None)[0]
    r_sl = slope - X @ np.linalg.lstsq(X, slope, rcond=None)[0]
    res["partial_corr_slope_rv20_given_far_iv_and_trailing_rv"] = float(np.corrcoef(r_sl, r_rv)[0, 1])
    qs = np.quantile(slope, [0.2, 0.4, 0.6, 0.8])
    q = np.searchsorted(qs, slope)               # 0 = most inverted ... 4 = steepest contango
    res["quintiles"] = []
    for i in range(5):
        m = q == i
        res["quintiles"].append({
            "quintile": i + 1, "slope_range": [float(slope[m].min()), float(slope[m].max())], "n": int(m.sum()),
            "mean_rv20": float(rv[m].mean()), "mean_far_iv": float(fiv[m].mean()),
            "mean_long_straddle_return": float(ret[m].mean()),
            "ci95": block_bootstrap_mean(list(d[m]), list(ret[m]))})
    # signal strategy: long straddle in Q1 (inverted -> high RV predicted), short in Q5 (contango).
    # Balanced long/short (equal counts), so the unconditional vol premium cancels: this is the signal's part.
    strat = np.where(q == 0, ret, np.where(q == 4, -ret, np.nan))
    keep = ~np.isnan(strat)
    res["signal_strategy_gross_mean_return"] = float(strat[keep].mean())
    res["signal_strategy_gross_ci95"] = block_bootstrap_mean(list(d[keep]), list(strat[keep]))
    # net with each ticker's own median round-trip straddle spread (measured in the spread window)
    if SPREAD_BY_TICKER:
        cost = np.array([SPREAD_BY_TICKER.get(x, np.nan) for x in t])
        net = strat - cost
        res["signal_strategy_net_round_trip_per_ticker_cost"] = float(np.nanmean(net[keep]))
        res["signal_strategy_net_hold_to_expiry_per_ticker_cost"] = float(np.nanmean((strat + cost / 2)[keep] - cost[keep]))
        res["signal_strategy_net_round_trip_ci95"] = block_bootstrap_mean(list(d[keep]), list(net[keep]))
    # rank / outlier-robust versions (slope has extreme near-expiry values in the full history)
    from scipy.stats import spearmanr
    res["spearman_slope_rv20"] = float(spearmanr(slope, rv)[0])
    res["spearman_slope_rv_minus_iv_over_iv"] = float(spearmanr(slope, ret)[0])
    lo, hi = np.percentile(slope, [1, 99])
    w = np.clip(slope, lo, hi)
    res["pearson_winsorized_1_99_slope_rv20"] = float(np.corrcoef(w, rv)[0, 1])
    # break-even: correlation with the straddle return needed for the Q1/Q5 trade to cover the median cost
    sd = float(ret.std())
    tail_z = 1.40   # mean |z| in the top/bottom normal quintile
    res["sd_long_straddle_return"] = sd
    res["breakeven_corr_with_straddle_return_round_trip"] = COST_RT / (tail_z * sd) if COST_RT else None
    res["breakeven_corr_with_straddle_return_hold_to_expiry"] = COST_RT / 2 / (tail_z * sd) if COST_RT else None
    return res


SPREAD_BY_TICKER = {}
COST_RT = None


# ---------------------------------------------------------------- (b) cost
def load_spreads():
    c = sqlite3.connect(os.path.join(ROOT, "gex_data_cache.db"))
    spot = {(t, d): s for t, d, s in c.execute(
        "SELECT ticker, snapshot_date, spot_price FROM gex_metrics WHERE sign_convention='model_a'")}
    chains = defaultdict(lambda: defaultdict(dict))   # (t,d) -> exp -> {(strike,type): rec}
    q = ("SELECT ticker, requested_date, raw_json FROM raw_records WHERE matches_requested_date=1 "
         f"AND requested_date BETWEEN ? AND ? AND ticker IN ({','.join('?' * len(TICKERS))})")
    for t, d, rj in c.execute(q, (*SPREAD_WINDOW, *TICKERS)):
        r = json.loads(rj)
        b, a = r.get("bid"), r.get("ask")
        if not b or not a or b <= 0 or a < b:
            continue
        chains[(t, d)][r["exp_date"]].setdefault((float(r["strike"]), r["type"]),
                                                 {"bid": b, "ask": a, "iv": r.get("volatility"), "dte": r.get("dte")})
    c.close()
    out = []
    for (t, d), exps in chains.items():
        S = spot.get((t, d))
        if not S:
            continue
        for bucket, lo, hi, target in (("near_7_16", 7, 16, 11), ("far_25_45", 25, 45, 30)):
            cands = []
            for e, legs in exps.items():
                dte = (date.fromisoformat(e) - date.fromisoformat(d)).days
                if lo <= dte <= hi:
                    cands.append((abs(dte - target), e, dte))
            if not cands:
                continue
            _, e, dte = min(cands)
            legs = exps[e]
            strikes = sorted({k for k, ty in legs if (k, "call") in legs and (k, "put") in legs}, key=lambda k: abs(k - S))
            if not strikes:
                continue
            k = strikes[0]
            cl, pu = legs[(k, "call")], legs[(k, "put")]
            mid = (cl["bid"] + cl["ask"] + pu["bid"] + pu["ask"]) / 2
            full = (cl["ask"] + pu["ask"] - cl["bid"] - pu["bid"]) / mid
            out.append({"ticker": t, "date": d, "bucket": bucket, "dte": dte, "strike": k, "spot": S,
                        "straddle_mid": mid, "full_rel_spread": full,
                        "atm_iv": np.nanmean([x for x in (cl["iv"], pu["iv"]) if x])})
    return out


def summarize_spreads(sp):
    res = {}
    for bucket in ("near_7_16", "far_25_45"):
        rows = [r for r in sp if r["bucket"] == bucket]
        per = {}
        for t in TICKERS:
            v = [r["full_rel_spread"] for r in rows if r["ticker"] == t]
            if v:
                per[t] = {"n_days": len(v), "median": float(np.median(v)), "mean": float(np.mean(v)),
                          "p90": float(np.percentile(v, 90))}
        allv = [r["full_rel_spread"] for r in rows]
        res[bucket] = {"pooled_median": float(np.median(allv)), "pooled_mean": float(np.mean(allv)),
                       "n": len(allv), "per_ticker": per}
    return res


def proxy_check(sp):
    """How well does the dataset's far_iv (median common strike, not ATM) track real ATM IV? Overlap dates."""
    c = sqlite3.connect(os.path.join(ROOT, "xgboost_volatility_dataset.db"))
    fiv = {(t, d): v for t, d, v in c.execute(
        "SELECT ticker, obs_date, far_iv FROM volatility_training_examples WHERE obs_date BETWEEN ? AND ?", SPREAD_WINDOW)}
    c.close()
    pairs = [(fiv[(r["ticker"], r["date"])], r["atm_iv"]) for r in sp
             if r["bucket"] == "far_25_45" and (r["ticker"], r["date"]) in fiv and r["atm_iv"] == r["atm_iv"]]
    if len(pairs) < 10:
        return {"n": len(pairs)}
    a, b = map(np.array, zip(*pairs))
    return {"n": len(pairs), "corr": float(np.corrcoef(a, b)[0, 1]), "median_ratio_far_iv_over_atm_iv": float(np.median(a / b))}


def main():
    global COST_RT
    results = {}
    sp = load_spreads()
    results["spreads"] = summarize_spreads(sp)
    results["far_iv_proxy_vs_real_atm_iv"] = proxy_check(sp)
    for tk, v in results["spreads"]["far_25_45"]["per_ticker"].items():
        SPREAD_BY_TICKER[tk] = v["median"]
    COST_RT = results["spreads"]["far_25_45"]["pooled_median"]
    results["cost_assumptions"] = {"round_trip_full_spread": COST_RT, "hold_to_expiry_half_spread": COST_RT / 2,
                                   "per_ticker_round_trip_median": dict(SPREAD_BY_TICKER)}
    rows = load_edge_rows()
    periods = {"edge_stage1_window": (f"Stage 1 window {STAGE1}", STAGE1),
               "edge_pre_stage1": ("2023-10-30..2026-01-14 (before Stage 1; never used by it)", ("2023-10-30", "2026-01-14")),
               "edge_post_stage1_pre_stage2": ("2026-06-11..2026-07-21", ("2026-06-11", "2026-07-21")),
               "edge_full_history": ("2023-10-30..2026-07-21 (all pre-Stage-2)", ("0000", "2026-09-09"))}
    for key, (label, (a, b)) in periods.items():
        results[key] = edge_block([r for r in rows if a <= r[1] <= b], label)
    for k in periods:
        g = results[k]["signal_strategy_gross_mean_return"]
        results[k]["net_after_round_trip_pooled_cost"] = g - COST_RT
        results[k]["net_after_hold_to_expiry_pooled_cost"] = g - COST_RT / 2
    with open(OUT, "w") as f:
        json.dump(results, f, indent=2, default=float)
    print(json.dumps(results, indent=2, default=float))


if __name__ == "__main__":
    main()

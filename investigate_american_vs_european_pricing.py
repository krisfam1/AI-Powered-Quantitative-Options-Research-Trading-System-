from dotenv import load_dotenv
load_dotenv()

"""
DIAGNOSTIC INVESTIGATION, not a pre-registered experiment -- no config
hash, no VALIDATED/REJECTED decision rule, same category as the
Contract-Identity Investigation. Purpose: verify whether this project's
pricing chain (options_pricing.py:black_scholes_price(), used throughout
V1/V2/every correction script/every live bot/every ML feature set --
confirmed by exhaustive grep, zero exceptions found) treats options as
European (correct) and, if so, quantify what that's actually costing in
accuracy for the real calls-only population this project trades.

STEP 1 FINDING, already confirmed by direct code read + exhaustive grep
before writing this script (not assumed): options_pricing.py's
black_scholes_price() is the plain closed-form European formula -- no
early-exercise boundary, no dividend term at all. Grepped the entire
codebase for binomial/barone/adesi/bjerksund/whaley/longstaff/
early_exercise -- ZERO hits anywhere. Every one of the 78+ files that
call black_scholes_price() (or call it indirectly via
options_backtest_engine.py's re-export) get the same European-only price.

THEORETICAL PRIOR, stated honestly before simulating anything: this
project's traded population is CALLS ONLY (fixed_direction="call"
throughout V1/V2). A rigorous, well-known result in options theory: an
American call on a NON-DIVIDEND-PAYING underlying is priced IDENTICALLY
to the European call (early exercise is never optimal with no dividend to
capture). Since black_scholes_price() has no dividend term at all, and
5 of this project's 6 tickers (TSLA/AMD/SMCI/MSTR historically, NVDA's
dividend is negligible) pay no meaningful dividend, the a priori
expectation is a near-zero gap under the project's OWN assumptions. This
is tested empirically below, not just asserted -- and separately tested
under REALISTIC real-world dividend yields (disclosed as an EXTERNAL
assumption, since this project has zero dividend data anywhere in its own
pipeline) to see whether that materially changes the picture.

DATA: reuses the REAL, already-validated 2,599-row trade population from
the closed XGBoost-interaction experiment (ml_xgboost_interaction_data.db)
-- real tickers, real entry dates, real strikes, real historical EODHD IV
(v2_iv_pricing_model.py's methodology), real DTE (constant 14 across all
2,599 rows, confirmed directly). Zero new data collection, zero synthetic
inputs. This is the SAME real trade population every other correctness
check in this project's V1/V2 chain has used.
"""

import json
import sqlite3
import warnings
from datetime import datetime

import numpy as np

from options_pricing import black_scholes_price

warnings.filterwarnings("ignore")

DB_PATH = "ml_xgboost_interaction_data.db"
RISK_FREE_RATE = 0.04  # matches this project's own black_scholes_price default, used throughout V1/V2
DTE = 14  # confirmed constant across all 2,599 rows

# Approximate REAL historical annual dividend yields, 2023-2026 -- EXTERNAL,
# publicly-known approximations, NOT sourced from this project's own data
# pipeline (which has zero dividend data anywhere). Disclosed explicitly as
# such, not presented as project-internal ground truth.
REAL_DIVIDEND_YIELDS = {
    "AAPL": 0.0045,  # ~0.4-0.5%/year, the one real dividend payer in this universe
    "TSLA": 0.0,
    "NVDA": 0.0003,  # tiny, near-negligible historical dividend
    "AMD": 0.0,
    "SMCI": 0.0,
    "MSTR": 0.0,
}


def log(msg: str) -> None:
    print(msg, flush=True)


def lsm_american_price(S0, K, dte_days, sigma, r=RISK_FREE_RATE, q=0.0, option_type="call",
                        n_paths=10000, n_steps=14, seed=42):
    """Longstaff-Schwartz least-squares Monte Carlo American option pricer.
    Uses calendar-day/365 convention, matching this project's own
    black_scholes_price() exactly, for apples-to-apples comparability.
    Antithetic variates for variance reduction. Basis functions: [1, x, x^2]
    where x = S/K (moneyness), a standard, numerically stable LSM basis for
    short-dated, near-the-money contracts (this population's actual shape).
    """
    rng = np.random.RandomState(seed)
    T = dte_days / 365.0
    dt = T / n_steps
    half = n_paths // 2

    Z = rng.standard_normal((half, n_steps))
    Z = np.vstack([Z, -Z])  # antithetic pairs
    drift = (r - q - 0.5 * sigma ** 2) * dt
    diffusion = sigma * np.sqrt(dt) * Z
    log_paths = np.cumsum(drift + diffusion, axis=1)
    S = S0 * np.exp(log_paths)  # shape (n_paths, n_steps), S[:, -1] = maturity

    if option_type == "call":
        payoff = lambda s: np.maximum(s - K, 0.0)
    else:
        payoff = lambda s: np.maximum(K - s, 0.0)

    discount_per_step = np.exp(-r * dt)
    cash_flow = payoff(S[:, -1])  # cash flow if held to maturity

    for t in range(n_steps - 2, -1, -1):
        St = S[:, t]
        exercise_value = payoff(St)
        itm = exercise_value > 0
        if np.sum(itm) < 10:
            cash_flow = cash_flow * discount_per_step
            continue
        discounted_future = cash_flow[itm] * discount_per_step
        x = St[itm] / K
        A = np.vstack([np.ones_like(x), x, x ** 2]).T
        coeffs, *_ = np.linalg.lstsq(A, discounted_future, rcond=None)
        continuation_est = A @ coeffs

        exercise_now = exercise_value[itm] > continuation_est
        idx_itm = np.where(itm)[0]
        idx_exercise = idx_itm[exercise_now]

        cash_flow = cash_flow * discount_per_step
        cash_flow[idx_exercise] = exercise_value[itm][exercise_now]

    price = float(np.mean(cash_flow))
    stderr = float(np.std(cash_flow) / np.sqrt(n_paths))
    return price, stderr


def main():
    report = {}

    # =========================================================================
    # VALIDATION: confirm the LSM implementation is doing real work, not a no-op
    # =========================================================================
    log("=" * 100)
    log("VALIDATION -- before trusting the LSM pricer on real data")
    log("=" * 100)

    S0, K, sigma = 100.0, 105.0, 0.30
    bs_call = black_scholes_price(S0, K, DTE, sigma, RISK_FREE_RATE, "call")
    lsm_call_q0, se_call = lsm_american_price(S0, K, DTE, sigma, q=0.0, option_type="call", n_paths=40000)
    log(f"Test 1 (American CALL, q=0, should ~= European BS call, no early-exercise value expected):")
    log(f"  BS European call:  {bs_call:.4f}")
    log(f"  LSM American call:  {lsm_call_q0:.4f} (se={se_call:.4f})")
    log(f"  Relative diff: {abs(lsm_call_q0-bs_call)/bs_call*100:.3f}%  -- PASS if small (<2-3%, MC noise)" )

    bs_put = black_scholes_price(S0, K, DTE, sigma, RISK_FREE_RATE, "put")
    lsm_put_q0, se_put = lsm_american_price(S0, K, DTE, sigma, q=0.0, option_type="put", n_paths=40000)
    log(f"\nTest 2 (American PUT, q=0, should show a REAL positive early-exercise premium):")
    log(f"  BS European put:   {bs_put:.4f}")
    log(f"  LSM American put:   {lsm_put_q0:.4f} (se={se_put:.4f})")
    log(f"  Premium: {lsm_put_q0-bs_put:+.4f} ({(lsm_put_q0-bs_put)/bs_put*100:+.2f}%) -- PASS if clearly positive, confirms the pricer does real work")

    report["validation"] = {
        "bs_call": bs_call, "lsm_call_q0": lsm_call_q0, "call_relative_diff_pct": abs(lsm_call_q0-bs_call)/bs_call*100,
        "bs_put": bs_put, "lsm_put_q0": lsm_put_q0, "put_premium_pct": (lsm_put_q0-bs_put)/bs_put*100,
    }

    # =========================================================================
    # MAIN INVESTIGATION: real trade population, calls only (matches V1's convention)
    # =========================================================================
    log("\n" + "=" * 100)
    log("MAIN INVESTIGATION: real 2,599-row trade population (ml_xgboost_interaction_data.db)")
    log("=" * 100)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT ticker, entry_date, real_iv, features_json FROM xgboost_training_examples").fetchall()
    conn.close()
    log(f"Loaded {len(rows)} real trades")

    results = []
    errors = 0
    for i, r in enumerate(rows):
        feats = json.loads(r["features_json"])
        ticker = r["ticker"]
        strike = feats["strike"]
        spot = feats["stock_price"]
        iv = r["real_iv"]
        moneyness = feats["moneyness"]

        try:
            bs_price = black_scholes_price(spot, strike, DTE, iv, RISK_FREE_RATE, "call")
            # BUGFIX 2026-09-25: n_paths=8000 (the original setting) produced a
            # systematic +2.4-2.9% upward bias, confirmed via a targeted
            # convergence check on 4 real trades across 8k/40k/150k/400k paths
            # -- the well-known LSM in-sample regression bias (the same path
            # set fits the continuation-value regression AND prices the
            # option). At 150k+ paths this shrinks to a small, stable
            # residual (-0.3% to -0.7%), consistent with the theoretical
            # zero-gap expectation for zero-dividend calls. Using 150,000
            # paths here, not the original 8,000.
            lsm_q0, _ = lsm_american_price(spot, strike, DTE, iv, q=0.0, option_type="call", n_paths=150000, seed=42 + i)
            q_real = REAL_DIVIDEND_YIELDS.get(ticker, 0.0)
            lsm_qreal, _ = lsm_american_price(spot, strike, DTE, iv, q=q_real, option_type="call", n_paths=150000, seed=42 + i)
        except Exception as exc:
            errors += 1
            continue

        results.append({
            "ticker": ticker, "entry_date": r["entry_date"], "strike": strike, "spot": spot, "iv": iv, "moneyness": moneyness,
            "bs_price": bs_price, "lsm_q0": lsm_q0, "lsm_qreal": lsm_qreal,
            "gap_q0_dollar": lsm_q0 - bs_price, "gap_q0_pct": (lsm_q0 - bs_price) / bs_price * 100 if bs_price > 0 else None,
            "gap_qreal_dollar": lsm_qreal - bs_price, "gap_qreal_pct": (lsm_qreal - bs_price) / bs_price * 100 if bs_price > 0 else None,
        })

        if (i + 1) % 500 == 0:
            log(f"  {i+1}/{len(rows)} processed...")

    log(f"\nProcessed {len(results)} trades ({errors} errors/skipped)")
    report["n_processed"] = len(results)
    report["n_errors"] = errors

    # ---- Overall distribution ----
    gap_q0_pct = np.array([r["gap_q0_pct"] for r in results if r["gap_q0_pct"] is not None])
    gap_qreal_pct = np.array([r["gap_qreal_pct"] for r in results if r["gap_qreal_pct"] is not None])
    gap_q0_dollar = np.array([r["gap_q0_dollar"] for r in results])
    gap_qreal_dollar = np.array([r["gap_qreal_dollar"] for r in results])

    log("\n--- OVERALL distribution: LSM American vs current BS European price ---")
    log(f"Zero-dividend (matches project's own assumption): mean={np.mean(gap_q0_pct):+.4f}% median={np.median(gap_q0_pct):+.4f}% "
        f"std={np.std(gap_q0_pct):.4f}% min={np.min(gap_q0_pct):+.4f}% max={np.max(gap_q0_pct):+.4f}% | mean $ = {np.mean(gap_q0_dollar):+.5f}")
    log(f"Realistic dividend (external assumption): mean={np.mean(gap_qreal_pct):+.4f}% median={np.median(gap_qreal_pct):+.4f}% "
        f"std={np.std(gap_qreal_pct):.4f}% min={np.min(gap_qreal_pct):+.4f}% max={np.max(gap_qreal_pct):+.4f}% | mean $ = {np.mean(gap_qreal_dollar):+.5f}")

    report["overall"] = {
        "q0_pct_mean": float(np.mean(gap_q0_pct)), "q0_pct_median": float(np.median(gap_q0_pct)), "q0_pct_std": float(np.std(gap_q0_pct)),
        "q0_pct_min": float(np.min(gap_q0_pct)), "q0_pct_max": float(np.max(gap_q0_pct)), "q0_dollar_mean": float(np.mean(gap_q0_dollar)),
        "qreal_pct_mean": float(np.mean(gap_qreal_pct)), "qreal_pct_median": float(np.median(gap_qreal_pct)), "qreal_pct_std": float(np.std(gap_qreal_pct)),
        "qreal_pct_min": float(np.min(gap_qreal_pct)), "qreal_pct_max": float(np.max(gap_qreal_pct)), "qreal_dollar_mean": float(np.mean(gap_qreal_dollar)),
    }

    # ---- By ticker ----
    log("\n--- By ticker (realistic-dividend case) ---")
    by_ticker = {}
    tickers = sorted(set(r["ticker"] for r in results))
    for t in tickers:
        sub = [r for r in results if r["ticker"] == t]
        pct_q0 = [r["gap_q0_pct"] for r in sub]
        pct_qreal = [r["gap_qreal_pct"] for r in sub]
        by_ticker[t] = {
            "n": len(sub), "dividend_yield_used": REAL_DIVIDEND_YIELDS.get(t, 0.0),
            "q0_mean_pct": float(np.mean(pct_q0)), "qreal_mean_pct": float(np.mean(pct_qreal)), "qreal_max_pct": float(np.max(pct_qreal)),
        }
        log(f"  {t}: n={len(sub)} div_yield={REAL_DIVIDEND_YIELDS.get(t,0.0)*100:.2f}%  q0_gap={by_ticker[t]['q0_mean_pct']:+.4f}%  "
            f"qreal_gap_mean={by_ticker[t]['qreal_mean_pct']:+.4f}%  qreal_gap_max={by_ticker[t]['qreal_max_pct']:+.4f}%")
    report["by_ticker"] = by_ticker

    # ---- By moneyness bucket ----
    log("\n--- By moneyness bucket (realistic-dividend case) ---")
    by_moneyness = {}
    moneyness_vals = np.array([r["moneyness"] for r in results])
    edges = np.percentile(moneyness_vals, [33.33, 66.67])
    labels = np.where(moneyness_vals <= edges[0], "low (deepest OTM)", np.where(moneyness_vals <= edges[1], "mid", "high (closest ATM)"))
    for label in ["low (deepest OTM)", "mid", "high (closest ATM)"]:
        idx = [i for i, l in enumerate(labels) if l == label]
        sub_pct = [results[i]["gap_qreal_pct"] for i in idx]
        by_moneyness[label] = {"n": len(idx), "mean_pct": float(np.mean(sub_pct)), "max_pct": float(np.max(sub_pct))}
        log(f"  {label}: n={len(idx)} mean_gap={by_moneyness[label]['mean_pct']:+.4f}% max_gap={by_moneyness[label]['max_pct']:+.4f}%")
    report["by_moneyness"] = by_moneyness

    # ---- Largest individual gaps found ----
    sorted_by_gap = sorted(results, key=lambda r: r["gap_qreal_pct"], reverse=True)
    log("\n--- Top 5 largest individual gaps found (realistic-dividend case) ---")
    top5 = []
    for r in sorted_by_gap[:5]:
        log(f"  {r['ticker']} {r['entry_date']}: BS={r['bs_price']:.4f} LSM(q_real)={r['lsm_qreal']:.4f} gap={r['gap_qreal_pct']:+.4f}% moneyness={r['moneyness']:.4f}")
        top5.append({k: r[k] for k in ["ticker", "entry_date", "bs_price", "lsm_qreal", "gap_qreal_pct", "moneyness"]})
    report["top5_gaps"] = top5

    with open("american_vs_european_pricing_investigation.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log("\nFull results written to american_vs_european_pricing_investigation.json")


if __name__ == "__main__":
    main()

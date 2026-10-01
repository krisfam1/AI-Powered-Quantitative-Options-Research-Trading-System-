from dotenv import load_dotenv
load_dotenv()

"""
Implements the 3 declared robustness checks for ML Experiment 1:
1. leave_one_ticker_out
2. alternate_horizon:10bar
3. alternate_horizon:5bar

Robustness criterion (explicit, consistent with the locked primary
test's own pass/fail definition): a check SURVIVES if its conclusion
direction matches the primary result. Since the primary result was
REJECTED (not significant AND effect size below threshold), each
check survives if it does NOT show a contradicting positive result
(p<=0.05 AND relative_mse_reduction>=10%) that would flip the
conclusion. This applies the SAME criteria already locked for the
primary test, just checking directional consistency under perturbation.
"""

import pickle
import numpy as np
from scipy import stats as scipy_stats
import backtest_engine as be
from ml_experiment1_executor import LOCKED_FEATURES, BASELINE_FEATURE, _fit_ridge_with_validation
from data_prep_experiment1 import chronological_split_with_purging, greedy_nonoverlapping_selection, TICKERS

EFFECT_THRESHOLD = 0.10
ALPHA = 0.05


def _encode_value(v):
    if isinstance(v, str):
        return {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}.get(v, 0.0)
    return float(v)


def _extract(rows, feature_names):
    X = np.array([[_encode_value(r[f]) for f in feature_names] for r in rows])
    y = np.array([r["target"] for r in rows])
    return X, y


def _run_comparison(train_rows, val_rows, primary_rows):
    """Reusable core: train both models, evaluate on primary_rows, return p-value + effect size."""
    Xa_train, y_train = _extract(train_rows, [BASELINE_FEATURE])
    Xa_val, y_val = _extract(val_rows, [BASELINE_FEATURE])
    model_a, _ = _fit_ridge_with_validation(Xa_train, y_train, Xa_val, y_val)

    Xb_train, _ = _extract(train_rows, LOCKED_FEATURES)
    Xb_val, _ = _extract(val_rows, LOCKED_FEATURES)
    model_b, _ = _fit_ridge_with_validation(Xb_train, y_train, Xb_val, y_val)

    Xa_p, y_p = _extract(primary_rows, [BASELINE_FEATURE])
    Xb_p, _ = _extract(primary_rows, LOCKED_FEATURES)
    err_a = (y_p - model_a.predict(Xa_p)) ** 2
    err_b = (y_p - model_b.predict(Xb_p)) ** 2

    diffs = err_a - err_b
    if len(diffs) >= 5 and not np.all(diffs == 0):
        _, p = scipy_stats.wilcoxon(diffs, alternative="greater")
    else:
        p = 1.0

    mse_a, mse_b = float(np.mean(err_a)), float(np.mean(err_b))
    rel_reduction = (mse_a - mse_b) / mse_a if mse_a != 0 else 0.0
    return p, rel_reduction, len(primary_rows)


def check_leave_one_ticker_out(dataset):
    """For each ticker, exclude it entirely and re-run the primary comparison."""
    results = {}
    for excl_ticker in TICKERS:
        train = [r for r in dataset["all_train"] if r["ticker"] != excl_ticker]
        val = [r for r in dataset["all_val"] if r["ticker"] != excl_ticker]
        primary = [r for r in dataset["primary_test_set"] if r["ticker"] != excl_ticker]
        if len(primary) < 5:
            results[excl_ticker] = {"skipped": True, "reason": "insufficient primary observations after exclusion"}
            continue
        p, rel_reduction, n = _run_comparison(train, val, primary)
        contradicts = (p <= ALPHA and rel_reduction >= EFFECT_THRESHOLD)
        results[excl_ticker] = {"p_value": p, "relative_mse_reduction": rel_reduction, "n": n, "contradicts_primary": contradicts}
    any_contradiction = any(r.get("contradicts_primary") for r in results.values() if not r.get("skipped"))
    return {"survived": not any_contradiction, "per_ticker": results}


def check_alternate_horizon(dataset, horizon):
    """Recomputes targets at an alternate horizon (bars re-fetched, features REUSED from persisted data)."""
    all_rows_by_key = {(r["ticker"], r["signal_index"]): r for r in dataset["all_complete_rows"]}

    new_rows_by_ticker = {}
    for ticker in TICKERS:
        ticker_rows = [r for r in dataset["all_complete_rows"] if r["ticker"] == ticker]
        if not ticker_rows:
            continue
        bars = be.get_historical_bars(ticker, __import__("datetime").datetime(2026,6,11,tzinfo=__import__("datetime").timezone.utc), __import__("datetime").datetime(2026,9,9,tzinfo=__import__("datetime").timezone.utc))
        new_rows = []
        for r in ticker_rows:
            idx = r["signal_index"]
            if idx + horizon >= len(bars):
                continue  # insufficient future bars at this horizon
            entry = float(bars[idx].close)
            exitp = float(bars[idx + horizon].close)
            new_target = (exitp - entry) / entry
            new_row = dict(r)
            new_row["target"] = new_target
            new_rows.append(new_row)
        new_rows_by_ticker[ticker] = new_rows

    all_new_rows = [r for rows in new_rows_by_ticker.values() for r in rows]
    train, val, test, _ = chronological_split_with_purging(all_new_rows, horizon=horizon)

    test_by_ticker = {}
    for r in test:
        test_by_ticker.setdefault(r["ticker"], []).append(r)
    primary = greedy_nonoverlapping_selection(test_by_ticker, horizon=horizon)

    if len(primary) < 5:
        return {"survived": None, "skipped": True, "reason": "insufficient primary observations at horizon=" + str(horizon)}

    p, rel_reduction, n = _run_comparison(train, val, primary)
    contradicts = (p <= ALPHA and rel_reduction >= EFFECT_THRESHOLD)
    return {"survived": not contradicts, "p_value": p, "relative_mse_reduction": rel_reduction, "n": n}


def run_all_robustness_checks():
    with open("ml_experiment1_dataset.pkl", "rb") as f:
        dataset = pickle.load(f)

    print("Running leave_one_ticker_out...")
    loto_result = check_leave_one_ticker_out(dataset)
    for ticker, r in loto_result["per_ticker"].items():
        if r.get("skipped"):
            print("  " + ticker + " excluded: SKIPPED (" + r["reason"] + ")")
        else:
            print("  " + ticker + " excluded: p=" + str(round(r["p_value"],4)) + " rel_reduction=" + str(round(r["relative_mse_reduction"]*100,2)) + "% contradicts=" + str(r["contradicts_primary"]))
    print("  leave_one_ticker_out SURVIVED: " + str(loto_result["survived"]))

    print("\nRunning alternate_horizon:10bar...")
    h10_result = check_alternate_horizon(dataset, 10)
    print("  Result: " + str(h10_result))

    print("\nRunning alternate_horizon:5bar...")
    h5_result = check_alternate_horizon(dataset, 5)
    print("  Result: " + str(h5_result))

    return {
        "leave_one_ticker_out": {"survived": loto_result["survived"], "description": "leave-one-ticker-out re-comparison"},
        "alternate_horizon:10bar": {"survived": bool(h10_result.get("survived")), "description": "10-bar forward-return horizon"},
        "alternate_horizon:5bar": {"survived": bool(h5_result.get("survived")), "description": "5-bar forward-return horizon"},
    }


if __name__ == "__main__":
    results = run_all_robustness_checks()
    print("\n" + "=" * 90)
    print("SUMMARY")
    print("=" * 90)
    for name, r in results.items():
        print(name + ": survived=" + str(r["survived"]))
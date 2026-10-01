from dotenv import load_dotenv
load_dotenv()

"""
Phase 4: frozen incremental-information experiment. Runs exactly as
locked in the Statistical Design Lock -- no methodology changes after
seeing results.

Structure: 51 total calendar-day observations (31 train, 20 holdout),
calendar-day is the primary independent unit. GEX values are constant
per (ticker, T-1 date) since they come from a single T-1 snapshot; only
forward returns vary across a ticker's same-day clusters, so those are
averaged within-ticker first, then across tickers, to get one
calendar-day observation per metric.

Continuous features: training-only tercile thresholds, frozen, applied
unchanged to holdout. Regime: majority (mode) across active tickers
that day; ties excluded as "mixed" (a real, small number, reported).

Primary test: Mann-Whitney U on the calendar-day observations, 20-bar
horizon. Bonferroni correction: alpha = 0.05/6 ~= 0.0083.
"""

import statistics
from scipy import stats
import backtest_engine as be
from backtest_engine import get_daily_regime
from entry_scorer import calculate_entry_score
from signal_validation_core import calculate_forward_stats, TICKERS
from gex_lookup import get_gex_for_signal
from datetime import datetime, timezone

TRAIN_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
TRAIN_END = datetime(2026, 8, 11, tzinfo=timezone.utc)
HOLDOUT_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
ALPHA_CORRECTED = 0.05 / 6

CONTINUOUS_FEATURES = ["net_gex_normalized", "gamma_flip_distance_pct", "call_wall_distance_pct", "put_wall_distance_pct", "gamma_gradient_at_spot"]
HORIZONS = ["return_5bar", "return_10bar", "return_20bar", "return_50bar"]


def collect_signals():
    all_signals = []
    for ticker in TICKERS:
        bars = be.get_historical_bars(ticker, TRAIN_START, HOLDOUT_END)
        if not bars:
            continue
        for index in range(60, len(bars)):
            if not be.check_breakout(bars, index, lookback=20):
                continue
            timestamp = bars[index].timestamp
            try:
                spy_regime = get_daily_regime("SPY", timestamp, period=50)
            except Exception:
                spy_regime = "neutral"
            if spy_regime != "bullish":
                continue
            try:
                score_result = calculate_entry_score(ticker, bars, index, "call", spy_regime=spy_regime)
            except Exception:
                continue
            if score_result["total_score"] < 20:
                continue
            fwd_stats = calculate_forward_stats(bars, index, "call")
            gex_result = get_gex_for_signal(ticker, timestamp)
            period = "train" if timestamp < TRAIN_END else "holdout"
            all_signals.append({
                "ticker": ticker, "index": index, "signal_date": timestamp.date().isoformat(),
                "period": period, **fwd_stats, "gex": gex_result,
            })
        print(ticker + ": collected")
    return all_signals


def build_calendar_day_observations(signals):
    """Returns one dict per calendar day: averaged returns (within-ticker then across-ticker), constant-per-ticker GEX values averaged across tickers, and majority regime."""
    with_gex = [s for s in signals if s["gex"]["available"]]

    by_date_ticker = {}
    for s in with_gex:
        by_date_ticker.setdefault(s["signal_date"], {}).setdefault(s["ticker"], []).append(s)

    observations = []
    for date, ticker_map in by_date_ticker.items():
        period = list(ticker_map.values())[0][0]["period"]
        ticker_level = {}
        for ticker, sigs in ticker_map.items():
            entry = {"ticker": ticker}
            for h in HORIZONS:
                vals = [s[h] for s in sigs if h in s]
                entry[h] = statistics.mean(vals) if vals else None
            gex = sigs[0]["gex"]
            for feat in CONTINUOUS_FEATURES:
                entry[feat] = gex.get(feat)
            entry["gex_regime"] = gex.get("gex_regime")
            ticker_level[ticker] = entry

        obs = {"date": date, "period": period, "n_tickers": len(ticker_level)}
        for h in HORIZONS:
            vals = [e[h] for e in ticker_level.values() if e[h] is not None]
            obs[h] = statistics.mean(vals) if vals else None
        for feat in CONTINUOUS_FEATURES:
            vals = [e[feat] for e in ticker_level.values() if e[feat] is not None]
            obs[feat] = statistics.mean(vals) if vals else None
        regimes = [e["gex_regime"] for e in ticker_level.values() if e["gex_regime"] in ("positive", "negative")]
        pos = regimes.count("positive")
        neg = regimes.count("negative")
        obs["majority_regime"] = "positive" if pos > neg else ("negative" if neg > pos else "mixed")
        obs["ticker_level"] = ticker_level
        observations.append(obs)

    return observations


def rank_biserial_effect_size(group_a, group_b):
    n1, n2 = len(group_a), len(group_b)
    if n1 == 0 or n2 == 0:
        return None
    u_stat, _ = stats.mannwhitneyu(group_a, group_b, alternative="two-sided")
    return round(1 - (2 * u_stat) / (n1 * n2), 3)


def test_feature(observations, feature_key, is_regime=False):
    train_obs = [o for o in observations if o["period"] == "train"]
    holdout_obs = [o for o in observations if o["period"] == "holdout"]

    if is_regime:
        train_strong = [o for o in train_obs if o["majority_regime"] == "positive"]
        train_weak = [o for o in train_obs if o["majority_regime"] == "negative"]
        holdout_strong = [o for o in holdout_obs if o["majority_regime"] == "positive"]
        holdout_weak = [o for o in holdout_obs if o["majority_regime"] == "negative"]
        threshold_info = "positive vs negative majority regime (no threshold needed, categorical)"
    else:
        train_vals = [o[feature_key] for o in train_obs if o.get(feature_key) is not None]
        if len(train_vals) < 6:
            return {"feature": feature_key, "classification": "NOT TESTABLE", "reason": "insufficient training data"}
        train_vals_sorted = sorted(train_vals)
        n = len(train_vals_sorted)
        low_cut = train_vals_sorted[n // 3]
        high_cut = train_vals_sorted[(2 * n) // 3]
        threshold_info = "train terciles: low_cut=" + str(round(low_cut, 4)) + " high_cut=" + str(round(high_cut, 4)) + " (frozen)"

        train_strong = [o for o in train_obs if o.get(feature_key) is not None and o[feature_key] >= high_cut]
        train_weak = [o for o in train_obs if o.get(feature_key) is not None and o[feature_key] <= low_cut]
        holdout_strong = [o for o in holdout_obs if o.get(feature_key) is not None and o[feature_key] >= high_cut]
        holdout_weak = [o for o in holdout_obs if o.get(feature_key) is not None and o[feature_key] <= low_cut]

    results = {"feature": feature_key, "threshold_info": threshold_info}
    results["train_n_strong"] = len(train_strong)
    results["train_n_weak"] = len(train_weak)
    results["holdout_n_strong"] = len(holdout_strong)
    results["holdout_n_weak"] = len(holdout_weak)

    for period_name, strong, weak in [("train", train_strong, train_weak), ("holdout", holdout_strong, holdout_weak)]:
        period_result = {}
        for horizon in HORIZONS:
            strong_vals = [o[horizon] for o in strong if o.get(horizon) is not None]
            weak_vals = [o[horizon] for o in weak if o.get(horizon) is not None]
            if len(strong_vals) < 2 or len(weak_vals) < 2:
                period_result[horizon] = {"insufficient_data": True}
                continue
            u_stat, p_val = stats.mannwhitneyu(strong_vals, weak_vals, alternative="two-sided")
            effect = rank_biserial_effect_size(strong_vals, weak_vals)
            period_result[horizon] = {
                "strong_mean": round(statistics.mean(strong_vals) * 100, 3),
                "weak_mean": round(statistics.mean(weak_vals) * 100, 3),
                "strong_median": round(statistics.median(strong_vals) * 100, 3),
                "weak_median": round(statistics.median(weak_vals) * 100, 3),
                "raw_p": round(p_val, 4),
                "corrected_p": round(min(p_val * 6, 1.0), 4),
                "effect_size_rank_biserial": effect,
                "direction": "positive" if statistics.mean(strong_vals) > statistics.mean(weak_vals) else "negative",
            }
        results[period_name] = period_result

    # Per-ticker descriptive breakdown (20-bar only, descriptive not independently tested)
    per_ticker = {}
    for ticker in TICKERS:
        strong_vals = []
        weak_vals = []
        for o in train_obs + holdout_obs:
            if ticker not in o["ticker_level"]:
                continue
            tl = o["ticker_level"][ticker]
            if is_regime:
                in_strong = o["majority_regime"] == "positive"
                in_weak = o["majority_regime"] == "negative"
            else:
                val = o.get(feature_key)
                in_strong = val is not None and val >= high_cut
                in_weak = val is not None and val <= low_cut
            if in_strong and tl.get("return_20bar") is not None:
                strong_vals.append(tl["return_20bar"])
            elif in_weak and tl.get("return_20bar") is not None:
                weak_vals.append(tl["return_20bar"])
        per_ticker[ticker] = {
            "n_strong": len(strong_vals), "n_weak": len(weak_vals),
            "strong_mean": round(statistics.mean(strong_vals) * 100, 3) if strong_vals else None,
            "weak_mean": round(statistics.mean(weak_vals) * 100, 3) if weak_vals else None,
        }
    results["per_ticker"] = per_ticker

    # Classification
    primary = results.get("train", {}).get("return_20bar", {})
    primary_holdout = results.get("holdout", {}).get("return_20bar", {})
    if primary.get("insufficient_data") or primary_holdout.get("insufficient_data"):
        results["classification"] = "NOT TESTABLE"
        results["classification_reason"] = "insufficient data in train or holdout at primary horizon"
    else:
        train_dir = primary.get("direction")
        holdout_dir = primary_holdout.get("direction")
        holdout_corrected_p = primary_holdout.get("corrected_p", 1.0)
        holdout_effect = abs(primary_holdout.get("effect_size_rank_biserial", 0) or 0)
        consistent_direction = train_dir == holdout_dir

        if not consistent_direction:
            results["classification"] = "C"
            results["classification_reason"] = "direction reverses between train and holdout"
        elif holdout_corrected_p < ALPHA_CORRECTED and holdout_effect > 0.3:
            results["classification"] = "A"
            results["classification_reason"] = "significant at corrected alpha, consistent direction, meaningful effect size"
        elif consistent_direction and holdout_effect > 0.2:
            results["classification"] = "B"
            results["classification_reason"] = "consistent direction, economically non-trivial effect, but does not reach corrected significance -- worth further investigation, not proof of absence of effect"
        else:
            results["classification"] = "C"
            results["classification_reason"] = "no detectable incremental value under this sample size and methodology"

    return results


if __name__ == "__main__":
    print("Collecting signals and building calendar-day observations...\n")
    signals = collect_signals()
    observations = build_calendar_day_observations(signals)
    print("\nTotal calendar-day observations: " + str(len(observations)))
    train_count = len([o for o in observations if o["period"] == "train"])
    holdout_count = len([o for o in observations if o["period"] == "holdout"])
    print("Train: " + str(train_count) + " | Holdout: " + str(holdout_count))

    print("\n" + "=" * 90)
    print("STATISTICAL LIMITATION -- STATED PROMINENTLY, PER INSTRUCTION")
    print("=" * 90)
    print("The primary analysis has only " + str(holdout_count) + " independent holdout calendar-day observations.")
    print("This gives limited power to detect modest effects. A non-significant result")
    print("therefore cannot establish that the underlying effect is absent.")

    all_results = {}

    print("\n" + "=" * 90)
    print("FEATURE 1: GEX REGIME")
    print("=" * 90)
    result = test_feature(observations, "gex_regime", is_regime=True)
    all_results["gex_regime"] = result
    print(result)

    for feature in CONTINUOUS_FEATURES:
        print("\n" + "=" * 90)
        print("FEATURE: " + feature)
        print("=" * 90)
        result = test_feature(observations, feature, is_regime=False)
        all_results[feature] = result
        print(result)

    print("\n" + "=" * 90)
    print("OVERALL CLASSIFICATION SUMMARY")
    print("=" * 90)
    for feat, res in all_results.items():
        print(feat + ": " + str(res.get("classification", "N/A")) + " -- " + str(res.get("classification_reason", "")))

    print("\nPHASE 4 COMPLETE -- STOPPING per instruction, awaiting review.")
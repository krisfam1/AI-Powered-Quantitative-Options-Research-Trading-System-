from dotenv import load_dotenv
load_dotenv()

"""
Regime aggregation sensitivity analysis -- PRE-SPECIFIED, per explicit
instruction. Does NOT replace or modify the archived Phase 4 results.

Design: for each calendar day, tickers are split by their OWN actual
T-1 regime (not majority vote). Only days where BOTH positive- and
negative-regime tickers are represented are used. Within each such day,
each ticker's clusters are first averaged into one ticker/day outcome
(equal weight per ticker, regardless of signal/cluster count), then the
positive-regime tickers' outcomes are averaged and the negative-regime
tickers' outcomes are averaged -- producing ONE PAIRED observation
(positive_avg, negative_avg) per qualifying calendar day.

This paired structure is tested with a Wilcoxon signed-rank test (the
paired analog of Mann-Whitney), which correctly treats each qualifying
calendar day as exactly one independent observation -- satisfying
"preserve calendar-day independence" without needing majority voting.

Same frozen baseline, same train/holdout boundary, same horizons as
Phase 4. No new features, no threshold optimization.
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


def build_paired_day_observations(signals):
    with_gex = [s for s in signals if s["gex"]["available"] and s["gex"].get("gex_regime") in ("positive", "negative")]

    by_date_ticker = {}
    for s in with_gex:
        by_date_ticker.setdefault(s["signal_date"], {}).setdefault(s["ticker"], []).append(s)

    paired_days = []
    participation_log = []

    for date, ticker_map in by_date_ticker.items():
        period = list(ticker_map.values())[0][0]["period"]
        pos_ticker_outcomes = {h: [] for h in HORIZONS}
        neg_ticker_outcomes = {h: [] for h in HORIZONS}
        pos_tickers = []
        neg_tickers = []

        for ticker, sigs in ticker_map.items():
            regime = sigs[0]["gex"]["gex_regime"]  # constant per ticker/day (single T-1 snapshot)
            ticker_outcome = {}
            for h in HORIZONS:
                vals = [s[h] for s in sigs if h in s and s[h] is not None]
                ticker_outcome[h] = statistics.mean(vals) if vals else None

            if regime == "positive":
                pos_tickers.append(ticker)
                for h in HORIZONS:
                    if ticker_outcome[h] is not None:
                        pos_ticker_outcomes[h].append(ticker_outcome[h])
            else:
                neg_tickers.append(ticker)
                for h in HORIZONS:
                    if ticker_outcome[h] is not None:
                        neg_ticker_outcomes[h].append(ticker_outcome[h])

        participation_log.append({"date": date, "period": period, "positive_tickers": pos_tickers, "negative_tickers": neg_tickers})

        if not pos_tickers or not neg_tickers:
            continue  # per instruction: only days with BOTH regimes represented

        day_obs = {"date": date, "period": period, "n_positive_tickers": len(pos_tickers), "n_negative_tickers": len(neg_tickers)}
        for h in HORIZONS:
            day_obs["positive_" + h] = statistics.mean(pos_ticker_outcomes[h]) if pos_ticker_outcomes[h] else None
            day_obs["negative_" + h] = statistics.mean(neg_ticker_outcomes[h]) if neg_ticker_outcomes[h] else None
        paired_days.append(day_obs)

    return paired_days, participation_log


def run_paired_test(paired_days, period_filter, horizon):
    subset = [d for d in paired_days if d["period"] == period_filter and d.get("positive_" + horizon) is not None and d.get("negative_" + horizon) is not None]
    if len(subset) < 3:
        return {"n": len(subset), "insufficient_data": True}

    pos_vals = [d["positive_" + horizon] for d in subset]
    neg_vals = [d["negative_" + horizon] for d in subset]
    diffs = [p - n for p, n in zip(pos_vals, neg_vals)]

    try:
        w_stat, p_val = stats.wilcoxon(pos_vals, neg_vals)
    except ValueError:
        w_stat, p_val = None, None

    return {
        "n": len(subset),
        "positive_mean": round(statistics.mean(pos_vals) * 100, 3),
        "negative_mean": round(statistics.mean(neg_vals) * 100, 3),
        "mean_diff": round(statistics.mean(diffs) * 100, 3),
        "wilcoxon_p": round(p_val, 4) if p_val is not None else None,
        "direction": "positive_higher" if statistics.mean(pos_vals) > statistics.mean(neg_vals) else "negative_higher",
    }


if __name__ == "__main__":
    print("Collecting signals and building paired within-day regime observations...\n")
    signals = collect_signals()
    paired_days, participation_log = build_paired_day_observations(signals)

    print("\n" + "=" * 90)
    print("PARTICIPATION LOG -- calendar days and regime representation")
    print("=" * 90)
    total_days = len(participation_log)
    qualifying_days = len(paired_days)
    print("Total calendar days with any regime-tagged signal: " + str(total_days))
    print("Days with BOTH positive and negative regime tickers (qualifying for primary comparison): " + str(qualifying_days))
    if qualifying_days == 0:
        print("\nNO QUALIFYING DAYS FOUND. Reporting this honestly -- cannot proceed with a primary comparison.")

    train_qualifying = [d for d in paired_days if d["period"] == "train"]
    holdout_qualifying = [d for d in paired_days if d["period"] == "holdout"]
    print("Train qualifying days: " + str(len(train_qualifying)))
    print("Holdout qualifying days: " + str(len(holdout_qualifying)))

    print("\nFull participation detail (all calendar days, not just qualifying):")
    for p in participation_log:
        print("  " + p["date"] + " (" + p["period"] + "): positive=" + str(p["positive_tickers"]) + " negative=" + str(p["negative_tickers"]))

    print("\n" + "=" * 90)
    print("PAIRED COMPARISON RESULTS (Wilcoxon signed-rank, primary horizon = 20 bars)")
    print("=" * 90)
    for period in ["train", "holdout"]:
        print("\n--- " + period.upper() + " ---")
        for horizon in HORIZONS:
            result = run_paired_test(paired_days, period, horizon)
            print("  " + horizon + ": " + str(result))

    print("\n" + "=" * 90)
    print("PER-TICKER PARTICIPATION SUMMARY")
    print("=" * 90)
    for ticker in TICKERS:
        pos_days = len([p for p in participation_log if ticker in p["positive_tickers"]])
        neg_days = len([p for p in participation_log if ticker in p["negative_tickers"]])
        print("  " + ticker + ": positive-regime days=" + str(pos_days) + " negative-regime days=" + str(neg_days))

    print("\n" + "=" * 90)
    print("DIRECTIONAL CONSISTENCY CHECK (20-bar, train vs holdout)")
    print("=" * 90)
    train_20 = run_paired_test(paired_days, "train", "return_20bar")
    holdout_20 = run_paired_test(paired_days, "holdout", "return_20bar")
    if train_20.get("insufficient_data") or holdout_20.get("insufficient_data"):
        print("Cannot assess directional consistency -- insufficient data in train and/or holdout at the primary horizon.")
    else:
        consistent = train_20["direction"] == holdout_20["direction"]
        print("Train direction: " + train_20["direction"] + " | Holdout direction: " + holdout_20["direction"])
        print("Directionally consistent: " + str(consistent))

    print("\n" + "=" * 90)
    print("INTERPRETATION NOTE (per explicit instruction)")
    print("=" * 90)
    print("This is a sensitivity analysis of the AGGREGATION METHOD, not a replacement for Phase 4.")
    print("A real effect here would indicate the original majority-vote aggregation suppressed real,")
    print("confirmed cross-sectional regime variation -- it would NOT independently prove GEX regime")
    print("is predictive. The original Phase 4 'NOT TESTABLE' classification for regime remains the")
    print("archived, official Phase 4 result.")

    print("\nSENSITIVITY ANALYSIS COMPLETE -- STOPPING per instruction.")
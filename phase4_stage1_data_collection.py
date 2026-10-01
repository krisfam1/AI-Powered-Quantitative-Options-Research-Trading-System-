from dotenv import load_dotenv
load_dotenv()

"""
Phase 4, Stage 1: collects the frozen baseline's qualifying signals
across the full 90-day window, merges each with its T-1 GEX data via
gex_lookup.py, and builds the two-stage clustering structure (within-
ticker, then cross-ticker same-calendar-day) per the locked design.

Does NOT run any statistical test yet -- this stage only builds and
reports the real, raw data structure (observation counts, cluster
counts at each stage) so the actual test (Stage 2) operates on a
verified, correct foundation.

Frozen baseline, exactly as validated: bullish regime (real, dynamic
SPY regime) + 7-factor score >= 20 + real breakout gate + call
direction. Train: 2026-06-11 to 2026-08-11. Holdout: 2026-08-11 to
2026-09-09.
"""

import backtest_engine as be
from backtest_engine import get_daily_regime
from entry_scorer import calculate_entry_score
from signal_validation_core import calculate_forward_stats, TICKERS
from gex_lookup import get_gex_for_signal
from datetime import datetime, timezone, timedelta

TRAIN_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
TRAIN_END = datetime(2026, 8, 11, tzinfo=timezone.utc)
HOLDOUT_END = datetime(2026, 9, 9, tzinfo=timezone.utc)


def collect_baseline_signals_with_gex():
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
                "ticker": ticker, "index": index, "timestamp": timestamp,
                "signal_date": timestamp.date().isoformat(), "period": period,
                **fwd_stats, "gex": gex_result,
            })
        print(ticker + ": done")
    return all_signals


def build_ticker_day_clusters(signals):
    """Stage 1: consecutive same-ticker signals (gap<=12 bars) collapse to one cluster."""
    by_ticker = {}
    for s in signals:
        by_ticker.setdefault(s["ticker"], []).append(s)

    clusters = []
    for ticker, sigs in by_ticker.items():
        sigs_sorted = sorted(sigs, key=lambda s: s["index"])
        current_cluster = []
        for s in sigs_sorted:
            if current_cluster and s["index"] - current_cluster[-1]["index"] > 12:
                clusters.append(current_cluster)
                current_cluster = []
            current_cluster.append(s)
        if current_cluster:
            clusters.append(current_cluster)
    return clusters


def build_calendar_day_clusters(ticker_day_clusters):
    """
    Stage 2: ticker-day clusters sharing the same calendar date collapse
    into one observation per date. FIX (pre-specified before any result
    is computed): a ticker with multiple same-day clusters is first
    averaged WITHIN that ticker, so every ticker contributes equally to
    the day's representative value regardless of how many separate
    clusters it produced -- avoids one ticker's intraday multiplicity
    silently dominating the calendar-day average.
    """
    by_date_and_ticker = {}
    for cluster in ticker_day_clusters:
        date = cluster[0]["signal_date"]
        ticker = cluster[0]["ticker"]
        by_date_and_ticker.setdefault(date, {}).setdefault(ticker, []).append(cluster)
    return by_date_and_ticker


if __name__ == "__main__":
    print("Collecting frozen baseline signals across the full 90-day window, merged with T-1 GEX...\n")
    signals = collect_baseline_signals_with_gex()
    print("\nTotal raw signal observations: " + str(len(signals)))

    with_gex = [s for s in signals if s["gex"]["available"]]
    without_gex = [s for s in signals if not s["gex"]["available"]]
    print("With available T-1 GEX: " + str(len(with_gex)))
    print("Without available GEX: " + str(len(without_gex)))

    ticker_day_clusters = build_ticker_day_clusters(with_gex)
    print("\nStage 1 -- ticker-day clusters (within-ticker, gap<=12 bars): " + str(len(ticker_day_clusters)))

    calendar_day_clusters = build_calendar_day_clusters(ticker_day_clusters)
    print("Stage 2 -- calendar-day observations (cross-ticker collapse, ticker-averaged first): " + str(len(calendar_day_clusters)))

    train_dates = [d for d in calendar_day_clusters if any(clusters[0][0]["period"] == "train" for clusters in calendar_day_clusters[d].values())]
    holdout_dates = [d for d in calendar_day_clusters if any(clusters[0][0]["period"] == "holdout" for clusters in calendar_day_clusters[d].values())]
    print("Train calendar-day observations: " + str(len(train_dates)))
    print("Holdout calendar-day observations: " + str(len(holdout_dates)))

    print("\nPer-ticker raw signal counts:")
    for ticker in TICKERS:
        count = len([s for s in with_gex if s["ticker"] == ticker])
        print("  " + ticker + ": " + str(count))

    print("\nSample calendar-day observation (first one, for structure verification):")
    first_date = sorted(calendar_day_clusters.keys())[0]
    sample = calendar_day_clusters[first_date]
    print("Date: " + first_date + " -- tickers active: " + str(list(sample.keys())) + " (each ticker's clusters will be averaged within-ticker first, per the fix)")
from dotenv import load_dotenv
load_dotenv()

"""
Ablation study: tests whether each individual factor (and cumulative
combinations) adds real predictive power to forward returns on the
underlying -- no option pricing involved.

Methodology: breakout/breakdown gate is always required (the existing,
mandatory design). For each ablation level, splits qualifying signals
by MEDIAN cumulative sub-score (top half vs. bottom half) -- avoids any
threshold tuning/optimization, per explicit instruction. If a factor
combination has real predictive power, the top-half group should show
meaningfully better forward returns than the bottom half. If it's
noise, the two halves should look similar.

Levels tested, cumulative:
1. Breakout/breakdown alone (gate only, no scoring split possible)
2. + relative volume
3. + trend strength
4. + momentum
5. + volatility regime
6. + SPY regime alignment
7. + news sentiment (full score, same as core validation)
"""

import statistics
import backtest_engine as be
from entry_scorer import calculate_entry_score
from signal_validation_core import calculate_forward_stats, TICKERS, HORIZONS
from datetime import datetime, timezone, timedelta

LEVELS = [
    ("2: +relative_volume", ["relative_volume"]),
    ("3: +trend_strength", ["relative_volume", "trend_strength"]),
    ("4: +momentum", ["relative_volume", "trend_strength", "momentum"]),
    ("5: +volatility_regime", ["relative_volume", "trend_strength", "momentum", "volatility_regime"]),
    ("6: +market_regime_alignment", ["relative_volume", "trend_strength", "momentum", "volatility_regime", "market_regime_alignment"]),
    ("7: +news_sentiment (full)", ["relative_volume", "trend_strength", "momentum", "volatility_regime", "market_regime_alignment", "news_sentiment"]),
]


def collect_gated_signals():
    """Level 1: every breakout/breakdown-qualifying moment, with full score breakdown attached."""
    all_signals = []
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=90)

    for ticker in TICKERS:
        bars = be.get_historical_bars(ticker, start, end)
        if not bars:
            continue
        for direction in ["call", "put"]:
            count = 0
            for index in range(60, len(bars)):
                if direction == "call" and not be.check_breakout(bars, index, lookback=20):
                    continue
                if direction == "put" and not be.check_breakdown(bars, index, lookback=20):
                    continue
                try:
                    score_result = calculate_entry_score(ticker, bars, index, direction, spy_regime="neutral")
                except Exception:
                    continue
                fwd_stats = calculate_forward_stats(bars, index, direction)
                all_signals.append({
                    "ticker": ticker, "direction": direction, "index": index,
                    "breakdown": score_result["breakdown"], "forward_stats": fwd_stats,
                })
                count += 1
            print(ticker + " " + direction + ": " + str(count) + " gate-qualifying moments")
    return all_signals


def _median_split_compare(signals, factor_keys, metric="return_20bar"):
    scored = []
    for s in signals:
        sub_score = sum(s["breakdown"].get(k, 0) for k in factor_keys)
        if metric in s["forward_stats"]:
            scored.append((sub_score, s["forward_stats"][metric]))

    if len(scored) < 10:
        return None

    scored.sort(key=lambda x: x[0])
    median_idx = len(scored) // 2
    bottom_half = [r for _, r in scored[:median_idx]]
    top_half = [r for _, r in scored[median_idx:]]

    return {
        "n_total": len(scored),
        "bottom_half_mean": round(statistics.mean(bottom_half) * 100, 3),
        "top_half_mean": round(statistics.mean(top_half) * 100, 3),
        "bottom_half_winrate": round(len([r for r in bottom_half if r > 0]) / len(bottom_half) * 100, 1),
        "top_half_winrate": round(len([r for r in top_half if r > 0]) / len(top_half) * 100, 1),
    }


if __name__ == "__main__":
    print("Collecting all breakout/breakdown-gated signals with full score breakdowns...\n")
    signals = collect_gated_signals()
    print("\nTotal gated signals: " + str(len(signals)))

    print("\n" + "=" * 80)
    print("ABLATION: does adding each factor meaningfully separate top-half vs bottom-half forward returns?")
    print("(If a factor has real predictive power, top-half should clearly beat bottom-half)")
    print("=" * 80)

    for metric in ["return_10bar", "return_20bar"]:
        print("\n--- Metric: " + metric + " ---")
        for level_name, factor_keys in LEVELS:
            result = _median_split_compare(signals, factor_keys, metric)
            if result is None:
                print(level_name + ": insufficient data")
                continue
            print(level_name + " (n=" + str(result["n_total"]) + "): bottom_half=" + str(result["bottom_half_mean"]) + "% (wr=" + str(result["bottom_half_winrate"]) + "%) | top_half=" + str(result["top_half_mean"]) + "% (wr=" + str(result["top_half_winrate"]) + "%)")
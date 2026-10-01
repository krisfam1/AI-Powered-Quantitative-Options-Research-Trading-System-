from dotenv import load_dotenv
load_dotenv()

"""
Temporal consistency test within the clean June 11 - September 9, 2026
window. NOT cross-regime robustness -- explicitly labeled as such.
Period boundaries determined MECHANICALLY (trading-day thirds) and
FROZEN before any V1/V2 result is examined.
"""

import statistics
from datetime import datetime, timezone
from collections import defaultdict
from portfolio_backtest import run_portfolio_backtest
from gex_data_loader import get_real_trading_days
from scipy import stats as scipy_stats

TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
FULL_START = "2026-06-10"
FULL_END = "2026-09-09"

print("Determining the real, complete set of trading days in the clean window...")
trading_days = get_real_trading_days(FULL_START, FULL_END, reference_ticker="SPY")
print("Total real trading days found: " + str(len(trading_days)))

# Mechanical split into thirds -- FROZEN before any performance is examined
n = len(trading_days)
third = n // 3
period_boundaries = [
    (trading_days[0], trading_days[third - 1]),
    (trading_days[third], trading_days[2 * third - 1]),
    (trading_days[2 * third], trading_days[-1]),
]

print("\n" + "=" * 100)
print("FROZEN PERIOD BOUNDARIES (determined mechanically, before any V1/V2 result examined)")
print("=" * 100)
for i, (start, end) in enumerate(period_boundaries):
    print("Period " + str(i+1) + ": " + str(start) + " to " + str(end))

periods_utc = [(datetime.combine(s, datetime.min.time(), tzinfo=timezone.utc), datetime.combine(e, datetime.min.time(), tzinfo=timezone.utc) + __import__("datetime").timedelta(days=1)) for s, e in period_boundaries]


def compute_period_metrics(trades):
    n = len(trades)
    if n == 0:
        return {"n": 0, "total_pnl": 0, "win_rate": None, "profit_factor": None}
    wins = [t for t in trades if t["pnl_dollars"] > 0]
    gross_win = sum(t["pnl_dollars"] for t in trades if t["pnl_dollars"] > 0)
    gross_loss = abs(sum(t["pnl_dollars"] for t in trades if t["pnl_dollars"] < 0))
    return {
        "n": n, "total_pnl": sum(t["pnl_dollars"] for t in trades),
        "win_rate": len(wins) / n * 100,
        "profit_factor": (gross_win / gross_loss) if gross_loss else None,
    }


all_period_results = []

for period_idx, (p_start, p_end) in enumerate(periods_utc):
    print("\n" + "=" * 100)
    print("PERIOD " + str(period_idx + 1) + ": " + str(period_boundaries[period_idx][0]) + " to " + str(period_boundaries[period_idx][1]))
    print("=" * 100)

    v1_results = {}
    v2_results = {}
    for ticker in TICKERS:
        print("Running " + ticker + " V1/V2 for Period " + str(period_idx+1) + "...")
        v1_results[ticker] = run_portfolio_backtest([ticker], p_start, p_end, starting_capital=100000.0, fixed_direction="call", pricing_mode="v1")
        v2_results[ticker] = run_portfolio_backtest([ticker], p_start, p_end, starting_capital=100000.0, fixed_direction="call", pricing_mode="v2_corrected")

    all_v1 = [t for tk in TICKERS for t in v1_results[tk]["closed_trades"]]
    all_v2 = [t for tk in TICKERS for t in v2_results[tk]["closed_trades"]]

    v1_m = compute_period_metrics(all_v1)
    v2_m = compute_period_metrics(all_v2)
    diff = v1_m["total_pnl"] - v2_m["total_pnl"]

    print("\nV1: n=" + str(v1_m["n"]) + " total_pnl=$" + str(round(v1_m["total_pnl"],2)) + " win_rate=" + str(round(v1_m["win_rate"],1) if v1_m["win_rate"] else None) + "%")
    print("V2: n=" + str(v2_m["n"]) + " total_pnl=$" + str(round(v2_m["total_pnl"],2)) + " win_rate=" + str(round(v2_m["win_rate"],1) if v2_m["win_rate"] else None) + "%")
    print("V1 - V2 P&L difference: $" + str(round(diff,2)))

    # Matched-pair analysis
    matched_pairs = []
    for ticker in TICKERS:
        v1_by_date = defaultdict(list)
        v2_by_date = defaultdict(list)
        for t in v1_results[ticker]["closed_trades"]:
            v1_by_date[str(t["entry_date"])].append(t)
        for t in v2_results[ticker]["closed_trades"]:
            v2_by_date[str(t["entry_date"])].append(t)
        for d in set(v1_by_date.keys()) & set(v2_by_date.keys()):
            for v1t, v2t in zip(v1_by_date[d], v2_by_date[d]):
                matched_pairs.append({"ticker": ticker, "v1": v1t, "v2": v2t})

    matched_p = None
    if len(matched_pairs) >= 5:
        diffs = [p["v2"]["pnl_dollars"] - p["v1"]["pnl_dollars"] for p in matched_pairs]
        try:
            _, matched_p = scipy_stats.wilcoxon(diffs)
        except Exception:
            matched_p = None
    print("Matched pairs: " + str(len(matched_pairs)) + " | Wilcoxon p=" + (str(round(matched_p,4)) if matched_p is not None else "insufficient data"))

    # Calendar-day aggregation
    v1_by_day = defaultdict(float)
    v2_by_day = defaultdict(float)
    for t in all_v1:
        v1_by_day[str(t["exit_date"])] += t["pnl_dollars"]
    for t in all_v2:
        v2_by_day[str(t["exit_date"])] += t["pnl_dollars"]
    common_days = sorted(set(v1_by_day.keys()) & set(v2_by_day.keys()))
    day_p = None
    if len(common_days) >= 5:
        day_diffs = [v2_by_day[d] - v1_by_day[d] for d in common_days]
        try:
            _, day_p = scipy_stats.wilcoxon(day_diffs)
        except Exception:
            day_p = None
    print("Common calendar days: " + str(len(common_days)) + " | Wilcoxon p=" + (str(round(day_p,4)) if day_p is not None else "insufficient data"))

    # Ticker contribution
    ticker_diffs = {}
    for tk in TICKERS:
        v1_tk = sum(t["pnl_dollars"] for t in v1_results[tk]["closed_trades"])
        v2_tk = sum(t["pnl_dollars"] for t in v2_results[tk]["closed_trades"])
        ticker_diffs[tk] = v1_tk - v2_tk
    print("Ticker contribution to V1-V2 diff: " + str({k: round(v,2) for k,v in ticker_diffs.items()}))

    all_period_results.append({
        "period": period_idx + 1, "start": str(period_boundaries[period_idx][0]), "end": str(period_boundaries[period_idx][1]),
        "v1_pnl": v1_m["total_pnl"], "v2_pnl": v2_m["total_pnl"], "diff": diff,
        "v1_n": v1_m["n"], "v2_n": v2_m["n"], "v1_win_rate": v1_m["win_rate"], "v2_win_rate": v2_m["win_rate"],
        "matched_p": matched_p, "day_p": day_p, "ticker_diffs": ticker_diffs,
    })

print("\n" + "=" * 100)
print("CROSS-PERIOD CONSISTENCY SUMMARY")
print("=" * 100)
v1_wins = len([r for r in all_period_results if r["diff"] > 0])
v2_wins = len([r for r in all_period_results if r["diff"] < 0])
print("Periods where V1 beats V2: " + str(v1_wins) + " / 3")
print("Periods where V2 beats V1: " + str(v2_wins) + " / 3")
signs = [r["diff"] > 0 for r in all_period_results]
print("Direction consistent across all 3 periods: " + str(len(set(signs)) == 1))

print("\nPer-period summary:")
for r in all_period_results:
    print("  Period " + str(r["period"]) + " (" + r["start"] + " to " + r["end"] + "): diff=$" + str(round(r["diff"],2)) + " matched_p=" + (str(round(r["matched_p"],4)) if r["matched_p"] else "N/A") + " day_p=" + (str(round(r["day_p"],4)) if r["day_p"] else "N/A"))

print("\nTicker concentration across periods:")
for tk in TICKERS:
    vals = [r["ticker_diffs"][tk] for r in all_period_results]
    print("  " + tk + ": " + str([round(v,2) for v in vals]) + " (consistent sign: " + str(len(set(v > 0 for v in vals)) == 1) + ")")

print("\n" + "=" * 100)
print("CRITICAL INTERPRETATION")
print("=" * 100)
print("This is TEMPORAL CONSISTENCY WITHIN THE CLEAN JUNE 11 - SEPTEMBER 9, 2026 WINDOW ONLY.")
print("This is NOT cross-regime robustness and NOT independent out-of-sample validation.")
print("All 3 periods share the same underlying data source, market conditions continuity, and")
print("overall time span -- they are NOT independent market regimes.")

print("\n" + "=" * 100)
print("ROBUSTNESS CLASSIFICATION")
print("=" * 100)
if v1_wins == 3:
    print("Direction: V1 beat V2 in all 3 periods -- consistent within this single window,")
    print("but per the interpretation rule above, this does NOT constitute cross-regime evidence.")
    print("CLASSIFICATION: B -- V1 appears more robust than V2 WITHIN THIS WINDOW, but evidence")
    print("remains insufficient for general/cross-regime superiority claims.")
elif v1_wins >= 2:
    print("CLASSIFICATION: B -- V1 shows a directional edge in most sub-periods, but not unanimous;")
    print("evidence remains insufficient for general superiority claims.")
else:
    print("CLASSIFICATION: D -- Evidence is contradictory/inconclusive across sub-periods.")

print("\nTEMPORAL CONSISTENCY TEST COMPLETE. STOPPING per instruction, awaiting review.")
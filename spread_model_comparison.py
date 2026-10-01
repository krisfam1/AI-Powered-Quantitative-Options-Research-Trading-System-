from dotenv import load_dotenv
load_dotenv()

"""
Compares the EXISTING synthetic spread model (options_backtest_engine.py's
_estimated_spread_cost_pct, used throughout every V1 backtest tonight)
against REAL EODHD bid-ask spreads, on the same 580 real Phase 6
candidate signals. Purely descriptive -- no new hypothesis, no
comparison-as-experiment, just: how far off has our existing model been?
"""

import os
import requests
from datetime import datetime, timezone, timedelta
import backtest_engine as be
from entry_scorer import calculate_entry_score
from backtest_engine import get_daily_regime
from options_backtest_engine import _estimated_spread_cost_pct

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
TARGET_DELTA = 0.30
TARGET_DTE = 14


def find_phase6_candidate_signals(ticker, bars):
    signals = []
    for index in range(60, len(bars)):
        bar_date = bars[index].timestamp.date()
        ts = datetime.combine(bar_date, datetime.min.time(), tzinfo=timezone.utc)
        try:
            regime = get_daily_regime(ticker, ts, period=50)
        except Exception:
            continue
        if regime != "bullish":
            continue
        if not be.check_breakout(bars, index, lookback=20):
            continue
        try:
            score_result = calculate_entry_score(ticker, bars, index, "call", spy_regime="bullish")
        except Exception:
            continue
        if score_result["total_score"] >= 20:
            signals.append(index)
    return signals


def find_nearest_v1_convention_contract(ticker, date, target_delta=TARGET_DELTA, target_dte=TARGET_DTE):
    exp_from = (date + timedelta(days=target_dte-4)).isoformat()
    exp_to = (date + timedelta(days=target_dte+4)).isoformat()
    params = {
        "filter[underlying_symbol]": ticker, "filter[tradetime_from]": date.isoformat(), "filter[tradetime_to]": date.isoformat(),
        "filter[exp_date_from]": exp_from, "filter[exp_date_to]": exp_to,
        "api_token": EODHD_API_TOKEN, "page[limit]": 1000,
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=60)
        resp.raise_for_status()
        records = [r["attributes"] for r in resp.json().get("data", []) if r["attributes"].get("type") == "call"]
    except Exception:
        return None
    candidates = [r for r in records if r.get("delta") is not None and r.get("dte") is not None]
    if not candidates:
        return None
    best = min(candidates, key=lambda r: abs(r["delta"] - target_delta) + abs(r["dte"] - target_dte) * 0.01)
    return best


print("Finding real Phase 6 candidate signals across all 6 tickers...\n")
all_signals = []
for ticker in TICKERS:
    bars = be.get_historical_bars(ticker, FIXED_START, FIXED_END)
    indices = find_phase6_candidate_signals(ticker, bars)
    for idx in indices:
        all_signals.append({"ticker": ticker, "date": bars[idx].timestamp.date()})
print("Total candidate signals: " + str(len(all_signals)))

print("\nFetching real contracts, comparing REAL spread vs SYNTHETIC model estimate (same pass)...\n")

results = []
skipped = 0
for i, sig in enumerate(all_signals):
    contract = find_nearest_v1_convention_contract(sig["ticker"], sig["date"])
    if contract is None or contract.get("bid") is None or contract.get("ask") is None:
        skipped += 1
        continue
    bid, ask = contract["bid"], contract["ask"]
    midpoint = (bid + ask) / 2
    if midpoint <= 0:
        skipped += 1
        continue
    real_spread_pct = (ask - bid) / midpoint * 100

    synthetic_spread_pct = _estimated_spread_cost_pct(midpoint) * 100

    results.append({
        "ticker": sig["ticker"], "date": sig["date"].isoformat(), "midpoint": midpoint,
        "real_spread_pct": real_spread_pct, "synthetic_spread_pct": synthetic_spread_pct,
        "diff": real_spread_pct - synthetic_spread_pct,
    })
    if (i+1) % 50 == 0:
        print("  ... " + str(i+1) + " / " + str(len(all_signals)) + " processed")

print("\nProcessed: " + str(len(results)) + " | Skipped: " + str(skipped))

import statistics
print("\n" + "=" * 100)
print("REAL vs SYNTHETIC SPREAD MODEL -- COMPARISON REPORT")
print("=" * 100)

real_spreads = [r["real_spread_pct"] for r in results]
synth_spreads = [r["synthetic_spread_pct"] for r in results]
diffs = [r["diff"] for r in results]

print("\nOVERALL (n=" + str(len(results)) + "):")
print("  Real spread:      median=" + str(round(statistics.median(real_spreads),2)) + "%  mean=" + str(round(statistics.mean(real_spreads),2)) + "%")
print("  Synthetic spread: median=" + str(round(statistics.median(synth_spreads),2)) + "%  mean=" + str(round(statistics.mean(synth_spreads),2)) + "%")
print("  Difference (real - synthetic): median=" + str(round(statistics.median(diffs),2)) + "pp  mean=" + str(round(statistics.mean(diffs),2)) + "pp")

understated = len([d for d in diffs if d > 0])
overstated = len([d for d in diffs if d < 0])
print("\n  Synthetic UNDERSTATED real spread: " + str(understated) + " / " + str(len(results)) + " (" + str(round(understated/len(results)*100,1)) + "%)")
print("  Synthetic OVERSTATED real spread: " + str(overstated) + " / " + str(len(results)) + " (" + str(round(overstated/len(results)*100,1)) + "%)")

print("\nBY TICKER:")
for ticker in TICKERS:
    t_results = [r for r in results if r["ticker"] == ticker]
    if not t_results:
        continue
    t_real = [r["real_spread_pct"] for r in t_results]
    t_synth = [r["synthetic_spread_pct"] for r in t_results]
    t_diff = [r["diff"] for r in t_results]
    print("  " + ticker + " (n=" + str(len(t_results)) + "): real_median=" + str(round(statistics.median(t_real),2)) + "% synthetic_median=" + str(round(statistics.median(t_synth),2)) + "% diff_median=" + str(round(statistics.median(t_diff),2)) + "pp")

print("\nCOMPARISON COMPLETE. Descriptive only -- no threshold, no significance test, no new experiment.")
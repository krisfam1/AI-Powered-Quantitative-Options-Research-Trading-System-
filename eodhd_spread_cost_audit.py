from dotenv import load_dotenv
load_dotenv()

"""
Step 0 -- Descriptive spread-cost audit. For every real Phase 6
candidate signal, finds the real EODHD contract closest to V1's
convention (nearest 0.30 delta, ~14 DTE) on that SAME signal date,
and reports real bid-ask spread as % of midpoint. Purely descriptive
-- no hypothesis test, no comparison, no threshold, no significance
claim. Uses same-day quotes (not T-1) since this describes real
historical execution cost, not a new signal-generation decision.
"""

import os
import requests
from datetime import datetime, timezone, timedelta
import backtest_engine as be
from entry_scorer import calculate_entry_score
from backtest_engine import get_daily_regime

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
    print(ticker + ": " + str(len(indices)) + " candidate signals")
    for idx in indices:
        all_signals.append({"ticker": ticker, "date": bars[idx].timestamp.date()})

print("\nTotal candidate signals: " + str(len(all_signals)))
print("\nFetching real V1-convention contracts for each signal (this will take a while)...\n")

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
    spread_pct = (ask - bid) / midpoint * 100
    results.append({
        "ticker": sig["ticker"], "date": sig["date"].isoformat(), "delta": contract["delta"], "dte": contract["dte"],
        "bid": bid, "ask": ask, "midpoint": midpoint, "spread_pct": spread_pct,
    })
    if (i+1) % 50 == 0:
        print("  ... " + str(i+1) + " / " + str(len(all_signals)) + " processed")

print("\nProcessed: " + str(len(results)) + " | Skipped (no data/invalid): " + str(skipped))

print("\n" + "=" * 100)
print("DESCRIPTIVE SPREAD-COST REPORT (real bid/ask, V1's actual 0.30-delta/14-DTE convention)")
print("=" * 100)

import statistics
all_spreads = [r["spread_pct"] for r in results]
print("\nOVERALL (n=" + str(len(results)) + "):")
print("  Median spread: " + str(round(statistics.median(all_spreads),2)) + "%")
print("  Mean spread: " + str(round(statistics.mean(all_spreads),2)) + "%")
print("  Min/Max: " + str(round(min(all_spreads),2)) + "% / " + str(round(max(all_spreads),2)) + "%")

print("\nBY TICKER:")
for ticker in TICKERS:
    ticker_spreads = [r["spread_pct"] for r in results if r["ticker"] == ticker]
    if not ticker_spreads:
        print("  " + ticker + ": no data")
        continue
    print("  " + ticker + " (n=" + str(len(ticker_spreads)) + "): median=" + str(round(statistics.median(ticker_spreads),2)) + "% mean=" + str(round(statistics.mean(ticker_spreads),2)) + "%")

avg_delta = statistics.mean([r["delta"] for r in results])
avg_dte = statistics.mean([r["dte"] for r in results])
print("\nConfirming convention match: avg_delta=" + str(round(avg_delta,3)) + " (target 0.30) avg_dte=" + str(round(avg_dte,1)) + " (target 14)")

print("\nDESCRIPTIVE AUDIT COMPLETE. No comparison made, no hypothesis tested, no threshold applied.")
from dotenv import load_dotenv
load_dotenv()

"""
Comprehensive V1 volatility warm-up/seed audit, per explicit scope.
Does NOT modify production code or methodology. Audit only.
"""

import statistics
from datetime import datetime, timezone
import backtest_engine as be
from options_backtest_engine import _precompute_hybrid_volatility_series, calculate_historical_volatility
from portfolio_backtest import run_portfolio_backtest

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
SAMPLE_INDICES = [0, 50, 100, 250, 500, 750, 1000, 1500, 2000, 3000, 4000, 5000]

print("=" * 100)
print("SECTION 1: PER-TICKER SEED/DIVERGENCE CHECK")
print("=" * 100)

ticker_data = {}
for ticker in TICKERS:
    bars = be.get_historical_bars(ticker, FIXED_START, FIXED_END)
    series = _precompute_hybrid_volatility_series(bars)
    ticker_data[ticker] = {"bars": bars, "series": series}

    print("\n--- " + ticker + " ---")
    print("Bar count: " + str(len(bars)) + " | Series length: " + str(len(series)))
    for idx in SAMPLE_INDICES:
        if idx < len(series):
            print("  index=" + str(idx) + " timestamp=" + str(bars[idx].timestamp) + " vol=" + str(round(series[idx], 4)))

    # Find first index where the 20-trading-day warmup ends (exact, via unique trading-day count)
    seen_dates = set()
    warmup_end_index = None
    for i, b in enumerate(bars):
        seen_dates.add(b.timestamp.date())
        if len(seen_dates) > 20 and warmup_end_index is None:
            warmup_end_index = i
            break
    ticker_data[ticker]["warmup_end_index"] = warmup_end_index
    if warmup_end_index:
        print("  Warm-up ends at index=" + str(warmup_end_index) + " (date=" + str(bars[warmup_end_index].timestamp.date()) + ")")
    else:
        print("  Warm-up boundary not found within available bars")

print("\n" + "=" * 100)
print("SECTION 2: SEED MECHANISM (confirmed directly from source)")
print("=" * 100)
print("Seed value: 0.30, hardcoded")
print("Trigger condition: day_position < lookback_days (20) inside _daily_bar_vol()")
print("day_position = index of current trading date within the sorted list of unique trading days seen so far")
print("EWMA blend (lambda=0.90) of 0.30 with 0.30 stays exactly 0.30 throughout the 20-day window")
print("Warm-up ends once 20 unique real trading days have accumulated in the series")

print("\n" + "=" * 100)
print("SECTION 3 & 5: COMPARABLE 27-SIGNAL ANALYSIS")
print("=" * 100)

print("Running V1 and V2 for AAPL over the fixed range (reusing the same comparable-signal population)...")
v1_result = run_portfolio_backtest(["AAPL"], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v1")
v2_result = run_portfolio_backtest(["AAPL"], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v2_entry_iv")

v1_trades = sorted(v1_result["closed_trades"], key=lambda t: str(t["entry_date"]))
v2_trades = sorted(v2_result["closed_trades"], key=lambda t: str(t["entry_date"]))
v1_by_date = {str(t["entry_date"]): t for t in v1_trades}
v2_by_date = {str(t["entry_date"]): t for t in v2_trades}
common_dates = sorted(set(v1_by_date.keys()) & set(v2_by_date.keys()))

v2_coverage = v2_result["v2_coverage_log"]
coverage_by_ts = {str(c["signal_timestamp"]): c for c in v2_coverage if c["v2_iv_available"]}

aapl_bars = ticker_data["AAPL"]["bars"]
aapl_warmup_end = ticker_data["AAPL"]["warmup_end_index"]

warmup_group = []
mature_group = []

print("\n| Date | Index | V1 Vol | Warmup/Mature | V2 IV | V2/V1 Ratio |")
for d in common_dates:
    v1t = v1_by_date[d]
    v2t = v2_by_date[d]
    ts_str = None
    for c_ts, c in coverage_by_ts.items():
        if str(c["signal_timestamp"])[:10] == d:
            ts_str = c_ts
            match_c = c
            break
    if ts_str is None:
        continue
    match_idx = None
    for i, b in enumerate(aapl_bars):
        if str(b.timestamp) == ts_str:
            match_idx = i
            break
    if match_idx is None:
        continue

    is_warmup = (aapl_warmup_end is not None and match_idx < aapl_warmup_end)
    ratio = v2t["entry_premium"] / v1t["entry_premium"]
    row = {"date": d, "index": match_idx, "v1_vol": match_c["v1_vol"], "v2_iv": match_c["v2_iv"], "ratio": ratio, "is_warmup": is_warmup}
    print(d + " | idx=" + str(match_idx) + " | v1_vol=" + str(round(match_c["v1_vol"],4)) + " | " + ("WARMUP" if is_warmup else "MATURE") + " | v2_iv=" + str(round(match_c["v2_iv"],4)) + " | ratio=" + str(round(ratio,3)))

    if is_warmup:
        warmup_group.append(row)
    else:
        mature_group.append(row)

print("\n" + "=" * 100)
print("SECTION 3 SUMMARY")
print("=" * 100)
total = len(warmup_group) + len(mature_group)
print("Total classified comparable signals: " + str(total) + " (of 27 expected)")
print("Warm-up group: " + str(len(warmup_group)) + " (" + str(round(len(warmup_group)/total*100,1) if total else 0) + "%)")
print("Mature group: " + str(len(mature_group)) + " (" + str(round(len(mature_group)/total*100,1) if total else 0) + "%)")

print("\n" + "=" * 100)
print("SECTION 4: GROUP COMPARISON")
print("=" * 100)
for label, group in [("WARM-UP", warmup_group), ("MATURE", mature_group)]:
    if not group:
        print(label + ": no observations")
        continue
    ratios = [g["ratio"] for g in group]
    v1_vols = [g["v1_vol"] for g in group]
    v2_ivs = [g["v2_iv"] for g in group]
    print(label + " (n=" + str(len(group)) + "):")
    print("  Median V1 vol: " + str(round(statistics.median(v1_vols),4)) + " | Median V2 IV: " + str(round(statistics.median(v2_ivs),4)))
    print("  Median V2/V1 ratio: " + str(round(statistics.median(ratios),3)) + " | Mean: " + str(round(statistics.mean(ratios),3)))

print("\n" + "=" * 100)
print("SECTION 5: WAS THE ORIGINAL 8-SIGNAL DIAGNOSTIC-2 SAMPLE REPRESENTATIVE?")
print("=" * 100)
diag2_indices = [55, 188, 215, 282, 310, 356, 434, 448]
diag2_warmup_count = len([i for i in diag2_indices if aapl_warmup_end and i < aapl_warmup_end])
print("Diagnostic-2 sample: 8/8 signals at indices " + str(diag2_indices))
print("AAPL warm-up boundary: index " + str(aapl_warmup_end))
print("Of the 8 original sample signals: " + str(diag2_warmup_count) + " were in the WARM-UP period")
print("Representativeness: " + ("NOT representative -- 100% warmup vs " + str(round(len(warmup_group)/total*100,1) if total else 0) + "% warmup in the full comparable population" if diag2_warmup_count == 8 else "Partially representative"))

print("\nAUDIT COMPLETE. STOPPING per instruction.")
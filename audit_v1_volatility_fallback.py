from dotenv import load_dotenv
load_dotenv()

"""
V1 Volatility-Source Integrity Audit. Does NOT modify production code.
Directly inspects the volatility computation pipeline in isolation --
more precise than reverse-engineering from a full backtest run.

calculate_historical_volatility()'s exact logic (confirmed from source
earlier tonight):
    key = _vol_cache_key(bars, cache_namespace)
    if key not in _volatility_series_cache:
        _volatility_series_cache[key] = _precompute_hybrid_volatility_series(bars)
    series = _volatility_series_cache[key]
    if current_index < len(series):
        return series[current_index]
    return 0.30

Fallback triggers ONLY when current_index >= len(series). This script
checks directly whether the precomputed series length matches the
bars length, and if not, identifies exactly which indices/timestamps
would fall into the fallback zone.
"""

from datetime import datetime, timezone
import backtest_engine as be
from options_backtest_engine import _precompute_hybrid_volatility_series, calculate_historical_volatility

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKER = "AAPL"

print("Fetching real historical bars for " + TICKER + "...")
bars = be.get_historical_bars(TICKER, FIXED_START, FIXED_END)
print("Total bars: " + str(len(bars)))

print("\nComputing the hybrid volatility series directly (same function V1 uses internally)...")
series = _precompute_hybrid_volatility_series(bars)
print("Series length: " + str(len(series)))

print("\n" + "=" * 90)
print("STEP 1 & 3: DOES THE FALLBACK CONDITION EVER TRIGGER FOR THIS TICKER/RANGE?")
print("=" * 90)
print("len(bars) = " + str(len(bars)) + " | len(series) = " + str(len(series)))
if len(series) >= len(bars):
    print("Series covers EVERY possible bar index (0 to " + str(len(bars)-1) + ") -- fallback CANNOT trigger for any signal in this range.")
else:
    fallback_start_index = len(series)
    fallback_count = len(bars) - len(series)
    print("Series is SHORTER than bars by " + str(fallback_count) + " entries.")
    print("Fallback WOULD trigger for any signal at index >= " + str(fallback_start_index))
    if fallback_start_index < len(bars):
        print("That corresponds to timestamps from " + str(bars[fallback_start_index].timestamp) + " onward.")

print("\n" + "=" * 90)
print("STEP 5: VERIFY THE ACTUAL VALUE AT SEVERAL REAL SIGNAL-LIKE INDICES")
print("=" * 90)
# Check the actual value calculate_historical_volatility() returns at several real indices,
# using the EXACT same cache_namespace="portfolio" that V1 actually uses
sample_indices = [100, 500, 1000, 2000, 3000, 4000, 5000, len(bars)-1]
for idx in sample_indices:
    if idx >= len(bars):
        continue
    val = calculate_historical_volatility(bars, idx, cache_namespace="audit_check")
    is_fallback = (idx >= len(series))
    print("Index " + str(idx) + " (timestamp=" + str(bars[idx].timestamp) + "): vol=" + str(round(val, 4)) + " is_fallback=" + str(is_fallback))

print("\n" + "=" * 90)
print("STEP 4: SPECIFIC INVESTIGATION OF THE 8 DIAGNOSTIC-2 SIGNALS")
print("=" * 90)
diag2_timestamps_str = [
    "2026-06-11 17:25:00+00:00", "2026-06-15 13:30:00+00:00", "2026-06-15 15:45:00+00:00",
    "2026-06-16 13:50:00+00:00", "2026-06-16 16:10:00+00:00", "2026-06-17 13:30:00+00:00",
    "2026-06-18 12:00:00+00:00", "2026-06-18 13:30:00+00:00",
]
print("| Signal | V1 vol | Source | Bar Index | len(series) | Fallback? |")
for ts_str in diag2_timestamps_str:
    match_idx = None
    for i, b in enumerate(bars):
        if str(b.timestamp) == ts_str:
            match_idx = i
            break
    if match_idx is None:
        print(ts_str + ": COULD NOT MATCH to a real bar index")
        continue
    val = calculate_historical_volatility(bars, match_idx, cache_namespace="audit_check")
    is_fallback = (match_idx >= len(series))
    source = "FALLBACK (0.30 hardcoded)" if is_fallback else "CALCULATED (hybrid EWMA series)"
    print(ts_str + " | vol=" + str(round(val,4)) + " | " + source + " | index=" + str(match_idx) + " | len(series)=" + str(len(series)) + " | fallback=" + str(is_fallback))

print("\nAUDIT COMPLETE.")
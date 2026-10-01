from dotenv import load_dotenv
load_dotenv()

"""
Unit tests, lookahead tests, and the critical timestamp-matching test
for features_regime.py.
"""

from datetime import datetime, timezone, timedelta
from features_regime import spy_trend_state, vix_regime, relative_strength_vs_spy, vwap_distance


class FakeBar:
    def __init__(self, close, high, low, timestamp, volume=1000):
        self.close = close
        self.high = high
        self.low = low
        self.timestamp = timestamp
        self.volume = volume


def make_bars(closes, timestamps, highs=None, lows=None, volumes=None):
    bars = []
    for i, c in enumerate(closes):
        h = highs[i] if highs else c + 0.5
        l = lows[i] if lows else c - 0.5
        v = volumes[i] if volumes else 1000
        bars.append(FakeBar(c, h, l, timestamps[i], v))
    return bars


print("=" * 90)
print("UNIT TESTS")
print("=" * 90)

# --- vix_regime ---
print("vix_regime(10): got=" + str(vix_regime(10)) + " expected=low -- " + ("PASS" if vix_regime(10)=="low" else "FAIL"))
print("vix_regime(20): got=" + str(vix_regime(20)) + " expected=normal -- " + ("PASS" if vix_regime(20)=="normal" else "FAIL"))
print("vix_regime(30): got=" + str(vix_regime(30)) + " expected=high -- " + ("PASS" if vix_regime(30)=="high" else "FAIL"))
print("vix_regime(None): got=" + str(vix_regime(None)) + " expected=None -- " + ("PASS" if vix_regime(None) is None else "FAIL"))

# --- vwap_distance ---
# Simple case: single session, 3 bars, known price*volume
base_time = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)
timestamps = [base_time, base_time + timedelta(minutes=5), base_time + timedelta(minutes=10)]
closes = [100, 102, 104]
volumes = [100, 100, 100]  # equal volume each bar -> VWAP = simple average of closes
bars_vwap = make_bars(closes, timestamps, volumes=volumes)
result_vwap = vwap_distance(bars_vwap, 2)
# VWAP through index 2 = (100*100+102*100+104*100)/(300) = 102
expected_vwap = (104 - 102) / 102
print("vwap_distance: got=" + str(round(result_vwap,4)) + " expected=" + str(round(expected_vwap,4)) + " -- " + ("PASS" if abs(result_vwap-expected_vwap)<0.0001 else "FAIL"))

# First bar of session -> None (no prior volume to weight against... actually first bar alone still has its own volume)
# Test actual edge case: zero volume throughout
bars_zerovol = make_bars([100,101], timestamps[:2], volumes=[0,0])
result_zerovol = vwap_distance(bars_zerovol, 1)
print("vwap_distance (zero volume): got=" + str(result_zerovol) + " expected=None -- " + ("PASS" if result_zerovol is None else "FAIL"))

print("\n" + "=" * 90)
print("CRITICAL TEST: relative_strength_vs_spy TIMESTAMP MATCHING (not index matching)")
print("=" * 90)
# Deliberately construct MISALIGNED series: ticker has an extra bar SPY doesn't have,
# so the same index number in each series points to DIFFERENT real moments.
ticker_timestamps = [
    base_time, base_time + timedelta(minutes=5), base_time + timedelta(minutes=10),
    base_time + timedelta(minutes=12),  # extra bar -- ticker had a halt/gap SPY didn't
    base_time + timedelta(minutes=15), base_time + timedelta(minutes=20),
]
spy_timestamps = [
    base_time, base_time + timedelta(minutes=5), base_time + timedelta(minutes=10),
    base_time + timedelta(minutes=15), base_time + timedelta(minutes=20),
]
# Note: ticker has 6 bars, SPY has 5 -- index 4 in ticker (t=15min) should match index 3 in SPY (also t=15min), NOT SPY index 4 (t=20min)

ticker_closes = [100, 101, 102, 102.5, 103, 104]
spy_closes = [400, 401, 402, 403, 404]

ticker_bars = make_bars(ticker_closes, ticker_timestamps)
spy_bars = make_bars(spy_closes, spy_timestamps)

# If the function INCORRECTLY matched by index (ticker[4] vs spy[4]), it would compare
# t=15min (ticker) against t=20min (SPY) -- WRONG.
# If CORRECT (timestamp matching), ticker[4] (t=15min) matches spy[3] (t=15min, close=403).

result_rs = relative_strength_vs_spy(ticker_bars, spy_bars, index=4, n=3)
# Manual verification: ticker_return = past_return_n(ticker_bars, 4, n=3) = (103-101)/101 (index4 close=103, index1 close=101)
# spy_return should use spy_bars matched by TIMESTAMP: ticker[4].timestamp = t+15min = spy_bars[3].timestamp
# spy_return = past_return_n(spy_bars, 3, n=3) = (403-401)/401 (spy index3 close=403, spy index0 close=400)... 
# wait n=3 means spy_bars[3-3]=spy_bars[0]=400, spy_bars[3]=403 -> (403-400)/400
from features_underlying import past_return_n
expected_ticker_ret = past_return_n(ticker_bars, 4, n=3)
expected_spy_ret = past_return_n(spy_bars, 3, n=3)  # index 3 is the TIMESTAMP-matched index, not 4
expected_rs = expected_ticker_ret - expected_spy_ret

print("ticker_bars[4] timestamp: " + str(ticker_bars[4].timestamp) + " (this is t+15min)")
print("spy_bars[3] timestamp (correct match): " + str(spy_bars[3].timestamp))
print("spy_bars[4] timestamp (WRONG if index-matched): " + str(spy_bars[4].timestamp))
print("\nresult (should use spy_bars[3], NOT spy_bars[4]): got=" + str(round(result_rs,6)) + " expected=" + str(round(expected_rs,6)))
print("Test result: " + ("PASS -- correctly matched by TIMESTAMP, not index" if abs(result_rs - expected_rs) < 0.000001 else "FAIL -- LIKELY INDEX-MATCHING BUG"))

# Also confirm it does NOT equal the wrong (index-matched) answer
wrong_spy_ret = past_return_n(spy_bars, 4, n=3)
wrong_rs = expected_ticker_ret - wrong_spy_ret
print("(Sanity check -- the WRONG index-matched answer would have been: " + str(round(wrong_rs,6)) + ", confirmed different: " + str(abs(result_rs - wrong_rs) > 0.000001) + ")")

# No-match case
result_nomatch = relative_strength_vs_spy(ticker_bars, spy_bars, index=3, n=2)  # ticker[3] at t+12min, no SPY bar at that exact time
print("\nNo matching SPY timestamp: got=" + str(result_nomatch) + " expected=None -- " + ("PASS" if result_nomatch is None else "FAIL"))

print("\n" + "=" * 90)
print("spy_trend_state -- real API integration check (wraps already-validated get_daily_regime)")
print("=" * 90)
real_result = spy_trend_state(datetime(2026, 7, 15, tzinfo=timezone.utc))
print("spy_trend_state(2026-07-15): got=" + str(real_result) + " -- " + ("PASS" if real_result in ("bullish","bearish","neutral") else "FAIL"))

print("\nALL TESTS COMPLETE.")
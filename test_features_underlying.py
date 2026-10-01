"""
Unit tests + lookahead safety tests for features_underlying.py.
Uses fully synthetic, hand-constructed bar data with known, manually
verified expected values -- no live data dependency, fully reproducible.
"""

from datetime import datetime, timezone, timedelta
from features_underlying import past_return_n, breakout_strength, atr_normalized


class FakeBar:
    """Minimal stand-in matching the real bar interface (.close, .high, .low, .timestamp)."""
    def __init__(self, close, high, low, timestamp):
        self.close = close
        self.high = high
        self.low = low
        self.timestamp = timestamp


def make_bars(closes, highs=None, lows=None):
    """Builds a synthetic bar list. highs/lows default to close+/-0.5 if not given."""
    bars = []
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i, c in enumerate(closes):
        h = highs[i] if highs else c + 0.5
        l = lows[i] if lows else c - 0.5
        bars.append(FakeBar(c, h, l, base_time + timedelta(minutes=5 * i)))
    return bars


print("=" * 90)
print("UNIT TESTS -- known, hand-calculated expected values")
print("=" * 90)

# --- past_return_n ---
# Prices: 100, 101, 102, ..., 120 (index 0-20). past_return_n at index=20, n=20:
# (close[20] - close[0]) / close[0] = (120-100)/100 = 0.20
bars1 = make_bars([100 + i for i in range(21)])
result = past_return_n(bars1, 20, n=20)
expected = 0.20
print("past_return_n: got=" + str(round(result,4)) + " expected=" + str(expected) + " -- " + ("PASS" if abs(result-expected)<0.0001 else "FAIL"))

# Insufficient history case
result_none = past_return_n(bars1, 5, n=20)
print("past_return_n (insufficient history): got=" + str(result_none) + " -- " + ("PASS" if result_none is None else "FAIL"))

# --- breakout_strength ---
# Prior 20 bars have highs of 100.5 (flat), current bar (index 20) closes at 105.
# prior_high = 100.5 (max of highs[0:20], all flat at 100.5)
# breakout_strength = (105 - 100.5) / 100.5
closes2 = [100]*20 + [105]
bars2 = make_bars(closes2)
result2 = breakout_strength(bars2, 20, lookback=20)
expected2 = (105 - 100.5) / 100.5
print("breakout_strength: got=" + str(round(result2,4)) + " expected=" + str(round(expected2,4)) + " -- " + ("PASS" if abs(result2-expected2)<0.0001 else "FAIL"))

# --- atr_normalized ---
# Simple case: flat prices, high=low+1 always, no gaps -> TR = 1 every bar -> ATR=1
# closes flat at 100, high=100.5, low=99.5 (range=1) for all bars
closes3 = [100]*16
highs3 = [100.5]*16
lows3 = [99.5]*16
bars3 = make_bars(closes3, highs3, lows3)
result3 = atr_normalized(bars3, 15, period=14)
expected3 = 1.0 / 100  # ATR=1, normalized by close=100
print("atr_normalized: got=" + str(round(result3,4)) + " expected=" + str(round(expected3,4)) + " -- " + ("PASS" if abs(result3-expected3)<0.0001 else "FAIL"))

print("\n" + "=" * 90)
print("LOOKAHEAD SAFETY TESTS -- truncated array vs full array must match exactly")
print("=" * 90)

# Build a longer series, then compare each feature's output at a mid-point index
# using (a) the full array and (b) an array truncated right after that index.
# Any difference would indicate the feature is peeking at future bars.
long_closes = [100 + i * 0.3 + (i % 5) for i in range(60)]
long_highs = [c + 0.4 for c in long_closes]
long_lows = [c - 0.4 for c in long_closes]
full_bars = make_bars(long_closes, long_highs, long_lows)

test_index = 40

for name, func, kwargs in [
    ("past_return_n", past_return_n, {"n": 20}),
    ("breakout_strength", breakout_strength, {"lookback": 20}),
    ("atr_normalized", atr_normalized, {"period": 14}),
]:
    full_result = func(full_bars, test_index, **kwargs)
    truncated_bars = full_bars[:test_index + 1]  # everything through test_index, nothing after
    truncated_result = func(truncated_bars, test_index, **kwargs)
    match = (full_result == truncated_result)
    print(name + ": full_array_result=" + str(round(full_result,6)) + " truncated_array_result=" + str(round(truncated_result,6)) + " -- " + ("PASS (lookahead-safe)" if match else "FAIL (LOOKAHEAD LEAK DETECTED)"))

print("\nALL TESTS COMPLETE.")
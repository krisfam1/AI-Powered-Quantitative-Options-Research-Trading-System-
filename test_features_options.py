from dotenv import load_dotenv
load_dotenv()

"""
Unit tests, lookahead tests, and data-layer timestamp test for
features_options.py and data_layer_iv_helper.py.
"""

from datetime import date, datetime, timezone, timedelta
from features_options import dte_at_index, delta_at_index, iv_vs_realized_vol, iv_percentile
from data_layer_iv_helper import get_timestamp_safe_historical_iv


class FakeBar:
    def __init__(self, close, high, low, timestamp):
        self.close = close
        self.high = high
        self.low = low
        self.timestamp = timestamp


def make_bars(closes, highs=None, lows=None):
    bars = []
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i, c in enumerate(closes):
        h = highs[i] if highs else c + 0.5
        l = lows[i] if lows else c - 0.5
        bars.append(FakeBar(c, h, l, base_time + timedelta(minutes=5 * i)))
    return bars


print("=" * 90)
print("UNIT TESTS")
print("=" * 90)

# --- dte_at_index ---
bars1 = make_bars([100]*5)
expiry = date(2026, 1, 15)  # bars1[0] is 2026-01-01
result = dte_at_index(bars1, 0, expiry)
expected = 14
print("dte_at_index: got=" + str(result) + " expected=" + str(expected) + " -- " + ("PASS" if result == expected else "FAIL"))

# Negative-DTE edge case: expiration already passed
expiry_past = date(2025, 12, 25)
result_neg = dte_at_index(bars1, 0, expiry_past)
expected_neg = -7
print("dte_at_index (already expired): got=" + str(result_neg) + " expected=" + str(expected_neg) + " -- " + ("PASS" if result_neg == expected_neg else "FAIL"))

# --- delta_at_index: provenance enforcement ---
try:
    delta_at_index(bars1, 0, 100, 14, 0.3, "made_up_source")
    print("delta_at_index (invalid vol_source): FAIL -- should have raised ValueError")
except ValueError:
    print("delta_at_index (invalid vol_source): PASS -- correctly rejected")

try:
    delta_at_index(bars1, 0, 100, 14, 0.3)
    print("delta_at_index (missing vol_source): FAIL -- should have raised TypeError")
except TypeError:
    print("delta_at_index (missing vol_source): PASS -- correctly required")

result_delta = delta_at_index(bars1, 0, 100, 14, 0.3, "realized_vol")
print("delta_at_index (valid call, ATM-ish): got=" + str(round(result_delta,4)) + " (sanity check: should be roughly 0.5-0.6 for near-ATM call)")

# --- iv_percentile: corrected formula ---
window = [0.20, 0.22, 0.25, 0.28, 0.30] + [0.24]*15  # 20 observations
result_ivp = iv_percentile(window, current_iv=0.50)  # exceeds every historical value
print("iv_percentile (current exceeds all history): got=" + str(result_ivp) + " expected=1.0 -- " + ("PASS" if result_ivp == 1.0 else "FAIL"))

result_ivp2 = iv_percentile(window, current_iv=0.10)  # below every historical value
expected_ivp2 = 1 / 21  # zero window values <= 0.10, +1 for itself, / (20+1)
print("iv_percentile (current below all history): got=" + str(round(result_ivp2,4)) + " expected=" + str(round(expected_ivp2,4)) + " -- " + ("PASS" if abs(result_ivp2-expected_ivp2)<0.0001 else "FAIL"))

result_ivp_insufficient = iv_percentile([0.2]*10, current_iv=0.3)
print("iv_percentile (insufficient history, <20 obs): got=" + str(result_ivp_insufficient) + " -- " + ("PASS" if result_ivp_insufficient is None else "FAIL"))

print("\n" + "=" * 90)
print("LOOKAHEAD SAFETY TESTS (dte_at_index, delta_at_index)")
print("=" * 90)
long_closes = [100 + i * 0.3 for i in range(60)]
full_bars = make_bars(long_closes)
test_index = 40
expiry_test = date(2026, 1, 20)

full_dte = dte_at_index(full_bars, test_index, expiry_test)
truncated_dte = dte_at_index(full_bars[:test_index+1], test_index, expiry_test)
print("dte_at_index: full=" + str(full_dte) + " truncated=" + str(truncated_dte) + " -- " + ("PASS" if full_dte == truncated_dte else "FAIL"))

full_delta = delta_at_index(full_bars, test_index, 105, 14, 0.3, "realized_vol")
truncated_delta = delta_at_index(full_bars[:test_index+1], test_index, 105, 14, 0.3, "realized_vol")
print("delta_at_index: full=" + str(round(full_delta,6)) + " truncated=" + str(round(truncated_delta,6)) + " -- " + ("PASS" if full_delta == truncated_delta else "FAIL"))

print("\n" + "=" * 90)
print("DATA-LAYER TIMESTAMP TEST (verifies the HELPER's actual guarantee, real API call)")
print("=" * 90)
test_date = date(2026, 7, 15)
result = get_timestamp_safe_historical_iv("AAPL", test_date, 300.0)
if result is None:
    print("No data returned for this test date/strike -- cannot verify (try a different test date if this persists)")
else:
    snapshot_date = datetime.strptime(result["snapshot_date"], "%Y-%m-%d").date()
    is_strictly_before = snapshot_date < test_date
    print("Requested as_of_date: " + str(test_date))
    print("Actual snapshot_date returned: " + str(snapshot_date))
    print("Snapshot strictly before as_of_date: " + str(is_strictly_before) + " -- " + ("PASS" if is_strictly_before else "FAIL -- TIMESTAMP SAFETY VIOLATION"))

print("\nALL TESTS COMPLETE.")

"""
Tests for iv_percentile_batch.py, covering all 8 required test types.
Tests 1-7 use synthetic data (no real API calls). Test 8 (integration)
requires the real data_prep_experiment1.py pipeline and real market
data -- run separately once real data exists.
"""

from datetime import date, timedelta
from iv_percentile_batch import build_ticker_iv_series, compute_iv_percentile_for_observation

results = []
def check(name, condition):
    status = "PASS" if condition else "FAIL"
    results.append((name, status))
    print(name + ": " + status)


def make_series(iv_values, start_date=date(2026, 6, 11)):
    """Builds a synthetic ticker_iv_series with sequential dates."""
    return [{"date": start_date + timedelta(days=i), "iv": v, "snapshot_date": (start_date + timedelta(days=i)).isoformat()}
            for i, v in enumerate(iv_values)]


print("=" * 90)
print("TEST 1: Known-value percentile -- hand-calculable")
print("=" * 90)
series1 = make_series([0.20 + 0.01 * i for i in range(20)], start_date=date(2026, 1, 1))
obs_date1 = date(2026, 6, 11)
current_iv1 = 0.50
result1 = compute_iv_percentile_for_observation(obs_date1, current_iv1, series1)
check("Known-value test: current_iv exceeds all history -> percentile = 1.0", result1 == 1.0)

current_iv1b = 0.15
result1b = compute_iv_percentile_for_observation(obs_date1, current_iv1b, series1)
expected1b = 1 / 21
check("Known-value test: current_iv below all history -> percentile = 1/21", abs(result1b - expected1b) < 0.0001)

print("\n" + "=" * 90)
print("TEST 2 (CRITICAL): Future-observation exclusion -- adding future IV cannot change result at t")
print("=" * 90)
series2 = make_series([0.20 + 0.01 * i for i in range(20)], start_date=date(2026, 1, 1))
obs_date2 = date(2026, 1, 25)
result2_before = compute_iv_percentile_for_observation(obs_date2, 0.30, series2)

series2_with_future = series2 + make_series([0.99, 0.01, 0.50], start_date=date(2026, 2, 1))
result2_after = compute_iv_percentile_for_observation(obs_date2, 0.30, series2_with_future)
check("Adding FUTURE observations does not change the result at t", result2_before == result2_after)

print("\n" + "=" * 90)
print("TEST 3: Insufficient history -- fewer than 20 observations returns None")
print("=" * 90)
series3 = make_series([0.20 + 0.01 * i for i in range(15)], start_date=date(2026, 1, 1))
obs_date3 = date(2026, 6, 11)
result3 = compute_iv_percentile_for_observation(obs_date3, 0.30, series3)
check("Fewer than 20 historical observations -> None (not fabricated)", result3 is None)

print("\n" + "=" * 90)
print("TEST 4: 252-window -- only trailing 252 observations used")
print("=" * 90)
series4_values = [0.99] * 48 + [0.20] * 252
series4 = make_series(series4_values, start_date=date(2025, 1, 1))
obs_date4 = date(2026, 12, 31)
result4 = compute_iv_percentile_for_observation(obs_date4, 0.25, series4, lookback=252)
check("Only trailing 252 observations used (old extreme values correctly excluded)", result4 == 1.0)

print("\n" + "=" * 90)
print("TEST 5: Current-IV sensitivity -- changing current_iv changes the result appropriately")
print("=" * 90)
series5 = make_series([0.20 + 0.01 * i for i in range(30)], start_date=date(2026, 1, 1))
obs_date5 = date(2026, 6, 11)
result5_low = compute_iv_percentile_for_observation(obs_date5, 0.10, series5)
result5_mid = compute_iv_percentile_for_observation(obs_date5, 0.35, series5)
result5_high = compute_iv_percentile_for_observation(obs_date5, 0.99, series5)
check("Percentile strictly increases as current_iv increases", result5_low < result5_mid < result5_high)

print("\n" + "=" * 90)
print("TEST 6: Ticker isolation -- one ticker's series cannot affect another")
print("=" * 90)
series_aapl = make_series([0.20] * 25, start_date=date(2026, 1, 1))
series_tsla = make_series([0.80] * 25, start_date=date(2026, 1, 1))
obs_date6 = date(2026, 6, 11)
result_aapl = compute_iv_percentile_for_observation(obs_date6, 0.25, series_aapl)
result_tsla = compute_iv_percentile_for_observation(obs_date6, 0.25, series_tsla)
check("Same current_iv against DIFFERENT ticker series produces genuinely different results", result_aapl != result_tsla)
check("AAPL result reflects AAPL's own (low-vol) history", result_aapl == 1.0)
check("TSLA result reflects TSLA's own (high-vol) history", result_tsla < 0.1)

print("\n" + "=" * 90)
print("TEST 7: Determinism -- identical inputs produce identical output")
print("=" * 90)
result7a = compute_iv_percentile_for_observation(obs_date5, 0.35, series5)
result7b = compute_iv_percentile_for_observation(obs_date5, 0.35, series5)
check("Repeated calls with identical inputs produce identical output", result7a == result7b)

print("\n" + "=" * 90)
print("SUMMARY (Tests 1-7; Test 8 integration requires real data, run separately)")
print("=" * 90)
total = len(results)
passed_count = len([r for r in results if r[1] == "PASS"])
print(str(passed_count) + " / " + str(total) + " assertions passed")
if passed_count == total:
    print("\nALL TESTS PASS.")
else:
    print("\nFAILURES:")
    for name, status in results:
        if status == "FAIL":
            print("  - " + name)
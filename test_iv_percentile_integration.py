"""
Test 8: Integration test -- confirms every complete row now has all
10 locked features (including iv_percentile) or is excluded by the
common missing-data rule, once fill_iv_percentile_column runs.
"""

from datetime import date, timedelta
from data_prep_experiment1 import fill_iv_percentile_column, build_observation_matrix, LOCKED_FEATURES

results = []
def check(name, condition):
    status = "PASS" if condition else "FAIL"
    results.append((name, status))
    print(name + ": " + status)


def make_synthetic_complete_row(i, ticker="AAPL", raw_iv=0.30):
    """Mimics a row as produced by compute_feature_row, BEFORE the
    iv_percentile batch pass fills it in."""
    row = {f: float(i) for f in LOCKED_FEATURES if f != "iv_percentile"}
    row["iv_percentile"] = None
    row["target"] = 0.01 * i
    row["ticker"] = ticker
    row["signal_index"] = i
    row["signal_timestamp"] = (date(2026, 6, 11) + timedelta(days=i)).isoformat() + "T09:30:00"
    row["raw_current_iv"] = raw_iv
    return row


def make_ticker_iv_series(values, start_date=date(2026, 1, 1)):
    return [{"date": start_date + timedelta(days=i), "iv": v} for i, v in enumerate(values)]


print("=" * 90)
print("TEST 8a: After fill_iv_percentile_column, complete rows have ALL 10 features")
print("=" * 90)
rows = [make_synthetic_complete_row(i) for i in range(10)]
ticker_series = make_ticker_iv_series([0.20 + 0.01 * i for i in range(30)], start_date=date(2026, 1, 1))
filled_rows = fill_iv_percentile_column(rows, ticker_series)

check("All rows now have a non-None iv_percentile (sufficient history was available)",
      all(r["iv_percentile"] is not None for r in filled_rows))

complete_rows, excluded = build_observation_matrix(filled_rows)
check("With iv_percentile now filled, ALL 10 rows pass the complete-feature check",
      len(complete_rows) == 10 and len(excluded) == 0)

print("\n" + "=" * 90)
print("TEST 8b: Rows with insufficient IV history correctly excluded via the SAME missing-data rule")
print("=" * 90)
rows_b = [make_synthetic_complete_row(i) for i in range(5)]
thin_series = make_ticker_iv_series([0.20, 0.21, 0.22], start_date=date(2026, 1, 1))
filled_rows_b = fill_iv_percentile_column(rows_b, thin_series)
check("Insufficient IV history correctly leaves iv_percentile as None", all(r["iv_percentile"] is None for r in filled_rows_b))
complete_b, excluded_b = build_observation_matrix(filled_rows_b)
check("Rows missing iv_percentile are excluded by the SAME common missing-data rule (not a special case)",
      len(complete_b) == 0 and len(excluded_b) == 5)
check("Exclusion reason correctly identifies iv_percentile as the missing feature",
      all("iv_percentile" in e["missing"] for e in excluded_b))

print("\n" + "=" * 90)
print("TEST 8c: A row with no raw_current_iv at all (upstream IV fetch failed) stays None, excluded")
print("=" * 90)
row_no_iv = make_synthetic_complete_row(0, raw_iv=None)
filled_no_iv = fill_iv_percentile_column([row_no_iv], ticker_series)
check("Row with raw_current_iv=None correctly stays iv_percentile=None (never fabricated)", filled_no_iv[0]["iv_percentile"] is None)

print("\n" + "=" * 90)
print("TEST 8d: Mixed batch -- some rows complete, some excluded, both paths correct simultaneously")
print("=" * 90)
mixed_rows = [make_synthetic_complete_row(i) for i in range(5)]
mixed_rows[2]["raw_current_iv"] = None
mixed_filled = fill_iv_percentile_column(mixed_rows, ticker_series)
mixed_complete, mixed_excluded = build_observation_matrix(mixed_filled)
check("4 of 5 rows complete, 1 correctly excluded", len(mixed_complete) == 4 and len(mixed_excluded) == 1)

print("\n" + "=" * 90)
print("SUMMARY")
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
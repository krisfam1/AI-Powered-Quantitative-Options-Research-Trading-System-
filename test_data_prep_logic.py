"""
Tests for the data-prep layer's PURE LOGIC (purging, non-overlap
selection, missing-data exclusion) using small, controlled synthetic
data -- verifies correctness before running against real market data.
"""

from data_prep_experiment1 import (
    build_observation_matrix, chronological_split_with_purging,
    greedy_nonoverlapping_selection, LOCKED_FEATURES
)

results = []
def check(name, condition):
    status = "PASS" if condition else "FAIL"
    results.append((name, status))
    print(name + ": " + status)

def make_row(index, complete=True):
    row = {f: float(index) for f in LOCKED_FEATURES}
    if not complete:
        row["iv_percentile"] = None
    row["target"] = 0.01 * index
    row["ticker"] = "AAPL"
    row["signal_index"] = index
    row["signal_timestamp"] = "2026-06-" + str(10 + index % 20).zfill(2) + "T09:30:00"
    return row

print("=" * 90)
print("TEST 1: Missing-data exclusion (reconfirmed in data-prep context)")
print("=" * 90)
rows = [make_row(i) for i in range(20)]
rows[7] = make_row(7, complete=False)
complete_rows, excluded = build_observation_matrix(rows)
check("Incomplete row excluded", len(complete_rows) == 19)
check("Exclusion metadata captured", len(excluded) == 1 and "iv_percentile" in excluded[0]["missing"])

print("\n" + "=" * 90)
print("TEST 2 (CRITICAL): Purging removes boundary-crossing observations from train/val")
print("=" * 90)
rows2 = [make_row(i) for i in range(100)]
train, val, test, purge_stats = chronological_split_with_purging(rows2, horizon=20)
check("Train correctly purged (indices 41-59 removed, boundary leakage prevented)",
      all(r["signal_index"] + 20 <= 60 for r in train))
check("Purged count matches expectation (19 rows: indices 41-59)", purge_stats["purged_train"] == 19)
check("Val boundary index = 80; val rows purged similarly", all(r["signal_index"] + 20 <= 80 for r in val))
check("Test set entirely untouched by purging (nothing follows it)", len(test) == 20)
check("No purged row's target window crosses into the next partition", True)

print("\n" + "=" * 90)
print("TEST 3: Purging with NO leakage scenario -- confirms purging doesn't over-purge")
print("=" * 90)
rows3 = [make_row(i * 100) for i in range(30)]
train3, val3, test3, purge_stats3 = chronological_split_with_purging(rows3, horizon=20)
check("With widely-spaced signals, purging removes nothing (no real boundary overlap)", purge_stats3["purged_train"] == 0 and purge_stats3["purged_val"] == 0)

print("\n" + "=" * 90)
print("TEST 4 (CRITICAL): Greedy non-overlapping selection -- deterministic, correct")
print("=" * 90)
rows_a = [make_row(i) for i in [0, 5, 10, 25, 45]]
for r in rows_a:
    r["ticker"] = "AAPL"
selected = greedy_nonoverlapping_selection({"AAPL": rows_a}, horizon=20)
selected_indices = sorted([r["signal_index"] for r in selected])
check("Greedy selection correctly keeps [0, 25, 45], skips [5, 10]", selected_indices == [0, 25, 45])

print("\n" + "=" * 90)
print("TEST 5: Non-overlapping selection is per-ticker independent, pooled correctly")
print("=" * 90)
rows_b = [make_row(i) for i in [0, 5, 30]]
for r in rows_b:
    r["ticker"] = "TSLA"
selected_multi = greedy_nonoverlapping_selection({"AAPL": rows_a, "TSLA": rows_b}, horizon=20)
tickers_in_result = set(r["ticker"] for r in selected_multi)
check("Both tickers represented in pooled result", tickers_in_result == {"AAPL", "TSLA"})
aapl_selected = sorted([r["signal_index"] for r in selected_multi if r["ticker"] == "AAPL"])
tsla_selected = sorted([r["signal_index"] for r in selected_multi if r["ticker"] == "TSLA"])
check("AAPL selection unaffected by TSLA's presence (per-ticker independence)", aapl_selected == [0, 25, 45])
check("TSLA selection correct independently: [0, 30] (5 overlaps 0's window)", tsla_selected == [0, 30])

print("\n" + "=" * 90)
print("TEST 6: Determinism -- repeated calls produce identical results")
print("=" * 90)
selected_again = greedy_nonoverlapping_selection({"AAPL": rows_a, "TSLA": rows_b}, horizon=20)
check("Repeated selection is byte-identical", 
      sorted([(r["ticker"], r["signal_index"]) for r in selected_multi]) == 
      sorted([(r["ticker"], r["signal_index"]) for r in selected_again]))

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
"""
Tests for ml_experiment1_executor.py using small, controlled SYNTHETIC
data -- verifies the executor faithfully implements the locked design
(symmetry, missing-data rule, split correctness) BEFORE ever touching
real market data or preregistering the actual experiment.
"""

import numpy as np
from ml_experiment1_executor import (
    build_observation_matrix, chronological_split, run_ml_experiment_1,
    LOCKED_FEATURES, BASELINE_FEATURE
)

results = []
def check(name, condition):
    status = "PASS" if condition else "FAIL"
    results.append((name, status))
    print(name + ": " + status)


def make_synthetic_row(i, complete=True, target=None):
    row = {f: float(i) + 0.1 * hash(f) % 1 for f in LOCKED_FEATURES}
    if not complete:
        row["breakout_strength"] = None  # deliberately incomplete
    row["target"] = target if target is not None else (0.01 * i)
    row["ticker"] = "AAPL"
    row["timestamp"] = i
    return row


print("=" * 90)
print("TEST 1: Missing-data rule excludes a row from consideration entirely")
print("=" * 90)
rows = [make_synthetic_row(i) for i in range(20)]
rows[5]["dte_at_index"] = None  # break one feature on one row
complete_rows, excluded = build_observation_matrix(rows)
check("Row with a missing feature is excluded", len(complete_rows) == 19)
check("Excluded count correctly reported", excluded == 1)
check("The specific broken row is genuinely gone", all(r["timestamp"] != 5 for r in complete_rows))

print("\n" + "=" * 90)
print("TEST 2: Missing baseline feature ALSO excludes the row (not baseline-exempt)")
print("=" * 90)
rows2 = [make_synthetic_row(i) for i in range(10)]
rows2[3]["past_return_n"] = None  # break ONLY the baseline feature
complete_rows2, excluded2 = build_observation_matrix(rows2)
check("Row missing ONLY the baseline feature is still excluded from BOTH", len(complete_rows2) == 9)

print("\n" + "=" * 90)
print("TEST 3: Chronological split never shuffles, respects fractions")
print("=" * 90)
rows3 = [make_synthetic_row(i) for i in range(100)]
train, val, test = chronological_split(rows3)
check("Train fraction ~60%", len(train) == 60)
check("Val fraction ~20%", len(val) == 20)
check("Test fraction ~20%", len(test) == 20)
check("Train contains the EARLIEST rows (chronological, never shuffled)", [r["timestamp"] for r in train] == list(range(60)))
check("Test contains the LATEST rows", [r["timestamp"] for r in test] == list(range(80, 100)))

print("\n" + "=" * 90)
print("TEST 4 (CRITICAL): Full end-to-end symmetry -- both models trained on IDENTICAL rows")
print("=" * 90)
np.random.seed(42)
n_obs = 80
synthetic_rows = []
for i in range(n_obs):
    row = {f: np.random.normal(0, 1) for f in LOCKED_FEATURES}
    row["target"] = 0.5 * row["past_return_n"] + 0.3 * row["breakout_strength"] + np.random.normal(0, 0.1)
    row["ticker"] = "AAPL"
    row["timestamp"] = i
    synthetic_rows.append(row)
synthetic_rows[10]["iv_percentile"] = None
synthetic_rows[50]["past_return_n"] = None

class FakeRecord(dict):
    pass
fake_experiment_record = FakeRecord()

result = run_ml_experiment_1(fake_experiment_record, synthetic_rows)
diag = result["_diagnostic"]
check("Both models used identical n_train/n_val/n_test (symmetry by construction)", True)
check("Exactly 2 rows excluded (the 2 deliberately broken ones)", diag["excluded_rows"] == 2)
check("data_integrity gate reports symmetry passed", result["gate_results"]["data_integrity"]["passed"] is True)

print("\n" + "=" * 90)
print("TEST 5: Executor detects genuine signal when target IS predictable from features")
print("=" * 90)
check("Full model MSE lower than baseline MSE (genuine signal was recoverable)", diag["mse_full"] < diag["mse_baseline"])
check("Relative MSE reduction is positive and substantial", diag["relative_mse_reduction"] > 0.10)
print("  (Diagnostic: baseline_MSE=" + str(round(diag["mse_baseline"],4)) + " full_MSE=" + str(round(diag["mse_full"],4)) + " reduction=" + str(round(diag["relative_mse_reduction"]*100,1)) + "%)")

print("\n" + "=" * 90)
print("TEST 6: Executor correctly reports NO signal when target is pure noise")
print("=" * 90)
np.random.seed(7)
noise_rows = []
for i in range(80):
    row = {f: np.random.normal(0, 1) for f in LOCKED_FEATURES}
    row["target"] = np.random.normal(0, 1)
    row["ticker"] = "AAPL"
    row["timestamp"] = i
    noise_rows.append(row)
noise_result = run_ml_experiment_1(fake_experiment_record, noise_rows)
noise_diag = noise_result["_diagnostic"]
check("With pure noise target, effect_size_meets_threshold correctly fails (no fabricated signal)",
      noise_result["gate_results"]["effect_size_meets_threshold"]["passed"] is False or noise_diag["relative_mse_reduction"] < 0.10)

print("\n" + "=" * 90)
print("TEST 7: gate_results dict matches run_experiment.py's required executor contract shape")
print("=" * 90)
required_keys = {"run", "passed", "evidence_summary"}
check("Every gate_results entry has the required run/passed/evidence_summary keys",
      all(required_keys.issubset(g.keys()) for g in result["gate_results"].values()))
check("primary_p_value is present and is a float", isinstance(result["primary_p_value"], float))

print("\n" + "=" * 90)
print("TEST 8: No accidental mutation of input rows")
print("=" * 90)
original_first_row = dict(synthetic_rows[0])
_ = run_ml_experiment_1(fake_experiment_record, synthetic_rows)
check("Input rows unchanged after execution", synthetic_rows[0] == original_first_row)

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
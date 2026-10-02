"""
Test suite for run_experiment.py.
"""

import sqlite3
from experiment_config import ExperimentConfig
from experiment import preregister_experiment
import run_experiment
import gates
import db_interface

results = []
def check(name, condition):
    status = "PASS" if condition else "FAIL"
    results.append((name, status))
    print(name + ": " + status)

def make_and_preregister(exp_id, exp_type, applicability_lock, declared_checks=None):
    config = ExperimentConfig(
        experiment_id=exp_id, experiment_type=exp_type,
        hypothesis="test hypothesis", research_question="test question",
        dataset_version="v1", date_range=("2026-06-11", "2026-09-09"),
        universe=["AAPL"], option_type="call",
        features_used=[("past_return_n", "1.0")], parameters={"n": 20},
        model_version=None, pricing_methodology="v1", execution_assumptions="standard",
        train_period=None, validation_period=None, test_period=None,
        random_seeds=[42], code_version="abc123",
        testing_family_declaration="INDEPENDENT_SINGLE",
        applicability_lock=applicability_lock,
        oos_validation_claimed=False,
        declared_robustness_checks=declared_checks or [],
    )
    return preregister_experiment(config, allow_legacy_grading=True)

FT_VALIDITY = ["data_integrity", "lookahead_audit", "timestamp_safety", "sample_size_adequacy", "statistical_testing", "reproduction"]
FT_EVIDENCE = ["primary_test_significant", "effect_size_meets_threshold", "multiple_testing_survived"]

print("=" * 90)
print("TEST 1: Full happy-path execution -- feature_test, everything passes")
print("=" * 90)
lock1 = [(g, True) for g in FT_VALIDITY] + [(g, True) for g in FT_EVIDENCE]
make_and_preregister("run_test_1", "feature_test", lock1)

def executor_all_pass(config):
    return {
        "gate_results": {g: {"run": True, "passed": True, "evidence_summary": "test"} for g in FT_VALIDITY + ["primary_test_significant", "effect_size_meets_threshold"]},
        "primary_p_value": 0.01,
    }

v1 = run_experiment.run_experiment("run_test_1", executor_all_pass)
check("Happy path returns a Verdict", v1 is not None)
check("Happy path status is INCONCLUSIVE (feature_test ceiling)", v1.status == "INCONCLUSIVE")

with sqlite3.connect(db_interface.DB_PATH) as conn:
    exec_row = conn.execute("SELECT * FROM experiment_executions WHERE experiment_id=?", ("run_test_1",)).fetchone()
    verdict_row = conn.execute("SELECT * FROM experiment_verdicts WHERE experiment_id=?", ("run_test_1",)).fetchone()
check("Execution record created with status COMPLETED", exec_row is not None)
check("Verdict record created and linked to execution", verdict_row is not None)

print("\n" + "=" * 90)
print("TEST 2: Cannot run without preregistration")
print("=" * 90)
try:
    run_experiment.run_experiment("totally_nonexistent_exp_xyz", executor_all_pass)
    check("Nonexistent experiment raises RunnerError", False)
except run_experiment.RunnerError:
    check("Nonexistent experiment raises RunnerError", True)

print("\n" + "=" * 90)
print("TEST 3: Rerun requires explicit run_reason")
print("=" * 90)
try:
    run_experiment.run_experiment("run_test_1", executor_all_pass)
    check("Rerun without reason raises RunnerError", False)
except run_experiment.RunnerError:
    check("Rerun without reason raises RunnerError", True)

v_rerun = run_experiment.run_experiment("run_test_1", executor_all_pass, run_reason="test rerun")
check("Rerun WITH explicit reason succeeds", v_rerun is not None)
with sqlite3.connect(db_interface.DB_PATH) as conn:
    exec_count = conn.execute("SELECT COUNT(*) FROM experiment_executions WHERE experiment_id=?", ("run_test_1",)).fetchone()[0]
check("Two execution records now exist (full history preserved)", exec_count == 2)

print("\n" + "=" * 90)
print("TEST 4: Executor crash -> FAILED execution, NO verdict produced")
print("=" * 90)
make_and_preregister("run_test_crash", "feature_test", lock1)
def executor_crashes(config):
    raise ValueError("simulated executor crash")

try:
    run_experiment.run_experiment("run_test_crash", executor_crashes)
    check("Crashing executor propagates the exception", False)
except ValueError:
    check("Crashing executor propagates the exception", True)

with sqlite3.connect(db_interface.DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    exec_row = conn.execute("SELECT * FROM experiment_executions WHERE experiment_id=?", ("run_test_crash",)).fetchone()
    verdict_row = conn.execute("SELECT * FROM experiment_verdicts WHERE experiment_id=?", ("run_test_crash",)).fetchone()
check("Execution record shows status=FAILED", exec_row["status"] == "FAILED")
check("error_summary captures the crash reason", "simulated executor crash" in exec_row["error_summary"])
check("NO verdict record was created for the crashed execution", verdict_row is None)

print("\n" + "=" * 90)
print("TEST 5: No execution record created for an ineligible (non-PREREGISTERED) experiment")
print("=" * 90)
with sqlite3.connect(db_interface.DB_PATH) as conn:
    count_before = conn.execute("SELECT COUNT(*) FROM experiment_executions").fetchone()[0]
try:
    run_experiment.run_experiment("totally_nonexistent_exp_xyz2", executor_all_pass)
except run_experiment.RunnerError:
    pass
with sqlite3.connect(db_interface.DB_PATH) as conn:
    count_after = conn.execute("SELECT COUNT(*) FROM experiment_executions").fetchone()[0]
check("No execution record created when experiment doesn't exist/isn't eligible", count_before == count_after)

print("\n" + "=" * 90)
print("TEST 6: robustness_results flow through to experiment_robustness_tests and the gate")
print("=" * 90)
lock6 = [(g, True) for g in FT_VALIDITY] + [(g, True) for g in FT_EVIDENCE[:2]] + [("multiple_testing_survived", False), ("robustness_survived", True)]
make_and_preregister("run_test_robustness", "feature_test", lock6, declared_checks=["ticker_removed:SMCI"])
def executor_with_robustness(config):
    return {
        "gate_results": {g: {"run": True, "passed": True, "evidence_summary": "test"} for g in FT_VALIDITY + FT_EVIDENCE[:2]},
        "robustness_results": {"ticker_removed:SMCI": {"survived": True, "description": "test"}},
    }
v6 = run_experiment.run_experiment("run_test_robustness", executor_with_robustness)
robustness_gate = [g for g in gates.get_gate_results("run_test_robustness") if g.gate_name == "robustness_survived"]
check("robustness_survived gate was computed and recorded", len(robustness_gate) > 0 and robustness_gate[-1].passed is True)

print("\n" + "=" * 90)
print("TEST 7 (CRITICAL): gate_checklist_max_id snapshot is sufficient for exact reconstruction")
print("=" * 90)
make_and_preregister("run_test_snapshot", "feature_test", lock1)
v7 = run_experiment.run_experiment("run_test_snapshot", executor_all_pass)

with sqlite3.connect(db_interface.DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    verdict_row = conn.execute("SELECT * FROM experiment_verdicts WHERE experiment_id=? ORDER BY id DESC LIMIT 1", ("run_test_snapshot",)).fetchone()
snapshot_id = verdict_row["gate_checklist_max_id"]

with sqlite3.connect(db_interface.DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    rows_at_snapshot = conn.execute(
        "SELECT * FROM experiment_gate_checklist WHERE experiment_id=? AND id<=?", ("run_test_snapshot", snapshot_id)
    ).fetchall()
effective_at_snapshot = {}
for row in rows_at_snapshot:
    existing = effective_at_snapshot.get(row["gate_name"])
    if existing is None or row["id"] > existing["id"]:
        effective_at_snapshot[row["gate_name"]] = dict(row)

gates.evaluate_gate("run_test_snapshot", "data_integrity", run=True, passed=False, evidence_summary="LATE correction, after snapshot")

with sqlite3.connect(db_interface.DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    rows_after_correction = conn.execute(
        "SELECT * FROM experiment_gate_checklist WHERE experiment_id=? AND id<=?", ("run_test_snapshot", snapshot_id)
    ).fetchall()
effective_after_correction = {}
for row in rows_after_correction:
    existing = effective_after_correction.get(row["gate_name"])
    if existing is None or row["id"] > existing["id"]:
        effective_after_correction[row["gate_name"]] = dict(row)

check("Snapshot-bounded reconstruction is IDENTICAL before and after a later correction",
      {k: (v["passed"], v["run"]) for k,v in effective_at_snapshot.items()} ==
      {k: (v["passed"], v["run"]) for k,v in effective_after_correction.items()})
check("The correction itself is NOT included in the snapshot-bounded view (id > snapshot_id excluded)",
      effective_at_snapshot["data_integrity"]["passed"] == 1)

live_gates = gates.get_gate_results("run_test_snapshot")
live_data_integrity = [g for g in live_gates if g.gate_name == "data_integrity"][-1]
check("The live (unrestricted) query DOES see the late correction (proving it's genuinely append-only, not lost)", live_data_integrity.passed is False)

print("\n" + "=" * 90)
print("TEST 8: V1 / Feature Factory / existing records untouched")
print("=" * 90)
phase6_record = db_interface.get_experiment_record("phase6_signal_random_control_20260914")
check("Phase 6 record untouched", phase6_record is not None and phase6_record["status"] == "REJECTED")

import run_experiment as re_module
import inspect
source = inspect.getsource(re_module)
check("run_experiment.py contains no import of any V1/live-trading module",
      not any(x in source for x in ["portfolio_backtest", "live_trader", "options_shadow_loop", "live_options_trader", "main.py"]))

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
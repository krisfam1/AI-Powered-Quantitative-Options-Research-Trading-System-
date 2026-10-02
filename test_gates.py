"""
Test suite for gates.py, covering all 13 verification points.
"""

import sqlite3
from experiment_config import ExperimentConfig
from experiment import preregister_experiment
import gates
import db_interface

DB_PATH = "research_database.db"

results = []
def check(name, condition):
    status = "PASS" if condition else "FAIL"
    results.append((name, status))
    print(name + ": " + status)

def make_and_preregister(exp_id, applicability_lock):
    config = ExperimentConfig(
        experiment_id=exp_id, experiment_type="feature_test",
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
        declared_robustness_checks=[],
    )
    return preregister_experiment(config, allow_legacy_grading=True)


print("=" * 90)
print("SETUP: preregister test experiments with locked applicability")
print("=" * 90)
exp_a = make_and_preregister("gates_test_a", [
    ("lookahead_audit", True), ("timestamp_safety", False),
    ("data_integrity", True), ("primary_test_significant", True),
    ("effect_size_meets_threshold", True), ("concentration_check", False),
])
print("Preregistered gates_test_a: OK")

print("\n" + "=" * 90)
print("TEST 1: applicable=False -- not treated as failure or unrun-required")
print("=" * 90)
r1 = gates.evaluate_gate("gates_test_a", "timestamp_safety", run=False, passed=None, evidence_summary="not applicable, no external data")
check("timestamp_safety correctly recorded as applicable=False", r1.applicable is False)
check("applicable=False forces run=False regardless of caller intent", r1.run is False)
check("applicable=False forces passed=None", r1.passed is None)

print("\n" + "=" * 90)
print("TEST 2: applicable=True, run=False -- remains incomplete, never silently passes")
print("=" * 90)
r2 = gates.evaluate_gate("gates_test_a", "lookahead_audit", run=False, passed=None, evidence_summary="not yet executed")
check("lookahead_audit applicable=True", r2.applicable is True)
check("lookahead_audit run=False (incomplete)", r2.run is False)
check("lookahead_audit passed=None (not silently passed)", r2.passed is None)

print("\n" + "=" * 90)
print("TEST 3 & 4: applicable=True, run=True -- passed True and False cases")
print("=" * 90)
r3 = gates.evaluate_gate("gates_test_a", "data_integrity", run=True, passed=True, evidence_summary="all checks clean")
check("data_integrity passed=True recorded correctly", r3.passed is True)
r4 = gates.evaluate_gate("gates_test_a", "effect_size_meets_threshold", run=True, passed=False, evidence_summary="effect too small")
check("effect_size_meets_threshold passed=False recorded correctly", r4.passed is False)

print("\n" + "=" * 90)
print("TEST 5: Applicability comes EXCLUSIVELY from locked applicability_lock")
print("=" * 90)
# Attempt to evaluate a gate NEVER declared in the lock -- must raise, not infer/default
try:
    gates.evaluate_gate("gates_test_a", "robustness_survived", run=True, passed=True, evidence_summary="attempt")
    check("Undeclared gate applicability raises (never inferred)", False)
except gates.ApplicabilityNotLockedError:
    check("Undeclared gate applicability raises (never inferred)", True)

# Confirm caller CANNOT override a locked applicable=False into applicable=True
r5 = gates.evaluate_gate("gates_test_a", "concentration_check", run=True, passed=True, evidence_summary="attempted override")
check("Locked applicable=False cannot be overridden by caller's run=True intent", r5.applicable is False and r5.run is False and r5.passed is None)

print("\n" + "=" * 90)
print("TEST 6: Unknown gate names fail cleanly")
print("=" * 90)
try:
    gates.GateResult("not_a_real_gate", True, True, True, "test", None)
    check("Unknown gate name rejected at GateResult construction", False)
except gates.UnrecognizedGateNameError:
    check("Unknown gate name rejected at GateResult construction", True)

print("\n" + "=" * 90)
print("TEST 7: Validity vs evidence gate distinction preserved")
print("=" * 90)
check("lookahead_audit correctly classified as validity gate", gates.is_validity_gate("lookahead_audit") and not gates.is_evidence_gate("lookahead_audit"))
check("effect_size_meets_threshold correctly classified as evidence gate", gates.is_evidence_gate("effect_size_meets_threshold") and not gates.is_validity_gate("effect_size_meets_threshold"))

print("\n" + "=" * 90)
print("TEST 8: applicable/run/passed three-state semantics preserved in PERSISTED result")
print("=" * 90)
persisted = gates.get_gate_results("gates_test_a")
persisted_data_integrity = [g for g in persisted if g.gate_name == "data_integrity"][0]
check("Persisted data_integrity matches recorded state", persisted_data_integrity.applicable and persisted_data_integrity.run and persisted_data_integrity.passed)

print("\n" + "=" * 90)
print("TEST 9: Gate results immutable after recording -- correction creates new row, not overwrite")
print("=" * 90)
before_count = len(gates.get_gate_results("gates_test_a"))
# Re-evaluate data_integrity with a DIFFERENT result (a "correction")
r_correction = gates.evaluate_gate("gates_test_a", "data_integrity", run=True, passed=False, evidence_summary="correction: found an issue on review")
after_count = len(gates.get_gate_results("gates_test_a"))
check("Correction appended as a NEW row, did not overwrite (count increased)", after_count == before_count + 1)
all_data_integrity_results = [g for g in gates.get_gate_results("gates_test_a") if g.gate_name == "data_integrity"]
check("Original data_integrity=True result still present in history", any(g.passed is True for g in all_data_integrity_results))
check("Corrected data_integrity=False result also present", any(g.passed is False for g in all_data_integrity_results))

# Confirm the GateResult OBJECT itself is frozen (cannot be mutated in Python)
from dataclasses import FrozenInstanceError
try:
    r3.passed = False
    check("GateResult object itself is immutable (frozen dataclass)", False)
except FrozenInstanceError:
    check("GateResult object itself is immutable (frozen dataclass)", True)

print("\n" + "=" * 90)
print("TEST 10: gates.py does NOT determine PROMISING/INCONCLUSIVE/REJECTED")
print("=" * 90)
check("GateResult has no verdict-related field", not hasattr(r3, "verdict") and not hasattr(r3, "status"))
check("evaluate_gate() return type is GateResult, not a verdict", isinstance(r3, gates.GateResult))

print("\n" + "=" * 90)
print("TEST 11: Invalid/inconsistent state combinations rejected")
print("=" * 90)
invalid_cases = [
    ("run=False with passed=True", dict(gate_name="lookahead_audit", applicable=True, run=False, passed=True, evidence_summary="x", evaluated_at=None)),
    ("run=False with passed=False", dict(gate_name="lookahead_audit", applicable=True, run=False, passed=False, evidence_summary="x", evaluated_at=None)),
    ("applicable=False with run=True", dict(gate_name="lookahead_audit", applicable=False, run=True, passed=None, evidence_summary="x", evaluated_at=None)),
    ("applicable=False with passed=True", dict(gate_name="lookahead_audit", applicable=False, run=False, passed=True, evidence_summary="x", evaluated_at=None)),
]
for label, kwargs in invalid_cases:
    try:
        gates.GateResult(**kwargs)
        check("Rejected: " + label, False)
    except gates.InconsistentGateStateError:
        check("Rejected: " + label, True)

print("\n" + "=" * 90)
print("TEST 12: Both validity AND evidence gates tested above (cross-reference)")
print("=" * 90)
check("At least one validity gate tested (data_integrity)", any(gates.is_validity_gate(g.gate_name) for g in persisted))
check("At least one evidence gate tested (effect_size_meets_threshold)", any(gates.is_evidence_gate(g.gate_name) for g in persisted))

print("\n" + "=" * 90)
print("TEST 13: Existing framework/data untouched")
print("=" * 90)
phase6_record = db_interface.get_experiment_record("phase6_signal_random_control_20260914")
check("Phase 6 experiment record still exists and untouched", phase6_record is not None and phase6_record["status"] == "REJECTED")
phase7_record = db_interface.get_experiment_record("phase7_pnl_concentration_20260914")
check("Phase 7 experiment record still exists and untouched", phase7_record is not None)

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
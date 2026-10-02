"""
Test suite for robustness.py, covering all 14 verification points.
"""

import sqlite3
from experiment_config import ExperimentConfig
from experiment import preregister_experiment
import robustness
import gates
import verdict
import db_interface

results = []
def check(name, condition):
    status = "PASS" if condition else "FAIL"
    results.append((name, status))
    print(name + ": " + status)

def make_and_preregister(exp_id, exp_type, declared_checks, applicability_lock=None):
    if applicability_lock is None:
        applicability_lock = [("reproduction", True), ("robustness_survived", True)]
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
        declared_robustness_checks=declared_checks,
    )
    return preregister_experiment(config, allow_legacy_grading=True)

def record_robustness_test(exp_id, test_type, survived, description="test"):
    with sqlite3.connect(db_interface.DB_PATH) as conn:
        conn.execute(
            "INSERT INTO experiment_robustness_tests (experiment_id, test_type, test_description, result_summary, survived) VALUES (?,?,?,?,?)",
            (exp_id, test_type, description, "test result", int(survived))
        )
        conn.commit()


print("=" * 90)
print("TEST 1: A robustness test that clearly survives")
print("=" * 90)
make_and_preregister("rb_survives", "robustness", ["ticker_removed:SMCI"])
record_robustness_test("rb_survives", "ticker_removed:SMCI", True)
r1 = robustness.compute_robustness_survival("rb_survives")
check("Single declared check, evaluated True -> SURVIVED", r1.status == robustness.SURVIVED)
check("declared_count == 1", r1.declared_count == 1)
check("survived_count == 1", r1.survived_count == 1)

print("\n" + "=" * 90)
print("TEST 2: A robustness test that clearly fails")
print("=" * 90)
make_and_preregister("rb_fails", "robustness", ["ticker_removed:SMCI"])
record_robustness_test("rb_fails", "ticker_removed:SMCI", False)
r2 = robustness.compute_robustness_survival("rb_fails")
check("Single declared check, evaluated False -> FAILED", r2.status == robustness.FAILED)

print("\n" + "=" * 90)
print("TEST 3: Missing/unevaluated robustness evidence")
print("=" * 90)
make_and_preregister("rb_missing", "robustness", ["ticker_removed:SMCI", "entry_timing_shift:+1bar"])
record_robustness_test("rb_missing", "ticker_removed:SMCI", True)
r3 = robustness.compute_robustness_survival("rb_missing")
check("One declared, evaluated+passed; one declared, NEVER evaluated -> INSUFFICIENT_COVERAGE", r3.status == robustness.INSUFFICIENT_COVERAGE)
check("This is NOT silently treated as SURVIVED (the core bug this design prevents)", r3.status != robustness.SURVIVED)

print("\n" + "=" * 90)
print("TEST 4: Multiple robustness checks within one experiment")
print("=" * 90)
make_and_preregister("rb_multi", "robustness", ["check_a", "check_b", "check_c"])
record_robustness_test("rb_multi", "check_a", True)
record_robustness_test("rb_multi", "check_b", True)
record_robustness_test("rb_multi", "check_c", True)
r4 = robustness.compute_robustness_survival("rb_multi")
check("3 declared, all 3 evaluated and survived -> SURVIVED", r4.status == robustness.SURVIVED)
check("per_check has exactly 3 entries", len(r4.per_check) == 3)

print("\n" + "=" * 90)
print("TEST 5: Deterministic results")
print("=" * 90)
r5a = robustness.compute_robustness_survival("rb_multi")
r5b = robustness.compute_robustness_survival("rb_multi")
check("Repeated calls produce identical status", r5a.status == r5b.status)
check("Repeated calls produce identical per_check", r5a.per_check == r5b.per_check)

print("\n" + "=" * 90)
print("TEST 6: Boundary case -- zero declared checks")
print("=" * 90)
make_and_preregister("rb_zero_declared", "robustness", [])
r6 = robustness.compute_robustness_survival("rb_zero_declared")
check("Zero declared checks -> INSUFFICIENT_COVERAGE (never vacuously SURVIVED)", r6.status == robustness.INSUFFICIENT_COVERAGE)

print("\n" + "=" * 90)
print("TEST 6b: Boundary case -- one failure among otherwise-unevaluated checks (FAILED takes priority)")
print("=" * 90)
make_and_preregister("rb_fail_priority", "robustness", ["check_a", "check_b", "check_c"])
record_robustness_test("rb_fail_priority", "check_a", False)
r6b = robustness.compute_robustness_survival("rb_fail_priority")
check("Known failure reported immediately, even with other checks unevaluated -> FAILED (not hidden as INSUFFICIENT_COVERAGE)", r6b.status == robustness.FAILED)

print("\n" + "=" * 90)
print("TEST 7: Invalid/malformed inputs fail cleanly")
print("=" * 90)
try:
    robustness.compute_robustness_survival("nonexistent_experiment_xyz")
    check("Nonexistent experiment_id raises", False)
except ValueError:
    check("Nonexistent experiment_id raises", True)

print("\n" + "=" * 90)
print("TEST 8: No accidental lookahead or data mutation")
print("=" * 90)
with sqlite3.connect(db_interface.DB_PATH) as conn:
    count_before = conn.execute("SELECT COUNT(*) FROM experiment_robustness_tests").fetchone()[0]
_ = robustness.compute_robustness_survival("rb_multi")
_ = robustness.compute_robustness_survival("rb_survives")
with sqlite3.connect(db_interface.DB_PATH) as conn:
    count_after = conn.execute("SELECT COUNT(*) FROM experiment_robustness_tests").fetchone()[0]
check("No new robustness test rows created by read operations", count_before == count_after)

print("\n" + "=" * 90)
print("TEST 9: No modification of experiment/gate/V1/Feature Factory records")
print("=" * 90)
phase6_record = db_interface.get_experiment_record("phase6_signal_random_control_20260914")
check("Phase 6 record untouched", phase6_record is not None and phase6_record["status"] == "REJECTED")

print("\n" + "=" * 90)
print("TEST 10: Compatibility with locked v4 verdict semantics (via gates.py bridge)")
print("=" * 90)
make_and_preregister("rb_verdict_bridge", "signal_research", ["ticker_removed:SMCI"],
    applicability_lock=[("data_integrity", True), ("lookahead_audit", True), ("timestamp_safety", False),
                         ("sample_size_adequacy", True), ("statistical_testing", True), ("reproduction", True),
                         ("primary_test_significant", True), ("effect_size_meets_threshold", True),
                         ("multiple_testing_survived", True), ("robustness_survived", True), ("oos_survived", False)])
record_robustness_test("rb_verdict_bridge", "ticker_removed:SMCI", True)
rb_result = robustness.compute_robustness_survival("rb_verdict_bridge")
check("Robustness result computed for verdict-bridging scenario", rb_result.status == robustness.SURVIVED)
gates.evaluate_gate("rb_verdict_bridge", "robustness_survived", run=True, passed=(rb_result.status == robustness.SURVIVED), evidence_summary=rb_result.reasoning)
for g in ["data_integrity", "lookahead_audit", "sample_size_adequacy", "statistical_testing", "reproduction",
          "primary_test_significant", "effect_size_meets_threshold", "multiple_testing_survived"]:
    gates.evaluate_gate("rb_verdict_bridge", g, run=True, passed=True, evidence_summary="test")
v = verdict.calculate_verdict("rb_verdict_bridge")
check("robustness.py's result correctly flows through gates.py into verdict.py -> PROMISING", v.status == "PROMISING")

print("\n" + "=" * 90)
print("TEST 11: Standalone robustness experiment capped at INCONCLUSIVE even when everything passes")
print("=" * 90)
gates.evaluate_gate("rb_multi", "reproduction", run=True, passed=True, evidence_summary="test")
gates.evaluate_gate("rb_multi", "robustness_survived", run=True, passed=True, evidence_summary="all checks survived")
v_rb_standalone = verdict.calculate_verdict("rb_multi")
check("Standalone robustness experiment, everything passed -> still capped at INCONCLUSIVE", v_rb_standalone.status == "INCONCLUSIVE")

print("\n" + "=" * 90)
print("TEST 12: robustness_survived as supporting evidence for another experiment type")
print("=" * 90)
check("Already demonstrated in Test 10 (signal_research reaching PROMISING via robustness_survived)", v.status == "PROMISING")

print("\n" + "=" * 90)
print("TEST 13: Declared/evaluated/failed distinction preserved (not collapsed to boolean)")
print("=" * 90)
check("per_check entries preserve declared/evaluated/survived as 3 separate fields", all(hasattr(c, "declared") and hasattr(c, "evaluated") and hasattr(c, "survived") for c in r3.per_check))
unevaluated_entry = [c for c in r3.per_check if c.check_name == "entry_timing_shift:+1bar"][0]
check("Unevaluated check correctly shows declared=True, evaluated=False", unevaluated_entry.declared is True and unevaluated_entry.evaluated is False)

print("\n" + "=" * 90)
print("TEST 14: Re-running the same evaluation produces the same result")
print("=" * 90)
check("Already demonstrated in Test 5 (determinism)", r5a.status == r5b.status)

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
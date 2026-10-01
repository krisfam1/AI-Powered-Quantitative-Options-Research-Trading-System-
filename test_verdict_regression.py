"""
Targeted regression tests for the verdict.py applicability-lock bug fix.
"""

from experiment_config import ExperimentConfig
from experiment import preregister_experiment
import gates
import verdict
import db_interface

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
    return preregister_experiment(config)

FT_VALIDITY = ["data_integrity", "lookahead_audit", "timestamp_safety", "sample_size_adequacy", "statistical_testing", "reproduction"]
FT_EVIDENCE = ["primary_test_significant", "effect_size_meets_threshold", "multiple_testing_survived"]

print("=" * 90)
print("CASE A: locked non-applicable gate, NO gate-result row -- must be correctly skipped")
print("=" * 90)
lock_a = [(g, True) for g in FT_VALIDITY if g != "timestamp_safety"] + [("timestamp_safety", False)] + [(g, True) for g in FT_EVIDENCE]
make_and_preregister("regr_case_a", lock_a)
for g in FT_VALIDITY:
    if g != "timestamp_safety":
        gates.evaluate_gate("regr_case_a", g, run=True, passed=True, evidence_summary="test")
for g in FT_EVIDENCE:
    gates.evaluate_gate("regr_case_a", g, run=True, passed=True, evidence_summary="test")
v_a = verdict.calculate_verdict("regr_case_a")
check("Case A: locked-False, never-evaluated gate does NOT block verdict", v_a.status == "INCONCLUSIVE")
check("Case A: reasoning does not mention timestamp_safety as missing", "timestamp_safety" not in v_a.reasoning)

print("\n" + "=" * 90)
print("CASE B: locked applicable gate, NO gate-result row -- must remain INCONCLUSIVE (missing)")
print("=" * 90)
lock_b = [(g, True) for g in FT_VALIDITY + FT_EVIDENCE]
make_and_preregister("regr_case_b", lock_b)
for g in FT_VALIDITY:
    gates.evaluate_gate("regr_case_b", g, run=True, passed=True, evidence_summary="test")
v_b = verdict.calculate_verdict("regr_case_b")
check("Case B: locked-True, never-evaluated required evidence -> INCONCLUSIVE (correctly missing)", v_b.status == "INCONCLUSIVE")
check("Case B: reasoning correctly cites missing evidence", "not yet evaluated" in v_b.reasoning)

print("\n" + "=" * 90)
print("CASE C: mixed applicability -- only applicable gates need results")
print("=" * 90)
lock_c = [("data_integrity", True), ("lookahead_audit", True), ("timestamp_safety", False),
          ("sample_size_adequacy", False), ("statistical_testing", True), ("reproduction", True),
          ("primary_test_significant", True), ("effect_size_meets_threshold", False), ("multiple_testing_survived", True)]
make_and_preregister("regr_case_c", lock_c)
for g in ["data_integrity", "lookahead_audit", "statistical_testing", "reproduction", "primary_test_significant", "multiple_testing_survived"]:
    gates.evaluate_gate("regr_case_c", g, run=True, passed=True, evidence_summary="test")
v_c = verdict.calculate_verdict("regr_case_c")
check("Case C: mixed applicability, all applicable gates satisfied -> INCONCLUSIVE (feature_test ceiling, not stuck on missing)", v_c.status == "INCONCLUSIVE")
check("Case C: reasoning is the ceiling message, not a missing-gates message", "all validity/evidence requirements satisfied" in v_c.reasoning)

print("\n" + "=" * 90)
print("CASE D: existing behavior -- explicitly evaluating an applicable=False gate is unaffected")
print("=" * 90)
lock_d = [(g, True) for g in FT_VALIDITY if g != "timestamp_safety"] + [("timestamp_safety", False)] + [(g, True) for g in FT_EVIDENCE]
make_and_preregister("regr_case_d", lock_d)
for g in FT_VALIDITY:
    if g != "timestamp_safety":
        gates.evaluate_gate("regr_case_d", g, run=True, passed=True, evidence_summary="test")
for g in FT_EVIDENCE:
    gates.evaluate_gate("regr_case_d", g, run=True, passed=True, evidence_summary="test")
gates.evaluate_gate("regr_case_d", "timestamp_safety", run=True, passed=True, evidence_summary="attempted explicit evaluation")
v_d = verdict.calculate_verdict("regr_case_d")
check("Case D: explicit evaluation of locked-False gate does not change the verdict vs Case A", v_d.status == v_a.status)

print("\n" + "=" * 90)
print("ADDITIONAL CONFIRMATIONS")
print("=" * 90)
gate_count_before = len(gates.get_gate_results("regr_case_a"))
_ = verdict.calculate_verdict("regr_case_a")
_ = verdict.calculate_verdict("regr_case_a")
gate_count_after = len(gates.get_gate_results("regr_case_a"))
check("No gate records created merely by calculating a verdict", gate_count_before == gate_count_after)

phase6_record = db_interface.get_experiment_record("phase6_signal_random_control_20260914")
check("Phase 6 record untouched", phase6_record is not None and phase6_record["status"] == "REJECTED")

print("\n" + "=" * 90)
print("SUMMARY")
print("=" * 90)
total = len(results)
passed_count = len([r for r in results if r[1] == "PASS"])
print(str(passed_count) + " / " + str(total) + " assertions passed")
if passed_count == total:
    print("\nALL REGRESSION TESTS PASS.")
else:
    print("\nFAILURES:")
    for name, status in results:
        if status == "FAIL":
            print("  - " + name)
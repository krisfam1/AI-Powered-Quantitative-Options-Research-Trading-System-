"""
Test suite for db_interface.py + preregister_experiment(), covering
all 15 verification points.
"""

import sqlite3
import json
from experiment_config import ExperimentConfig
from experiment import preregister_experiment, PreregistrationError
import db_interface

DB_PATH = "research_database.db"

results = []
def check(name, condition):
    status = "PASS" if condition else "FAIL"
    results.append((name, status))
    print(name + ": " + status)

def make_config(**overrides):
    defaults = dict(
        experiment_id="prereg_test_001", experiment_type="feature_test",
        hypothesis="test hypothesis", research_question="test question",
        dataset_version="v1", date_range=("2026-06-11", "2026-09-09"),
        universe=["AAPL"], option_type="call",
        features_used=[("past_return_n", "1.0")], parameters={"n": 20},
        model_version=None, pricing_methodology="v1", execution_assumptions="standard",
        train_period=None, validation_period=None, test_period=None,
        random_seeds=[42], code_version="abc123",
        testing_family_declaration="INDEPENDENT_SINGLE",
        applicability_lock=[("lookahead_audit", True), ("timestamp_safety", False)],
        oos_validation_claimed=False,
        declared_robustness_checks=[],
    )
    defaults.update(overrides)
    return ExperimentConfig(**defaults)


print("=" * 90)
print("TEST 1 & 10 & 11: Valid preregistration succeeds, correct state/timestamp, exact config persisted")
print("=" * 90)
config1 = make_config(experiment_id="test1_valid")
exp1 = preregister_experiment(config1, allow_legacy_grading=True)
check("Preregistration succeeded", exp1 is not None)
check("State is PREREGISTERED", exp1.state == "PREREGISTERED")
check("preregistered_at timestamp set", exp1.preregistered_at is not None)

record = db_interface.get_experiment_record("test1_valid")
check("Record persisted to DB", record is not None)
check("Persisted config_hash matches frozen config's hash", record["config_hash"] == config1.config_hash)
check("Persisted hypothesis matches", record["hypothesis"] == config1.hypothesis)
check("Persisted state is PREREGISTERED", record["state"] == "PREREGISTERED")

print("\n" + "=" * 90)
print("TEST 2: preregister_experiment() is the only DB touchpoint (config construction alone touched nothing)")
print("=" * 90)
config_standalone = make_config(experiment_id="test2_standalone_no_db")
check("Config construction alone does not create a DB record", db_interface.get_experiment_record("test2_standalone_no_db") is None)

print("\n" + "=" * 90)
print("TEST 3: EXISTING_FAMILY requires the family to already exist")
print("=" * 90)
config_bad_family = make_config(experiment_id="test3_bad_family", testing_family_declaration="EXISTING_FAMILY:nonexistent_family")
try:
    preregister_experiment(config_bad_family, allow_legacy_grading=True)
    check("EXISTING_FAMILY with nonexistent family rejected", False)
except PreregistrationError:
    check("EXISTING_FAMILY with nonexistent family rejected", True)

print("\n" + "=" * 90)
print("TEST 4: NEW_FAMILY correctly creates the family and registers the experiment")
print("=" * 90)
config_new_family = make_config(experiment_id="test4_new_family", testing_family_declaration="NEW_FAMILY:test_family_alpha")
exp4 = preregister_experiment(config_new_family, allow_legacy_grading=True)
check("NEW_FAMILY preregistration succeeded", exp4.state == "PREREGISTERED")
check("Testing family now exists", db_interface.testing_family_exists("test_family_alpha"))
with sqlite3.connect(DB_PATH) as conn:
    member = conn.execute("SELECT 1 FROM testing_family_members WHERE family_id=? AND experiment_id=?", ("test_family_alpha", "test4_new_family")).fetchone()
check("Creating experiment registered as a family member", member is not None)

print("\n" + "=" * 90)
print("TEST: EXISTING_FAMILY now succeeds against the family just created")
print("=" * 90)
config_join_family = make_config(experiment_id="test4b_joins_family", testing_family_declaration="EXISTING_FAMILY:test_family_alpha")
exp4b = preregister_experiment(config_join_family, allow_legacy_grading=True)
check("EXISTING_FAMILY join succeeded once family exists", exp4b.state == "PREREGISTERED")

print("\n" + "=" * 90)
print("TEST 5: INDEPENDENT_SINGLE requires no family action")
print("=" * 90)
config_indep = make_config(experiment_id="test5_independent", testing_family_declaration="INDEPENDENT_SINGLE")
exp5 = preregister_experiment(config_indep, allow_legacy_grading=True)
with sqlite3.connect(DB_PATH) as conn:
    member_count = conn.execute("SELECT COUNT(*) FROM testing_family_members WHERE experiment_id=?", ("test5_independent",)).fetchone()[0]
check("INDEPENDENT_SINGLE experiment has zero family memberships", member_count == 0)

print("\n" + "=" * 90)
print("TEST 6 & 9: Duplicate experiment IDs rejected (idempotency-safe)")
print("=" * 90)
config_dup = make_config(experiment_id="test1_valid")  # SAME ID as Test 1
try:
    preregister_experiment(config_dup, allow_legacy_grading=True)
    check("Duplicate experiment_id rejected", False)
except PreregistrationError:
    check("Duplicate experiment_id rejected", True)

print("\n" + "=" * 90)
print("TEST 7: Duplicate family membership rejected")
print("=" * 90)
config_dup_member = make_config(experiment_id="test7_dup_member_attempt", testing_family_declaration="EXISTING_FAMILY:test_family_alpha")
exp7 = preregister_experiment(config_dup_member, allow_legacy_grading=True)  # first join succeeds (different experiment_id)
check("First join to family succeeds", exp7.state == "PREREGISTERED")
# Now attempt the SAME experiment_id trying to "rejoin" -- should fail on duplicate experiment_id first,
# but let's also directly test the underlying register_family_member duplicate-membership guard:
conn_test = db_interface.get_connection()
try:
    db_interface.register_family_member(conn_test, "test_family_alpha", "test7_dup_member_attempt")
    check("Direct duplicate family membership rejected", False)
except ValueError:
    check("Direct duplicate family membership rejected", True)
finally:
    conn_test.close()

print("\n" + "=" * 90)
print("TEST 8: Nonexistent existing-family reference rejected (re-verified distinctly)")
print("=" * 90)
config_bad_family2 = make_config(experiment_id="test8_bad_family2", testing_family_declaration="EXISTING_FAMILY:totally_made_up_family_xyz")
try:
    preregister_experiment(config_bad_family2, allow_legacy_grading=True)
    check("Nonexistent family reference rejected", False)
except PreregistrationError:
    check("Nonexistent family reference rejected", True)

print("\n" + "=" * 90)
print("TEST 12 & 13: applicability_lock/oos_validation_claimed cannot be altered; DB cannot silently mutate config")
print("=" * 90)
config12 = make_config(experiment_id="test12_immutable_check", applicability_lock=[("lookahead_audit", True), ("timestamp_safety", True)], oos_validation_claimed=True, test_period=("2026-09-10","2026-09-20"))
exp12 = preregister_experiment(config12, allow_legacy_grading=True)
record12 = db_interface.get_experiment_record("test12_immutable_check")
persisted_lock = json.loads(record12["applicability_lock"])
original_lock = [list(a) for a in config12.applicability_lock]
check("Persisted applicability_lock matches original exactly", persisted_lock == original_lock)
check("Persisted oos_validation_claimed matches original", bool(record12["oos_validation_claimed"]) == config12.oos_validation_claimed)
try:
    config12.applicability_lock[0] = ("changed", False)
    check("applicability_lock still immutable on the Python object after persistence", False)
except TypeError:
    check("applicability_lock still immutable on the Python object after persistence", True)

print("\n" + "=" * 90)
print("TEST 14 & 15: Invalid config fails cleanly, no partial DB state (transaction safety)")
print("=" * 90)
# Attempt a NEW_FAMILY preregistration that will fail AFTER family creation
# (duplicate experiment_id on the SAME call) to verify rollback leaves no orphaned family.
config15 = make_config(experiment_id="test1_valid", testing_family_declaration="NEW_FAMILY:should_not_exist_after_rollback")
try:
    preregister_experiment(config15, allow_legacy_grading=True)
except PreregistrationError:
    pass
check("Family from failed/rolled-back preregistration does NOT exist (no partial state)", not db_interface.testing_family_exists("should_not_exist_after_rollback"))
check("Failed experiment_id 'test1_valid' was NOT overwritten by the failed attempt", db_interface.get_experiment_record("test1_valid")["config_hash"] == config1.config_hash)

print("\n" + "=" * 90)
print("SUMMARY")
print("=" * 90)
total = len(results)
passed = len([r for r in results if r[1] == "PASS"])
print(str(passed) + " / " + str(total) + " assertions passed")
if passed == total:
    print("\nALL TESTS PASS.")
else:
    print("\nFAILURES:")
    for name, status in results:
        if status == "FAIL":
            print("  - " + name)
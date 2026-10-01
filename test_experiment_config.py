"""
Formal test suite for ExperimentConfig, per the locked v4 architecture.
Covers: immutability, recursive freezing, required-field validation,
testing-family format validation (no DB dependency), oos_validation_claimed
coupling, applicability_lock immutability, deterministic config_hash,
identical/different configs, and rejection of uncanonicalizable values.
"""

from dataclasses import FrozenInstanceError
from experiment_config import ExperimentConfig, InvalidExperimentConfigError
from canonical_hash import UncanonicalizableValueError


def make_valid_config(**overrides):
    defaults = dict(
        experiment_id="test_exp_001", experiment_type="feature_test",
        hypothesis="test hypothesis", research_question="test question",
        dataset_version="v1", date_range=("2026-06-11", "2026-09-09"),
        universe=["AAPL", "TSLA"], option_type="call",
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


results = []

def check(name, condition):
    status = "PASS" if condition else "FAIL"
    results.append((name, status))
    print(name + ": " + status)


print("=" * 90)
print("TEST 1: Standalone construction -- no database dependency")
print("=" * 90)
config = make_valid_config()
check("Constructed successfully with no DB access", config is not None)
print("config_hash: " + config.config_hash[:16] + "...")

print("\n" + "=" * 90)
print("TEST 2: True immutability -- top-level and nested")
print("=" * 90)
try:
    config.hypothesis = "changed"
    check("Top-level attribute mutation blocked", False)
except FrozenInstanceError:
    check("Top-level attribute mutation blocked", True)

try:
    config.universe.append("NVDA")
    check("universe is a real (non-appendable) tuple", False)
except AttributeError:
    check("universe is a real (non-appendable) tuple", True)

try:
    config.applicability_lock[0] = ("changed", True)
    check("applicability_lock immutable (no item assignment)", False)
except TypeError:
    check("applicability_lock immutable (no item assignment)", True)

print("\n" + "=" * 90)
print("TEST 3: Recursive freezing of mutable inputs (parameters dict)")
print("=" * 90)
check("parameters correctly frozen to tuple-of-pairs", isinstance(config.parameters, tuple))
check("universe correctly frozen to tuple", isinstance(config.universe, tuple))

original_universe = ["AAPL", "TSLA"]
config_mut = make_valid_config(universe=original_universe)
hash_before = config_mut.config_hash
original_universe.append("NVDA")
check("mutating original list post-construction has no effect on stored config", config_mut.universe == ("AAPL", "TSLA"))
check("hash unaffected by post-construction mutation of original input", config_mut.config_hash == hash_before)

print("\n" + "=" * 90)
print("TEST 4: Required-field validation")
print("=" * 90)
try:
    make_valid_config(experiment_type="not_a_real_type")
    check("Invalid experiment_type rejected", False)
except InvalidExperimentConfigError:
    check("Invalid experiment_type rejected", True)

try:
    make_valid_config(hypothesis="")
    check("Empty hypothesis rejected", False)
except InvalidExperimentConfigError:
    check("Empty hypothesis rejected", True)

try:
    make_valid_config(research_question="   ")
    check("Whitespace-only research_question rejected", False)
except InvalidExperimentConfigError:
    check("Whitespace-only research_question rejected", True)

print("\n" + "=" * 90)
print("TEST 5: testing_family_declaration format validation (no DB dependency)")
print("=" * 90)
for bad_decl in ["random_string", "NEW_FAMILY:", "existing_family:lowercase", "EXISTING_FAMILY: has space"]:
    try:
        make_valid_config(testing_family_declaration=bad_decl)
        check("Rejected malformed declaration: " + repr(bad_decl), False)
    except InvalidExperimentConfigError:
        check("Rejected malformed declaration: " + repr(bad_decl), True)

for good_decl in ["INDEPENDENT_SINGLE", "NEW_FAMILY:feature_screen_v1", "EXISTING_FAMILY:feature_screen_v1"]:
    try:
        make_valid_config(testing_family_declaration=good_decl)
        check("Accepted valid declaration: " + repr(good_decl), True)
    except InvalidExperimentConfigError:
        check("Accepted valid declaration: " + repr(good_decl), False)

print("\n" + "=" * 90)
print("TEST 6: oos_validation_claimed behavior")
print("=" * 90)
try:
    make_valid_config(oos_validation_claimed=True, test_period=None)
    check("oos_validation_claimed=True without test_period rejected", False)
except InvalidExperimentConfigError:
    check("oos_validation_claimed=True without test_period rejected", True)

try:
    make_valid_config(oos_validation_claimed=True, test_period=("2026-09-10", "2026-09-20"))
    check("oos_validation_claimed=True WITH test_period accepted", True)
except InvalidExperimentConfigError:
    check("oos_validation_claimed=True WITH test_period accepted", False)

print("\n" + "=" * 90)
print("TEST 7: Deterministic config_hash -- identical/different configs")
print("=" * 90)
config_a = make_valid_config()
config_b = make_valid_config()
check("Identical configs produce identical hash", config_a.config_hash == config_b.config_hash)

config_c = make_valid_config(hypothesis="a different hypothesis")
check("Different hypothesis produces different hash", config_a.config_hash != config_c.config_hash)

config_d = make_valid_config(random_seeds=[43])
check("Different random_seeds produces different hash", config_a.config_hash != config_d.config_hash)

print("\n" + "=" * 90)
print("TEST 8: Unsupported/uncanonicalizable values rejected, not stringified")
print("=" * 90)
class CustomObj:
    pass

try:
    make_valid_config(parameters={"bad_value": CustomObj()})
    check("Custom object in parameters rejected", False)
except InvalidExperimentConfigError:
    check("Custom object in parameters rejected", True)

try:
    make_valid_config(parameters={"bad_value": float("nan")})
    check("NaN in parameters rejected", False)
except InvalidExperimentConfigError:
    check("NaN in parameters rejected", True)

try:
    make_valid_config(parameters={"bad_value": {1, 2, 3}})
    check("Set in parameters rejected", False)
except InvalidExperimentConfigError:
    check("Set in parameters rejected", True)

print("\n" + "=" * 90)
print("SUMMARY")
print("=" * 90)
total = len(results)
passed = len([r for r in results if r[1] == "PASS"])
print(str(passed) + " / " + str(total) + " assertions passed")
if passed == total:
    print("\nALL TESTS PASS.")
else:
    print("\nFAILURES DETECTED:")
    for name, status in results:
        if status == "FAIL":
            print("  - " + name)
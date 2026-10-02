"""
Test suite for tiered_verdict.py and its wiring (experiment_config / experiment / run_experiment / verdict).
Run it in a throwaway directory with a fresh schema (create_research_db_schema.py): the integration
section registers fixtures in ./research_database.db, like every other framework test.
"""
import json
import sqlite3

import tiered_verdict as tv
from experiment_config import ExperimentConfig, InvalidExperimentConfigError
from experiment import preregister_experiment, PreregistrationError

results = []
def check(name, condition):
    results.append((name, "PASS" if condition else "FAIL"))
    print(name + ": " + ("PASS" if condition else "FAIL"))

CHECKS = ["confound_gate", "econ_gate", "s1", "s2", "s3", "s4"]

def decl_dict(**over):
    d = {"scheme": "tiered_v1", "hypothesized_sign": "+", "alpha_one_sided": 0.0167, "effect_size_floor": 0.15,
         "power_at_floor": 0.85, "min_abs_t_stat": 0, "hard_gates": ["confound_gate", "econ_gate"],
         "soft_checks": ["s1", "s2", "s3", "s4"], "max_soft_failures_for_small_size": 2}
    d.update(over)
    return d

def D(**over):
    return tv.validate_declaration({"tiered_grading": decl_dict(**over)}, CHECKS)

def P(est, p=0.001, popp=0.999, cb=None, n=200, t=None):
    return tv.PrimaryResult(est, p, popp, cb if cb is not None else est + 0.1, n, t)

ALL = {c: True for c in CHECKS}

print("=" * 90); print("PURE GRADING"); print("=" * 90)
check("clean pass -> VALIDATED_FULL_CONFIDENCE", tv.grade(D(), P(0.25), ALL).status == tv.VALIDATED_FULL)
check("1 soft failure -> VALIDATED_SMALL_SIZE_MONITOR", tv.grade(D(), P(0.25), {**ALL, "s1": False}).status == tv.VALIDATED_SMALL)
check("2 soft failures (= tolerance) -> SMALL", tv.grade(D(), P(0.25), {**ALL, "s1": False, "s2": False}).status == tv.VALIDATED_SMALL)
check("3 soft failures (> tolerance) -> HELD, not REJECTED",
      tv.grade(D(), P(0.25), {**ALL, "s1": False, "s2": False, "s3": False}).status == tv.HELD)
check("all soft failures -> still not REJECTED", tv.grade(D(), P(0.25), {**ALL, **{c: False for c in ["s1", "s2", "s3", "s4"]}}).status == tv.HELD)
check("hard gate failure -> REJECTED even with a perfect primary", tv.grade(D(), P(0.40), {**ALL, "econ_gate": False}).status == tv.REJECTED)
check("hard gate failure -> REJECTED even when underpowered", tv.grade(D(power_at_floor=0.3), P(0.05, p=0.4), {**ALL, "confound_gate": False}).status == tv.REJECTED)
check("wrong sign, powered -> REJECTED", tv.grade(D(), P(-0.02, p=0.6, popp=0.4), ALL).status == tv.REJECTED)
check("wrong sign, underpowered, not significant -> HELD", tv.grade(D(power_at_floor=0.4), P(-0.05, p=0.7, popp=0.3), ALL).status == tv.HELD)
check("wrong sign, underpowered, significantly reversed -> REJECTED", tv.grade(D(power_at_floor=0.4), P(-0.3, p=0.999, popp=0.001), ALL).status == tv.REJECTED)
check("right sign, not significant, powered, bound excludes floor -> REJECTED (decisive null)",
      tv.grade(D(), P(0.03, p=0.3, cb=0.12), ALL).status == tv.REJECTED)
check("right sign, not significant, powered, bound includes floor -> HELD",
      tv.grade(D(), P(0.10, p=0.08, cb=0.22), ALL).status == tv.HELD)
check("right sign, not significant, underpowered -> HELD", tv.grade(D(power_at_floor=0.5), P(0.03, p=0.3, cb=0.12), ALL).status == tv.HELD)
check("significant but below floor, bound includes floor -> HELD", tv.grade(D(), P(0.12, p=0.01, cb=0.18), ALL).status == tv.HELD)
check("significant but below floor, powered, bound excludes floor -> REJECTED", tv.grade(D(), P(0.11, p=0.01, cb=0.14), ALL).status == tv.REJECTED)
check("min_abs_t_stat=3: t=2.5 blocks VALIDATED (-> HELD)", tv.grade(D(min_abs_t_stat=3.0), P(0.25, t=2.5), ALL).status == tv.HELD)
check("min_abs_t_stat=3: t=3.2 -> VALIDATED_FULL", tv.grade(D(min_abs_t_stat=3.0), P(0.25, t=3.2), ALL).status == tv.VALIDATED_FULL)
check("min_abs_t_stat declared but no t reported -> INCOMPLETE", tv.grade(D(min_abs_t_stat=3.0), P(0.25), ALL).status == tv.INCOMPLETE)
check("negative hypothesis: estimate -0.25 -> VALIDATED_FULL", tv.grade(D(hypothesized_sign="-"), P(-0.25, cb=0.35), ALL).status == tv.VALIDATED_FULL)
check("negative hypothesis: estimate +0.05, powered -> REJECTED", tv.grade(D(hypothesized_sign="-"), P(0.05, p=0.8, popp=0.2), ALL).status == tv.REJECTED)
check("missing soft check -> INCOMPLETE", tv.grade(D(), P(0.25), {k: v for k, v in ALL.items() if k != "s4"}).status == tv.INCOMPLETE)
check("missing primary -> INCOMPLETE", tv.grade(D(), None, ALL).status == tv.INCOMPLETE)
check("soft failures are listed for monitoring", tv.grade(D(), P(0.25), {**ALL, "s3": False}).soft_failures == ("s3",))
check("every tier carries a deployment meaning", all(tv.DEPLOYMENT_MEANING.get(t) for t in tv.TIERS))

print("\n" + "=" * 90); print("DECLARATION VALIDATION"); print("=" * 90)
def bad(**over):
    try:
        D(**over); return False
    except tv.InvalidTieredDeclarationError:
        return True
check("alpha > 0.05 refused (never loosen the bar)", bad(alpha_one_sided=0.10))
check("0 hard gates refused", bad(hard_gates=[], soft_checks=CHECKS))
check("4 hard gates refused (deliberately minimal)", bad(hard_gates=["confound_gate", "econ_gate", "s1", "s2"], soft_checks=["s3", "s4"]))
check("unclassified check refused", bad(soft_checks=["s1", "s2", "s3"]))
check("check in both lists refused", bad(soft_checks=["s1", "s2", "s3", "s4", "econ_gate"]))
check("undeclared check refused", bad(soft_checks=["s1", "s2", "s3", "s4", "ghost"]))
check("tolerance >= number of soft checks refused", bad(max_soft_failures_for_small_size=4))
check("bad sign refused", bad(hypothesized_sign="up"))
check("unknown key refused", bad(**{"bonus": 1}))
check("no declaration -> None (legacy config)", tv.validate_declaration({"n": 20}, CHECKS) is None)

def make_config(exp_id, parameters, checks=CHECKS, lock=None):
    return ExperimentConfig(
        experiment_id=exp_id, experiment_type="signal_research", hypothesis="h", research_question="q",
        dataset_version="v1", date_range=("2026-01-01", "2026-06-30"), universe=["SPY"], option_type="n/a",
        features_used=[("x", "1.0")], parameters=parameters, model_version=None, pricing_methodology="n/a",
        execution_assumptions="none", train_period=None, validation_period=None, test_period=None,
        random_seeds=[42], code_version="t", testing_family_declaration="INDEPENDENT_SINGLE",
        applicability_lock=lock or [(g, True) for g in ["data_integrity", "lookahead_audit", "timestamp_safety",
                                                        "sample_size_adequacy", "statistical_testing", "reproduction"]],
        oos_validation_claimed=False, declared_robustness_checks=checks)

try:
    make_config("bad_decl", {"tiered_grading": decl_dict(hard_gates=[], soft_checks=CHECKS)}); ok = False
except InvalidExperimentConfigError:
    ok = True
check("ExperimentConfig refuses an invalid declaration at construction (before any hash)", ok)
c1 = make_config("hash_probe", {"tiered_grading": decl_dict()})
c2 = make_config("hash_probe", {"tiered_grading": decl_dict(max_soft_failures_for_small_size=1)})
check("the declaration is part of the hash", c1.config_hash != c2.config_hash)

print("\n" + "=" * 90); print("REGISTRATION + END-TO-END (fresh schema in the working directory)"); print("=" * 90)
try:
    preregister_experiment(make_config("tier_legacy_refused", {"n": 20})); ok = False
except PreregistrationError:
    ok = True
check("new registration without tiered_grading is refused", ok)
preregister_experiment(make_config("tier_legacy_fixture", {"n": 20}), allow_legacy_grading=True)
check("legacy fixture registers with explicit allow_legacy_grading=True", True)

import run_experiment, verdict
VALID = ["data_integrity", "lookahead_audit", "timestamp_safety", "sample_size_adequacy", "statistical_testing", "reproduction"]

def executor(primary, checks):
    def _ex(_rec):
        return {"gate_results": {g: {"run": True, "passed": True, "evidence_summary": "t"} for g in VALID},
                "robustness_results": {k: {"survived": v, "description": "t"} for k, v in checks.items()},
                "tiered_primary": primary}
    return _ex

cases = [
    ("tier_e2e_full", {"estimate": 0.25, "p_one_sided": 0.001, "p_opposite_one_sided": 0.999, "confidence_bound": 0.35, "n": 200}, ALL, tv.VALIDATED_FULL),
    ("tier_e2e_small", {"estimate": 0.25, "p_one_sided": 0.001, "p_opposite_one_sided": 0.999, "confidence_bound": 0.35, "n": 200}, {**ALL, "s2": False}, tv.VALIDATED_SMALL),
    ("tier_e2e_held", {"estimate": 0.10, "p_one_sided": 0.08, "p_opposite_one_sided": 0.92, "confidence_bound": 0.22, "n": 200}, ALL, tv.HELD),
    ("tier_e2e_rejected", {"estimate": 0.25, "p_one_sided": 0.001, "p_opposite_one_sided": 0.999, "confidence_bound": 0.35, "n": 200}, {**ALL, "confound_gate": False}, tv.REJECTED),
]
for eid, prim, chk, want in cases:
    preregister_experiment(make_config(eid, {"tiered_grading": decl_dict()}))
    v = run_experiment.run_experiment(eid, executor(prim, chk))
    check(f"end-to-end {eid} -> {want}", v.status == want)
    check(f"end-to-end {eid}: deployment meaning stored", bool(v.promising_meaning))
with sqlite3.connect("research_database.db") as conn:
    n_rb = conn.execute("SELECT COUNT(*) FROM experiment_gate_checklist WHERE experiment_id='tier_e2e_small' "
                        "AND gate_name='robustness_survived'").fetchone()[0]
    n_pr = conn.execute("SELECT COUNT(*) FROM experiment_primary_results WHERE experiment_id LIKE 'tier_e2e_%'").fetchone()[0]
check("tiered experiments do not get the legacy all-or-nothing robustness_survived gate", n_rb == 0)
check("primary results persisted append-only (4 rows)", n_pr == 4)
preregister_experiment(make_config("tier_e2e_incomplete", {"tiered_grading": decl_dict()}))
v = run_experiment.run_experiment("tier_e2e_incomplete", executor(None, ALL))
check("no primary result -> INCOMPLETE, not a verdict", v.status == tv.INCOMPLETE)

fails = [n for n, s in results if s == "FAIL"]
print("\n" + "=" * 90)
print(f"{len(results) - len(fails)}/{len(results)} passed" + (f"; FAILURES: {fails}" if fails else ""))

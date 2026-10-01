"""
verdict.py -- calculates the final PROMISING/INCONCLUSIVE/REJECTED
verdict for a preregistered experiment. PURE, READ-ONLY calculation --
never modifies experiment config, gate records, V1, Feature Factory,
or any existing research record. Has no execution/promotion capability.

Effective-result rule for append-only gate corrections (per review):
the LATEST recorded result for a given gate_name (highest autoincrement
id in experiment_gate_checklist, which is the immutable recording
sequence) is the effective result. Original and corrected records
both remain permanently in the database -- this rule only determines
which one verdict.py treats as current for THIS calculation.
"""

import json
import sqlite3
from dataclasses import dataclass
from typing import Optional
import db_interface
import gates
import gates

EXPERIMENT_TYPE_REQUIREMENTS = {
    "feature_test": {
        "validity_required": ["data_integrity", "lookahead_audit", "timestamp_safety",
                               "sample_size_adequacy", "statistical_testing", "reproduction"],
        "evidence_required": ["primary_test_significant", "effect_size_meets_threshold",
                               "multiple_testing_survived"],
        "evidence_conditional": [],
        "max_verdict": "INCONCLUSIVE",
        "promising_meaning": None,
    },
    "signal_research": {
        "validity_required": ["data_integrity", "lookahead_audit", "timestamp_safety",
                               "sample_size_adequacy", "statistical_testing", "reproduction"],
        "evidence_required": ["primary_test_significant", "effect_size_meets_threshold",
                               "multiple_testing_survived", "robustness_survived"],
        "evidence_conditional": ["oos_survived"],
        "max_verdict": "PROMISING",
        "promising_meaning": "Sufficient evidence to justify a SEPARATE strategy-level validation experiment. Does NOT authorize adding the signal to V1 or changing the trading strategy.",
    },
    "model_test": {
        "validity_required": ["data_integrity", "lookahead_audit", "sample_size_adequacy",
                               "statistical_testing", "reproduction"],
        "evidence_required": ["primary_performance_test_significant", "effect_size_meets_threshold",
                               "multiple_testing_survived", "concentration_check", "robustness_survived"],
        "evidence_conditional": ["oos_survived"],
        "max_verdict": "PROMISING",
        "promising_meaning": "Sufficient evidence to justify a paper-trading candidacy review. Does NOT automatically replace V1.",
    },
    "baseline": {
        "validity_required": ["data_integrity", "lookahead_audit", "reproduction"],
        "evidence_required": ["primary_performance_test_significant", "effect_size_meets_threshold",
                               "concentration_check", "robustness_survived"],
        "evidence_conditional": ["multiple_testing_survived", "oos_survived"],
        "max_verdict": "PROMISING",
        "promising_meaning": "The frozen baseline (or a fully-specified variant) shows genuine, non-concentrated economic evidence.",
    },
    "pricing_validation": {
        "validity_required": ["data_integrity", "lookahead_audit", "timestamp_safety", "reproduction"],
        "evidence_required": ["pricing_accuracy_meets_threshold", "pricing_coverage_meets_threshold"],
        "evidence_conditional": [],
        "max_verdict": "PROMISING",
        "promising_meaning": "The pricing methodology accurately represents real historical option prices, with adequate real-data coverage. This is a METHODOLOGY finding.",
    },
    "exit_test": {
        "validity_required": ["data_integrity", "lookahead_audit", "reproduction"],
        "evidence_required": ["primary_performance_test_significant", "effect_size_meets_threshold",
                               "concentration_check"],
        "evidence_conditional": ["robustness_survived", "multiple_testing_survived"],
        "max_verdict": "PROMISING",
        "promising_meaning": "This specific exit-rule variant shows genuine improvement over the frozen baseline's exits, in isolation. Does NOT authorize changing V1's live exits.",
    },
    "oos_validation": {
        "validity_required": ["data_integrity", "lookahead_audit", "reproduction"],
        "evidence_required": ["oos_survived", "effect_size_meets_threshold", "concentration_check"],
        "evidence_conditional": [],
        "max_verdict": "PROMISING",
        "promising_meaning": "A prior PROMISING finding has now been confirmed on genuinely independent, out-of-sample data.",
    },
    "robustness": {
        "validity_required": ["reproduction"],
        "evidence_required": ["robustness_survived"],
        "evidence_conditional": [],
        "max_verdict": "INCONCLUSIVE",
        "promising_meaning": None,
    },
}


class UnknownExperimentTypeError(Exception):
    pass


@dataclass(frozen=True)
class Verdict:
    status: str
    reasoning: str
    promising_meaning: Optional[str]
    experiment_id: str
    experiment_type: str


def get_effective_gate_result(experiment_id: str, gate_name: str):
    """
    Resolves the EFFECTIVE result for a gate_name, per the explicit,
    deterministic rule: the LATEST recorded row (highest autoincrement
    id -- the immutable recording sequence) is effective. Earlier
    (corrected) results remain in the database, untouched, but are not
    used for THIS verdict calculation.
    """
    with sqlite3.connect(db_interface.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM experiment_gate_checklist WHERE experiment_id=? AND gate_name=? ORDER BY id DESC LIMIT 1",
            (experiment_id, gate_name)
        ).fetchone()
    if row is None:
        return None
    return gates.GateResult(
        gate_name=row["gate_name"], applicable=bool(row["applicable"]), run=bool(row["run"]),
        passed=(None if row["passed"] is None else bool(row["passed"])),
        evidence_summary=row["evidence_summary"], evaluated_at=None,
    )


def _claims_oos(experiment_record: dict) -> bool:
    """OOS evidence is only ever claimed if BOTH oos_validation_claimed=True
    AND a real test_period exists -- both read from the frozen, persisted
    config. Never inferred, never assumed."""
    claimed = bool(experiment_record["oos_validation_claimed"])
    has_test_period = experiment_record["test_period_start"] is not None
    return claimed and has_test_period


def _check_gate_list(experiment_id: str, gate_names: list, experiment_record: dict):
    """
    Returns {'missing': [...], 'failed': [...]} for a list of gate names.
    FIX: applicability_lock is AUTHORITATIVE, checked FIRST, before any
    gate-result row is consulted. A gate locked applicable=False is
    skipped immediately regardless of whether evaluate_gate() was ever
    called for it. Only locked applicable=True requires a result.
    """
    missing = []
    failed = []
    for name in gate_names:
        try:
            is_applicable = gates.get_locked_applicability(experiment_record, name)
        except gates.ApplicabilityNotLockedError:
            missing.append(name)
            continue
        if not is_applicable:
            continue
        result = get_effective_gate_result(experiment_id, name)
        if result is None or not result.run:
            missing.append(name)
            continue
        if result.passed is False:
            failed.append(name)
    return {"missing": missing, "failed": failed}


def calculate_verdict(experiment_id: str) -> Verdict:
    """
    PURE, READ-ONLY calculation. Does not modify the experiment config,
    gate records, V1, Feature Factory, or any existing research record.
    """
    experiment_record = db_interface.get_experiment_record(experiment_id)
    if experiment_record is None:
        raise ValueError("No preregistered experiment found with id: " + experiment_id)

    exp_type = experiment_record["experiment_type"]
    if exp_type not in EXPERIMENT_TYPE_REQUIREMENTS:
        raise UnknownExperimentTypeError("Unknown experiment_type: " + repr(exp_type))
    reqs = EXPERIMENT_TYPE_REQUIREMENTS[exp_type]

    # STEP 1: Required validity
    validity_check = _check_gate_list(experiment_id, reqs["validity_required"], experiment_record)
    if validity_check["missing"]:
        return Verdict("INCONCLUSIVE", "required validity gates not yet run: " + str(validity_check["missing"]),
                        None, experiment_id, exp_type)
    if validity_check["failed"]:
        # Per the review: a validity failure means the experiment COULDN'T
        # answer its own question -- INCONCLUSIVE, not REJECTED.
        return Verdict("INCONCLUSIVE", "experiment invalid -- failed required validity gate(s): " + str(validity_check["failed"]),
                        None, experiment_id, exp_type)

    # STEP 2: Required evidence
    evidence_check = _check_gate_list(experiment_id, reqs["evidence_required"], experiment_record)
    if evidence_check["missing"]:
        return Verdict("INCONCLUSIVE", "required evidence not yet evaluated: " + str(evidence_check["missing"]),
                        None, experiment_id, exp_type)
    if evidence_check["failed"]:
        return Verdict("REJECTED", "preregistered hypothesis/evidence not supported: " + str(evidence_check["failed"]),
                        None, experiment_id, exp_type)

    # STEP 3: Claimed conditional evidence (currently only oos_survived uses this mechanism)
    claimed_conditional = []
    for cond_name in reqs.get("evidence_conditional", []):
        if cond_name == "oos_survived":
            if _claims_oos(experiment_record):
                claimed_conditional.append(cond_name)
        else:
            try:
                is_applicable = gates.get_locked_applicability(experiment_record, cond_name)
            except gates.ApplicabilityNotLockedError:
                is_applicable = False
            if is_applicable:
                claimed_conditional.append(cond_name)

    conditional_check = _check_gate_list(experiment_id, claimed_conditional, experiment_record)
    if conditional_check["missing"]:
        return Verdict("INCONCLUSIVE", "claimed conditional evidence not yet evaluated: " + str(conditional_check["missing"]),
                        None, experiment_id, exp_type)
    if conditional_check["failed"]:
        return Verdict("REJECTED", "claimed conditional evidence failed: " + str(conditional_check["failed"]),
                        None, experiment_id, exp_type)

    # STEP 4: Everything required AND claimed passed -- apply experiment-type ceiling
    final_status = reqs["max_verdict"]
    promising_meaning = reqs["promising_meaning"] if final_status == "PROMISING" else None
    return Verdict(final_status, "all validity/evidence requirements satisfied for experiment_type=" + exp_type,
                    promising_meaning, experiment_id, exp_type)
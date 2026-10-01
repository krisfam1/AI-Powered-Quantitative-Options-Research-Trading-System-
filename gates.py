"""
gates.py -- represents and evaluates individual validity/evidence
gates. Does NOT calculate the final verdict (that is verdict.py's
exclusive responsibility). Applicability comes EXCLUSIVELY from the
locked ExperimentConfig.applicability_lock -- never inferred, never
alterable after preregistration.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import db_interface

VALIDITY_GATES = frozenset({
    "data_integrity", "lookahead_audit", "timestamp_safety",
    "sample_size_adequacy", "statistical_testing", "reproduction",
})

EVIDENCE_GATES = frozenset({
    "primary_test_significant", "primary_performance_test_significant",
    "effect_size_meets_threshold", "multiple_testing_survived",
    "concentration_check", "robustness_survived", "oos_survived",
    "pricing_accuracy_meets_threshold", "pricing_coverage_meets_threshold",
})

ALL_RECOGNIZED_GATES = VALIDITY_GATES | EVIDENCE_GATES


class UnrecognizedGateNameError(Exception):
    """Raised when a gate name outside the controlled vocabulary is used."""
    pass


class InconsistentGateStateError(Exception):
    """Raised when applicable/run/passed violate the locked three-state semantics."""
    pass


class ApplicabilityNotLockedError(Exception):
    """Raised when a gate's applicability was never declared in the
    experiment's locked applicability_lock -- applicability can NEVER
    be inferred or assumed, only read from what was preregistered."""
    pass


@dataclass(frozen=True)
class GateResult:
    gate_name: str
    applicable: bool
    run: bool
    passed: Optional[bool]
    evidence_summary: str
    evaluated_at: Optional[str]

    def __post_init__(self):
        if self.gate_name not in ALL_RECOGNIZED_GATES:
            raise UnrecognizedGateNameError(
                "Unrecognized gate name: " + repr(self.gate_name) +
                ". Must be one of: " + str(sorted(ALL_RECOGNIZED_GATES))
            )

        # Enforce the locked three-state semantics -- no other combination is valid.
        if not self.applicable:
            if self.run:
                raise InconsistentGateStateError(
                    "applicable=False but run=True -- a gate that does not apply cannot have been executed."
                )
            if self.passed is not None:
                raise InconsistentGateStateError(
                    "applicable=False but passed is not None -- a non-applicable gate has no pass/fail state."
                )
        else:
            if not self.run:
                if self.passed is not None:
                    raise InconsistentGateStateError(
                        "run=False but passed is not None -- an unrun gate cannot have a pass/fail result "
                        "(this would silently treat 'not yet run' as a real outcome)."
                    )
            else:
                if self.passed is None:
                    raise InconsistentGateStateError(
                        "run=True but passed is None -- an executed gate must have an explicit True/False result."
                    )


def is_validity_gate(gate_name: str) -> bool:
    return gate_name in VALIDITY_GATES


def is_evidence_gate(gate_name: str) -> bool:
    return gate_name in EVIDENCE_GATES


def get_locked_applicability(experiment_record: dict, gate_name: str) -> bool:
    """
    Reads applicability EXCLUSIVELY from the experiment's locked,
    persisted applicability_lock (set at preregistration, never
    alterable afterward). Raises if this gate's applicability was
    never declared -- gates.py NEVER infers or assumes applicability.
    """
    import json
    lock_pairs = json.loads(experiment_record["applicability_lock"])
    lock_dict = {name: applicable for name, applicable in lock_pairs}
    if gate_name not in lock_dict:
        raise ApplicabilityNotLockedError(
            "Gate '" + gate_name + "' applicability was never declared in this experiment's "
            "locked applicability_lock at preregistration. Applicability cannot be inferred after the fact."
        )
    return lock_dict[gate_name]


def evaluate_gate(experiment_id: str, gate_name: str, run: bool, passed: Optional[bool], evidence_summary: str) -> GateResult:
    """
    Records a gate evaluation result. Applicability is looked up from
    the experiment's LOCKED applicability_lock (never passed in or
    inferred by the caller). Uses INSERT-only persistence -- a
    correction to a prior gate result creates a NEW row, never
    overwrites the original (append-only history, per point 9).
    """
    experiment_record = db_interface.get_experiment_record(experiment_id)
    if experiment_record is None:
        raise ValueError("No preregistered experiment found with id: " + experiment_id)

    applicable = get_locked_applicability(experiment_record, gate_name)

    if not applicable:
        # A non-applicable gate can only ever be recorded as applicable=False,
        # run=False, passed=None -- caller-supplied run/passed for a
        # non-applicable gate are simply ignored/overridden to the only valid state.
        result = GateResult(gate_name, applicable=False, run=False, passed=None,
                             evidence_summary=evidence_summary, evaluated_at=None)
    else:
        evaluated_at = datetime.now(timezone.utc).isoformat() if run else None
        result = GateResult(gate_name, applicable=True, run=run, passed=passed,
                             evidence_summary=evidence_summary, evaluated_at=evaluated_at)

    with sqlite3.connect(db_interface.DB_PATH) as conn:
        conn.execute(
            "INSERT INTO experiment_gate_checklist (experiment_id, gate_name, applicable, run, passed, evidence_summary) VALUES (?,?,?,?,?,?)",
            (experiment_id, result.gate_name, int(result.applicable), int(result.run),
             (None if result.passed is None else int(result.passed)), result.evidence_summary)
        )
        conn.commit()

    return result


def get_gate_results(experiment_id: str) -> list:
    """
    Read-only fetch of ALL recorded gate results for an experiment,
    in insertion order -- includes the FULL correction history if any
    gate was re-evaluated (append-only, nothing hidden or overwritten).
    Consumed by verdict.py (not implemented in this layer).
    """
    with sqlite3.connect(db_interface.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM experiment_gate_checklist WHERE experiment_id=? ORDER BY id ASC",
            (experiment_id,)
        ).fetchall()
    results = []
    for row in rows:
        results.append(GateResult(
            gate_name=row["gate_name"], applicable=bool(row["applicable"]), run=bool(row["run"]),
            passed=(None if row["passed"] is None else bool(row["passed"])),
            evidence_summary=row["evidence_summary"], evaluated_at=None,  # evaluated_at not persisted separately in existing table
        ))
    return results
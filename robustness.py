"""
robustness.py -- supporting-evidence layer for robustness testing.
Methodology-agnostic: does not prescribe WHICH robustness checks to
run (parameter perturbation, ticker removal, etc.) -- only aggregates
declared-vs-actual results into an honest three-state outcome.

CRITICAL DISTINCTION: "the checks we happened to record passed" is
NOT the same claim as "the complete declared robustness battery
passed." This module enforces that distinction structurally.

Read-only with respect to experiment/gate/V1/Feature Factory data.
Reuses the existing experiment_robustness_tests table -- no new
persistence architecture. Does NOT call gates.evaluate_gate() itself;
the caller is responsible for recording the resulting
robustness_survived gate, exactly as multiple_testing.py's pattern.
"""

import sqlite3
from dataclasses import dataclass
from typing import Tuple
import db_interface

SURVIVED = "SURVIVED"
FAILED = "FAILED"
INSUFFICIENT_COVERAGE = "INSUFFICIENT_COVERAGE"


@dataclass(frozen=True)
class RobustnessCheckStatus:
    """Per-check status, distinguishing declared-not-evaluated from
    evaluated-survived from evaluated-failed -- never collapsed into
    a single boolean."""
    check_name: str
    declared: bool
    evaluated: bool
    survived: bool  # meaningless (False by convention) if evaluated=False -- always check `evaluated` first


@dataclass(frozen=True)
class RobustnessResult:
    """Full, auditable result. status is the three-state outcome;
    per_check gives the complete breakdown so the aggregate result is
    never a black box."""
    status: str  # SURVIVED / FAILED / INSUFFICIENT_COVERAGE
    experiment_id: str
    declared_count: int
    evaluated_count: int
    survived_count: int
    per_check: Tuple[RobustnessCheckStatus, ...]
    reasoning: str


def compute_robustness_survival(experiment_id: str) -> RobustnessResult:
    """
    PURE, READ-ONLY. Compares the experiment's LOCKED
    declared_robustness_checks (from ExperimentConfig, set at
    preregistration, immutable) against what has actually been
    recorded in experiment_robustness_tests.

    Rule (explicitly approved, not a default-pass):
      SURVIVED  iff every declared check has been evaluated AND every
                    evaluated check's survived=True.
      FAILED    iff at least one declared check was evaluated and
                    showed survived=False (regardless of whether other
                    declared checks remain unevaluated -- a known
                    failure is reported immediately, not hidden behind
                    "insufficient coverage").
      INSUFFICIENT_COVERAGE iff no declared check has failed, but at
                    least one declared check has not yet been evaluated
                    (including the case of zero declared checks --
                    genuinely undeclared robustness testing is treated
                    as insufficient, not vacuously "survived").
    """
    experiment_record = db_interface.get_experiment_record(experiment_id)
    if experiment_record is None:
        raise ValueError("No preregistered experiment found with id: " + experiment_id)

    import json
    declared_checks = json.loads(experiment_record["declared_robustness_checks"]) if experiment_record.get("declared_robustness_checks") else []

    with sqlite3.connect(db_interface.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        recorded_rows = conn.execute(
            "SELECT * FROM experiment_robustness_tests WHERE experiment_id=?", (experiment_id,)
        ).fetchall()

    # Build a lookup of the LATEST recorded result per test_type (using the
    # same "highest id = effective result" convention as verdict.py's
    # get_effective_gate_result, for consistency across the framework).
    recorded_by_type = {}
    for row in recorded_rows:
        existing = recorded_by_type.get(row["test_type"])
        if existing is None or row["id"] > existing["id"]:
            recorded_by_type[row["test_type"]] = row

    per_check = []
    for check_name in declared_checks:
        recorded = recorded_by_type.get(check_name)
        if recorded is None:
            per_check.append(RobustnessCheckStatus(check_name, declared=True, evaluated=False, survived=False))
        else:
            per_check.append(RobustnessCheckStatus(check_name, declared=True, evaluated=True, survived=bool(recorded["survived"])))

    declared_count = len(declared_checks)
    evaluated_count = len([c for c in per_check if c.evaluated])
    survived_count = len([c for c in per_check if c.evaluated and c.survived])
    failed_checks = [c.check_name for c in per_check if c.evaluated and not c.survived]
    unevaluated_checks = [c.check_name for c in per_check if not c.evaluated]

    if failed_checks:
        status = FAILED
        reasoning = "declared robustness check(s) failed: " + str(failed_checks)
    elif unevaluated_checks:
        status = INSUFFICIENT_COVERAGE
        reasoning = "declared robustness check(s) not yet evaluated: " + str(unevaluated_checks) + " (declared_count=" + str(declared_count) + ")"
    elif declared_count == 0:
        status = INSUFFICIENT_COVERAGE
        reasoning = "no robustness checks were declared for this experiment -- undeclared robustness cannot be treated as survived"
    else:
        status = SURVIVED
        reasoning = "all " + str(declared_count) + " declared robustness check(s) were evaluated and survived"

    return RobustnessResult(
        status=status, experiment_id=experiment_id, declared_count=declared_count,
        evaluated_count=evaluated_count, survived_count=survived_count,
        per_check=tuple(per_check), reasoning=reasoning,
    )
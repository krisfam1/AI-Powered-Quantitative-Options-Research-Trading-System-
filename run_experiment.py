"""
run_experiment.py -- thin orchestration layer. Contains NO research
logic of its own; only sequences the already-tested framework pieces
(gates, verdict, multiple_testing, robustness, db_interface) in the
correct, locked order. Zero imports of any V1 or live-trading file --
structurally incapable of touching V1.

Locked execution sequence:
  Fetch + verify PREREGISTERED -> check rerun requirement ->
  create execution record -> run executor -> persist results ->
  robustness -> multiple testing -> other gates -> capture gate
  snapshot -> calculate verdict -> persist verdict + execution link +
  snapshot -> complete execution.
"""

import sqlite3
import json
from datetime import datetime, timezone
import db_interface
import gates
import verdict
import multiple_testing
import robustness

DB_PATH = db_interface.DB_PATH


class RunnerError(Exception):
    pass


def _init_runner_schema():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS experiment_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT,
                run_reason TEXT,
                started_at TEXT,
                completed_at TEXT,
                status TEXT,           -- RUNNING / COMPLETED / FAILED
                error_summary TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS experiment_verdicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT,
                execution_id INTEGER,
                status TEXT,
                reasoning TEXT,
                promising_meaning TEXT,
                gate_checklist_max_id INTEGER,
                calculated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS experiment_primary_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT,
                execution_id INTEGER,
                estimate REAL,
                p_one_sided REAL,
                p_opposite_one_sided REAL,
                confidence_bound REAL,
                n INTEGER,
                t_stat REAL,
                recorded_at TEXT
            )
        """)  # tiered grading (tiered_verdict.py): append-only; the latest row per experiment is effective
        conn.commit()


_init_runner_schema()


def run_experiment(experiment_id: str, executor, run_reason: str = None):
    """
    executor: a callable(locked_config_dict) -> {
        "gate_results": {gate_name: {"run": bool, "passed": bool|None, "evidence_summary": str}, ...},
        "robustness_results": {check_name: {"survived": bool, "description": str}, ...},  # optional
        "primary_p_value": float,  # optional
        "tiered_primary": {"estimate", "p_one_sided", "p_opposite_one_sided", "confidence_bound", "n",
                           "t_stat" (optional)},  # required for tiered_grading experiments
    }
    Tiered-grading experiments (tiered_verdict.py) are graded per check (hard gates vs soft checks),
    so the legacy all-or-nothing robustness_survived gate is not computed for them.
    Contains NO research logic itself -- caller-supplied, fully external
    to this module.
    """
    # ---- [0] Fetch + verify PREREGISTERED (BEFORE any execution record is created) ----
    experiment_record = db_interface.get_experiment_record(experiment_id)
    if experiment_record is None:
        raise RunnerError("No experiment found with id: " + experiment_id)
    if experiment_record["state"] != "PREREGISTERED":
        raise RunnerError(
            "Experiment '" + experiment_id + "' is not in PREREGISTERED state (current: " +
            str(experiment_record["state"]) + "). Cannot execute."
        )

    # ---- [0b] Check rerun requirement ----
    with sqlite3.connect(DB_PATH) as conn:
        prior_count = conn.execute(
            "SELECT COUNT(*) FROM experiment_executions WHERE experiment_id=?", (experiment_id,)
        ).fetchone()[0]
    if prior_count > 0 and not run_reason:
        raise RunnerError(
            "Experiment '" + experiment_id + "' has already been executed " + str(prior_count) +
            " time(s). Re-running requires an explicit run_reason (e.g. 'corrected input data', "
            "'rerun after gate correction'). This is not a default-allowed operation."
        )
    if not run_reason:
        run_reason = "initial_run"

    # ---- [0c] Create execution record ----
    started_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "INSERT INTO experiment_executions (experiment_id, run_reason, started_at, status) VALUES (?,?,?,?)",
            (experiment_id, run_reason, started_at, "RUNNING")
        )
        execution_id = cursor.lastrowid
        conn.commit()

    try:
        # ---- [1] Run executor ----
        raw_results = executor(experiment_record)

        # ---- [2] Persist robustness test results (append-only) ----
        robustness_results = raw_results.get("robustness_results", {})
        with sqlite3.connect(DB_PATH) as conn:
            for check_name, r in robustness_results.items():
                conn.execute(
                    "INSERT INTO experiment_robustness_tests (experiment_id, test_type, test_description, result_summary, survived) VALUES (?,?,?,?,?)",
                    (experiment_id, check_name, r.get("description", ""), "recorded via run_experiment", int(r["survived"]))
                )
            conn.commit()

        # ---- [2b] Tiered grading: persist the primary result (append-only) ----
        import tiered_verdict
        is_tiered = tiered_verdict.declaration_from_parameters(json.loads(experiment_record["parameters"])) is not None
        if is_tiered:
            tp = raw_results.get("tiered_primary")
            if tp is not None:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        "INSERT INTO experiment_primary_results (experiment_id, execution_id, estimate, p_one_sided, "
                        "p_opposite_one_sided, confidence_bound, n, t_stat, recorded_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        (experiment_id, execution_id, tp["estimate"], tp["p_one_sided"], tp["p_opposite_one_sided"],
                         tp["confidence_bound"], tp["n"], tp.get("t_stat"), datetime.now(timezone.utc).isoformat()))
                    conn.commit()

        # ---- [3] Compute + record robustness_survived gate (if applicable; legacy grading only) ----
        try:
            if is_tiered:
                raise gates.ApplicabilityNotLockedError("tiered grading: robustness graded per check")
            gates.get_locked_applicability(experiment_record, "robustness_survived")
            rb_result = robustness.compute_robustness_survival(experiment_id)
            gates.evaluate_gate(experiment_id, "robustness_survived",
                                 run=True, passed=(rb_result.status == robustness.SURVIVED),
                                 evidence_summary=rb_result.reasoning)
        except gates.ApplicabilityNotLockedError:
            pass  # not declared for this experiment -- nothing to do

        # ---- [4] Compute + record multiple_testing_survived gate (if applicable) ----
        try:
            gates.get_locked_applicability(experiment_record, "multiple_testing_survived")
            p_value = raw_results.get("primary_p_value")
            if p_value is not None:
                mt_result = multiple_testing.check_multiple_testing_survived(experiment_id, p_value)
                gates.evaluate_gate(experiment_id, "multiple_testing_survived",
                                     run=True, passed=mt_result["survived"],
                                     evidence_summary="p=" + str(p_value) + " vs threshold=" + str(mt_result["threshold"].per_test_alpha))
        except gates.ApplicabilityNotLockedError:
            pass

        # ---- [5] Record all other executor-reported gates ----
        for gate_name, g in raw_results.get("gate_results", {}).items():
            if gate_name in ("robustness_survived", "multiple_testing_survived"):
                continue  # already handled above via the computed path (robustness_survived: legacy only)
            gates.evaluate_gate(experiment_id, gate_name,
                                 run=g["run"], passed=g.get("passed"),
                                 evidence_summary=g.get("evidence_summary", ""))

        # ---- [6] Capture gate snapshot (exact evidentiary cutoff) ----
        with sqlite3.connect(DB_PATH) as conn:
            max_id_row = conn.execute(
                "SELECT MAX(id) FROM experiment_gate_checklist WHERE experiment_id=?", (experiment_id,)
            ).fetchone()
            gate_checklist_max_id = max_id_row[0] if max_id_row and max_id_row[0] is not None else 0

        # ---- [7] Calculate verdict ----
        v = verdict.calculate_verdict(experiment_id)

        # ---- [8] Persist verdict, linked to execution + snapshot ----
        calculated_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO experiment_verdicts (experiment_id, execution_id, status, reasoning, promising_meaning, gate_checklist_max_id, calculated_at) VALUES (?,?,?,?,?,?,?)",
                (experiment_id, execution_id, v.status, v.reasoning, v.promising_meaning, gate_checklist_max_id, calculated_at)
            )
            conn.execute(
                "UPDATE experiment_executions SET completed_at=?, status=? WHERE id=?",
                (calculated_at, "COMPLETED", execution_id)
            )
            conn.commit()

        return v

    except Exception as e:
        # ---- Executor crash / any failure: mark FAILED, produce NO verdict ----
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE experiment_executions SET completed_at=?, status=?, error_summary=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), "FAILED", str(e), execution_id)
            )
            conn.commit()
        raise
"""
db_interface.py -- the ONLY module that reads/writes research_database.db
for the Experiment Framework. ExperimentConfig itself NEVER touches this
module (per Fix 1, v4 architecture) -- only preregister_experiment()
(in experiment.py) calls into here.
"""

import sqlite3
import json
from datetime import datetime, timezone
from canonical_hash import compute_config_hash

DB_PATH = "research_database.db"


class TestingFamilyNotFoundError(Exception):
    pass


class DuplicateExperimentError(Exception):
    pass


def _init_extended_schema():
    """
    Adds the columns/tables needed for the Experiment Framework's
    preregistration layer, on top of the already-existing experiments
    table (built earlier tonight). Additive only -- never drops or
    alters existing columns/data.
    """
    with sqlite3.connect(DB_PATH) as conn:
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(experiments)").fetchall()}
        new_cols = {
            "config_hash": "TEXT",
            "applicability_lock": "TEXT",       # JSON-serialized tuple-of-pairs
            "oos_validation_claimed": "INTEGER", # boolean
            "testing_family_declaration": "TEXT",
            "state": "TEXT",                     # DRAFT / PREREGISTERED / ... (state machine)
            "declared_robustness_checks": "TEXT", # JSON-serialized tuple of check names
        }
        for col, coltype in new_cols.items():
            if col not in existing_cols:
                conn.execute("ALTER TABLE experiments ADD COLUMN " + col + " " + coltype)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS testing_families (
                family_id TEXT PRIMARY KEY,
                correction_method TEXT,
                family_alpha REAL,
                created_at TEXT,
                creating_experiment_id TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS testing_family_members (
                family_id TEXT,
                experiment_id TEXT,
                joined_at TEXT,
                PRIMARY KEY (family_id, experiment_id)
            )
        """)
        conn.commit()


def testing_family_exists(family_id: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT 1 FROM testing_families WHERE family_id=?", (family_id,)).fetchone()
        return row is not None


def create_testing_family(conn, family_id: str, creating_experiment_id: str,
                           correction_method: str = "bonferroni", family_alpha: float = 0.05):
    """Takes an OPEN connection (conn) -- caller controls the transaction boundary."""
    existing = conn.execute("SELECT 1 FROM testing_families WHERE family_id=?", (family_id,)).fetchone()
    if existing is not None:
        raise ValueError("Testing family already exists, cannot create again: " + family_id)
    conn.execute(
        "INSERT INTO testing_families (family_id, correction_method, family_alpha, created_at, creating_experiment_id) VALUES (?,?,?,?,?)",
        (family_id, correction_method, family_alpha, datetime.now(timezone.utc).isoformat(), creating_experiment_id)
    )
    conn.execute(
        "INSERT INTO testing_family_members (family_id, experiment_id, joined_at) VALUES (?,?,?)",
        (family_id, creating_experiment_id, datetime.now(timezone.utc).isoformat())
    )


def register_family_member(conn, family_id: str, experiment_id: str):
    """Takes an OPEN connection -- caller controls the transaction boundary."""
    existing_family = conn.execute("SELECT 1 FROM testing_families WHERE family_id=?", (family_id,)).fetchone()
    if existing_family is None:
        raise TestingFamilyNotFoundError("Referenced testing family does not exist: " + family_id)
    already_member = conn.execute(
        "SELECT 1 FROM testing_family_members WHERE family_id=? AND experiment_id=?", (family_id, experiment_id)
    ).fetchone()
    if already_member is not None:
        raise ValueError("Experiment is already a member of this family: " + experiment_id + " / " + family_id)
    conn.execute(
        "INSERT INTO testing_family_members (family_id, experiment_id, joined_at) VALUES (?,?,?)",
        (family_id, experiment_id, datetime.now(timezone.utc).isoformat())
    )


def persist_preregistration(config, preregistered_at: str):
    """
    Persists a frozen ExperimentConfig as a PREREGISTERED experiment
    record. Uses plain INSERT (never INSERT OR REPLACE) so the existing
    PRIMARY KEY constraint on experiment_id provides automatic duplicate
    rejection. Called from experiment.py's preregister_experiment(),
    inside the SAME transaction as any testing-family operations.

    Takes an OPEN connection -- caller controls the transaction boundary.
    """
    def _insert(conn):
        conn.execute("""
            INSERT INTO experiments (
                experiment_id, created_at, experiment_type, hypothesis, research_question,
                preregistered_at, hypothesis_locked, hypothesis_amended_after_results,
                dataset_version, date_range_start, date_range_end, universe, option_type,
                features_used, parameters, model_version, pricing_methodology, execution_assumptions,
                train_period_start, train_period_end, validation_period_start, validation_period_end,
                test_period_start, test_period_end, sample_size,
                config_hash, applicability_lock, oos_validation_claimed, testing_family_declaration, state,
                declared_robustness_checks
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            config.experiment_id, preregistered_at, config.experiment_type, config.hypothesis, config.research_question,
            preregistered_at, 1, 0,
            config.dataset_version, config.date_range[0], config.date_range[1],
            json.dumps(list(config.universe)), config.option_type,
            json.dumps([list(f) for f in config.features_used]),
            json.dumps([list(p) for p in config.parameters]),
            config.model_version, config.pricing_methodology, config.execution_assumptions,
            config.train_period[0] if config.train_period else None, config.train_period[1] if config.train_period else None,
            config.validation_period[0] if config.validation_period else None, config.validation_period[1] if config.validation_period else None,
            config.test_period[0] if config.test_period else None, config.test_period[1] if config.test_period else None,
            None,  # sample_size -- filled in later, at RESULTS_RECORDED
            config.config_hash, json.dumps([list(a) for a in config.applicability_lock]),
            int(config.oos_validation_claimed), config.testing_family_declaration, "PREREGISTERED",
            json.dumps(list(config.declared_robustness_checks)),
        ))
    return _insert


def get_experiment_record(experiment_id: str):
    """Read-only fetch, for verification/testing purposes."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM experiments WHERE experiment_id=?", (experiment_id,)).fetchone()
        return dict(row) if row else None


def get_connection():
    """Returns a raw connection for the orchestrator to manage its own transaction boundary."""
    return sqlite3.connect(DB_PATH)


_init_extended_schema()
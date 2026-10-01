"""
Experiment -- the mutable wrapper around a frozen ExperimentConfig,
holding lifecycle state. preregister_experiment() is the ONLY function
that touches the database during preregistration (per Fix 1, v4).
"""

import re
import sqlite3
from datetime import datetime, timezone
import db_interface
from experiment_config import ExperimentConfig, InvalidExperimentConfigError

VALID_STATES = ("DRAFT", "PREREGISTERED", "EXECUTING", "RESULTS_RECORDED", "GATES_EVALUATED", "VERDICT_ISSUED", "PERSISTED")

_FAMILY_DECL_PATTERN = re.compile(r"^(INDEPENDENT_SINGLE|NEW_FAMILY:([\w\-]+)|EXISTING_FAMILY:([\w\-]+))$")


class PreregistrationError(Exception):
    """Raised when preregistration fails for any reason. The caller can
    assume NO partial database state was left behind -- see the
    transaction handling in preregister_experiment()."""
    pass


class Experiment:
    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.state = "DRAFT"
        self.preregistered_at = None


def _parse_declaration(declaration: str):
    m = _FAMILY_DECL_PATTERN.match(declaration)
    if declaration == "INDEPENDENT_SINGLE":
        return ("INDEPENDENT_SINGLE", None)
    if declaration.startswith("NEW_FAMILY:"):
        return ("NEW_FAMILY", declaration.split(":", 1)[1])
    if declaration.startswith("EXISTING_FAMILY:"):
        return ("EXISTING_FAMILY", declaration.split(":", 1)[1])
    raise PreregistrationError("Malformed testing_family_declaration (should have been caught at config construction): " + repr(declaration))


def preregister_experiment(config: ExperimentConfig) -> Experiment:
    """
    Validates and persists a frozen ExperimentConfig as a PREREGISTERED
    experiment. This is the ONLY function that touches the database
    during preregistration -- ExperimentConfig itself never does.

    Transaction safety: family creation/registration and experiment
    persistence happen inside ONE database transaction. If ANY step
    fails, the entire transaction rolls back -- no partial state
    (an orphaned family with no member, or a family membership with
    no corresponding experiment record) is ever left behind.
    """
    kind, family_id = _parse_declaration(config.testing_family_declaration)
    preregistered_at = datetime.now(timezone.utc).isoformat()
    insert_fn = db_interface.persist_preregistration(config, preregistered_at)

    conn = db_interface.get_connection()
    try:
        if kind == "NEW_FAMILY":
            db_interface.create_testing_family(conn, family_id, config.experiment_id)
        elif kind == "EXISTING_FAMILY":
            db_interface.register_family_member(conn, family_id, config.experiment_id)
        # INDEPENDENT_SINGLE: no family action

        insert_fn(conn)  # the experiment record itself

        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise PreregistrationError("Experiment ID already exists (duplicate preregistration rejected): " + config.experiment_id) from e
    except Exception as e:
        conn.rollback()
        raise PreregistrationError("Preregistration failed, transaction rolled back, no partial state persisted: " + str(e)) from e
    finally:
        conn.close()

    experiment = Experiment(config)
    experiment.state = "PREREGISTERED"
    experiment.preregistered_at = preregistered_at
    return experiment
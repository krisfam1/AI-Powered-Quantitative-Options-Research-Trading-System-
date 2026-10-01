"""
multiple_testing.py -- computes multiple-testing-corrected significance
thresholds. READ-ONLY with respect to experiment/gate data: does NOT
create or modify gate results (that remains gates.py's exclusive
responsibility) or touch V1/Feature Factory/existing records.

Bonferroni is fully implemented. Benjamini-Hochberg is explicitly
deferred -- raises a clear NotSupportedError rather than a partial/
misleading implementation, since BH requires a closed family with a
complete, fixed p-value set (a separate architectural decision).
"""

import sqlite3
from dataclasses import dataclass
from typing import Optional
import db_interface

STANDARD_ALPHA = 0.05  # THE single, authoritative default significance level -- referenced everywhere, never re-hardcoded


class TestingFamilyNotFoundError(Exception):
    pass


class UnsupportedCorrectionMethodError(Exception):
    pass


class BenjaminiHochbergNotSupportedError(UnsupportedCorrectionMethodError):
    """BH requires a closed testing family with a fixed member set and
    complete p-value collection -- a separate, deferred architectural
    decision (family closure semantics, immutability, versioning).
    Not implemented here."""
    pass


@dataclass(frozen=True)
class ThresholdResult:
    """Full metadata for reproducibility/auditability -- not just a
    bare number. Explicitly exposes the TEMPORAL nature of open-family
    Bonferroni correction: member_count_used reflects the family's
    CURRENT size at calculation time, which can change for future
    recalculations of the same experiment."""
    correction_method: str          # "bonferroni" or "none_single_test"
    family_id: Optional[str]        # None for INDEPENDENT_SINGLE
    family_alpha: float
    member_count_used: int          # current count AT THIS CALCULATION -- may differ on later recalculation
    per_test_alpha: float
    is_temporally_stable: bool      # False whenever member_count_used could change for an OPEN family


def _parse_declaration(declaration: str):
    if declaration == "INDEPENDENT_SINGLE":
        return ("INDEPENDENT_SINGLE", None)
    if declaration.startswith("NEW_FAMILY:"):
        return ("FAMILY", declaration.split(":", 1)[1])
    if declaration.startswith("EXISTING_FAMILY:"):
        return ("FAMILY", declaration.split(":", 1)[1])
    raise ValueError("Malformed testing_family_declaration (should have been caught at preregistration): " + repr(declaration))


def compute_per_test_alpha(experiment_id: str) -> ThresholdResult:
    """
    Computes the applicable per-test significance threshold for an
    experiment, based on its LOCKED testing_family_declaration.
    Separated from survival determination per the review -- this
    function ONLY computes the threshold and its full metadata.

    READ-ONLY: makes no modification to any experiment, gate, or
    family record.
    """
    experiment_record = db_interface.get_experiment_record(experiment_id)
    if experiment_record is None:
        raise ValueError("No preregistered experiment found with id: " + experiment_id)

    decl_kind, family_id = _parse_declaration(experiment_record["testing_family_declaration"])

    if decl_kind == "INDEPENDENT_SINGLE":
        return ThresholdResult(
            correction_method="none_single_test", family_id=None, family_alpha=STANDARD_ALPHA,
            member_count_used=1, per_test_alpha=STANDARD_ALPHA, is_temporally_stable=True,
        )

    # FAMILY case
    with sqlite3.connect(db_interface.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        family_row = conn.execute("SELECT * FROM testing_families WHERE family_id=?", (family_id,)).fetchone()
        if family_row is None:
            raise TestingFamilyNotFoundError("Referenced testing family does not exist: " + family_id)

        correction_method = family_row["correction_method"]
        family_alpha = family_row["family_alpha"]

        if correction_method == "bonferroni":
            member_count = conn.execute(
                "SELECT COUNT(*) FROM testing_family_members WHERE family_id=?", (family_id,)
            ).fetchone()[0]
            per_test_alpha = family_alpha / member_count
            return ThresholdResult(
                correction_method="bonferroni", family_id=family_id, family_alpha=family_alpha,
                member_count_used=member_count, per_test_alpha=per_test_alpha,
                is_temporally_stable=False,  # OPEN family -- this count may grow, changing future recalculations
            )

        if correction_method == "benjamini_hochberg":
            raise BenjaminiHochbergNotSupportedError(
                "Benjamini-Hochberg correction is not yet implemented. BH requires a closed testing family "
                "with a fixed member set and complete p-value collection -- this is a separate, deferred "
                "architectural decision (family closure semantics, immutability, versioning) not yet designed. "
                "Family: " + family_id
            )

        raise UnsupportedCorrectionMethodError(
            "Unrecognized correction_method for family '" + family_id + "': " + repr(correction_method)
        )


def check_multiple_testing_survived(experiment_id: str, observed_p_value: float) -> dict:
    """
    Compares an observed p-value against the applicable per-test
    threshold. Convention (explicitly documented, per review): p <=
    alpha counts as survival (standard convention).

    Returns a dict with both the boolean result AND the full
    ThresholdResult metadata, so callers (and gates.py, when recording
    the resulting evidence) have complete auditability -- this
    function does NOT itself record anything to gates.py or any
    persistence layer.
    """
    threshold_result = compute_per_test_alpha(experiment_id)
    survived = observed_p_value <= threshold_result.per_test_alpha
    return {
        "survived": survived,
        "observed_p_value": observed_p_value,
        "threshold": threshold_result,
    }
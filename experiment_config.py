"""
ExperimentConfig -- a pure, immutable description of an experiment.
NO database access anywhere in this module (Fix 1, v4). Can be
constructed standalone, offline, for unit testing, or before any DB
connection exists.
"""

from dataclasses import dataclass, field
from typing import Tuple, Optional
import re
from canonical_hash import compute_config_hash, _deep_freeze, UncanonicalizableValueError

VALID_EXPERIMENT_TYPES = (
    "baseline", "signal_research", "feature_test", "model_test",
    "exit_test", "pricing_validation", "robustness", "oos_validation",
)

_FAMILY_DECL_PATTERN = re.compile(r"^(INDEPENDENT_SINGLE|NEW_FAMILY:[\w\-]+|EXISTING_FAMILY:[\w\-]+)$")


class InvalidExperimentConfigError(Exception):
    """Raised for any malformed config field at construction time."""
    pass


def _validate_declaration_format(declaration: str):
    """
    STRING FORMAT VALIDATION ONLY -- per Fix 1 (v4), this function does
    NOT query the database to check whether a referenced family exists.
    That check belongs to preregister_experiment() (the framework layer),
    not to config construction.
    """
    if not isinstance(declaration, str) or not _FAMILY_DECL_PATTERN.match(declaration):
        raise InvalidExperimentConfigError(
            "testing_family_declaration must be exactly 'INDEPENDENT_SINGLE', "
            "'NEW_FAMILY:<id>', or 'EXISTING_FAMILY:<id>' (id = word characters/hyphens only). Got: " + repr(declaration)
        )


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_id: str
    experiment_type: str
    hypothesis: str
    research_question: str
    dataset_version: str
    date_range: Tuple[str, str]
    universe: Tuple[str, ...]
    option_type: str
    features_used: Tuple[Tuple[str, str], ...]
    parameters: Tuple[Tuple[str, object], ...]
    model_version: Optional[str]
    pricing_methodology: str
    execution_assumptions: str
    train_period: Optional[Tuple[str, str]]
    validation_period: Optional[Tuple[str, str]]
    test_period: Optional[Tuple[str, str]]
    random_seeds: Tuple[int, ...]
    code_version: Optional[str]
    testing_family_declaration: str
    applicability_lock: Tuple[Tuple[str, bool], ...]
    oos_validation_claimed: bool
    declared_robustness_checks: Tuple[str, ...]
    config_hash: str = field(init=False)

    def __post_init__(self):
        # --- Basic field validation ---
        if self.experiment_type not in VALID_EXPERIMENT_TYPES:
            raise InvalidExperimentConfigError(
                "experiment_type must be one of " + str(VALID_EXPERIMENT_TYPES) + ", got: " + repr(self.experiment_type)
            )
        if not self.hypothesis or not self.hypothesis.strip():
            raise InvalidExperimentConfigError("hypothesis cannot be empty")
        if not self.research_question or not self.research_question.strip():
            raise InvalidExperimentConfigError("research_question cannot be empty")

        _validate_declaration_format(self.testing_family_declaration)

        if self.oos_validation_claimed and self.test_period is None:
            raise InvalidExperimentConfigError(
                "oos_validation_claimed=True requires a non-None test_period to be set at the SAME preregistration time -- "
                "OOS intent must be locked together with the actual test period, not asserted independently."
            )

        # --- Deep-freeze every field that could contain mutable input ---
        # (universe/features_used/random_seeds/applicability_lock may arrive
        # as lists from the caller; parameters may arrive as a raw dict)
        try:
            object.__setattr__(self, "universe", _deep_freeze(tuple(self.universe)))
            object.__setattr__(self, "features_used", _deep_freeze(tuple(self.features_used)))
            object.__setattr__(self, "random_seeds", _deep_freeze(tuple(self.random_seeds)))
            object.__setattr__(self, "applicability_lock", _deep_freeze(tuple(self.applicability_lock)))
            object.__setattr__(self, "declared_robustness_checks", _deep_freeze(tuple(self.declared_robustness_checks)))

            if isinstance(self.parameters, dict):
                object.__setattr__(self, "parameters", _deep_freeze(self.parameters))
            else:
                object.__setattr__(self, "parameters", _deep_freeze(tuple(self.parameters)))
        except UncanonicalizableValueError as e:
            raise InvalidExperimentConfigError(
                "Config contains a value that cannot be deterministically canonicalized -- "
                "preregistration REFUSED rather than silently converting/stringifying it. " + str(e)
            )

        # --- Tiered grading declaration (tiered_verdict.py, adopted 2026-10-02) ---
        # Validation only: it never alters a field, so it cannot change any existing config hash.
        import tiered_verdict
        try:
            tiered_verdict.validate_declaration(self.parameters, self.declared_robustness_checks)
        except tiered_verdict.InvalidTieredDeclarationError as e:
            raise InvalidExperimentConfigError("Invalid tiered_grading declaration: " + str(e))

        # --- Compute the canonical config hash (Fix 6, v4) ---
        # Must happen LAST, after every other field is in its final,
        # deep-frozen form -- config_hash is a pure function of everything else.
        hashable_fields = {
            k: v for k, v in self.__dict__.items() if k != "config_hash"
        }
        try:
            computed_hash = compute_config_hash(hashable_fields)
        except UncanonicalizableValueError as e:
            raise InvalidExperimentConfigError(
                "Config contains a value that cannot be deterministically canonicalized -- "
                "preregistration REFUSED rather than silently hashing an unreliable representation. " + str(e)
            )
        object.__setattr__(self, "config_hash", computed_hash)
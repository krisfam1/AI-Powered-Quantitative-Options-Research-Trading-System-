"""
Deterministic, canonical hashing for ExperimentConfig. Two semantically
identical configs MUST produce identical hashes. Any value that cannot
be deterministically canonicalized causes an explicit failure at
construction time -- NEVER silently stringified via a catch-all
default=str fallback.
"""

import hashlib
import json

# Explicitly supported, deterministically-canonicalizable types.
# Anything outside this set raises, rather than being silently coerced.
_SUPPORTED_SCALAR_TYPES = (str, int, float, bool, type(None))


class UncanonicalizableValueError(Exception):
    """Raised when a config value cannot be deterministically canonicalized.
    This is a hard failure -- preregistration must not proceed."""
    pass


def _canonicalize(value):
    """
    Recursively converts a value into a canonical, JSON-serializable
    form with deterministic key ordering and explicit type tagging
    (so e.g. the tuple (1,2) and the list [1,2] never collide, and a
    float and an equal-valued int never collide).
    """
    if isinstance(value, bool):
        # Must check bool BEFORE int -- bool is a subclass of int in Python,
        # and True/False must never canonicalize identically to 1/0.
        return {"__type__": "bool", "__value__": value}

    if isinstance(value, int):
        return {"__type__": "int", "__value__": value}

    if isinstance(value, float):
        # Reject NaN/Infinity explicitly -- not deterministically comparable/hashable
        # in a way that survives round-tripping reliably across environments.
        if value != value or value in (float("inf"), float("-inf")):
            raise UncanonicalizableValueError("NaN/Infinity float values cannot be canonicalized: " + repr(value))
        return {"__type__": "float", "__value__": value}

    if isinstance(value, str):
        return {"__type__": "str", "__value__": value}

    if value is None:
        return {"__type__": "none", "__value__": None}

    if isinstance(value, tuple):
        return {"__type__": "tuple", "__value__": [_canonicalize(v) for v in value]}

    if isinstance(value, list):
        # Lists should never reach here if ExperimentConfig.__post_init__
        # correctly deep-froze everything to tuples first -- but if one
        # slips through, FAIL rather than silently treat it as a tuple
        # (list vs tuple identity matters for reproducibility guarantees).
        raise UncanonicalizableValueError(
            "Raw list found where a frozen tuple was expected: " + repr(value) +
            " -- ExperimentConfig.__post_init__ must deep-freeze all lists before hashing."
        )

    if isinstance(value, dict):
        raise UncanonicalizableValueError(
            "Raw dict found where a frozen tuple-of-pairs was expected: " + repr(value) +
            " -- ExperimentConfig.__post_init__ must deep-freeze all dicts before hashing."
        )

    # Any other type (custom objects, sets, datetime objects not yet
    # converted to ISO strings, etc.) is explicitly UNSUPPORTED.
    raise UncanonicalizableValueError(
        "Unsupported type for canonical hashing: " + str(type(value)) + " (value: " + repr(value) + "). "
        "Convert to an explicit str/int/float/bool/tuple representation before constructing ExperimentConfig."
    )


def _deep_freeze(value):
    """
    Recursively converts lists -> tuples and dicts -> sorted tuple-of-pairs,
    so that no mutable structure survives into a frozen ExperimentConfig.
    Unlike _canonicalize (used only for hashing), this is used to actually
    TRANSFORM the stored config fields at construction time.
    """
    if isinstance(value, dict):
        return tuple(sorted((k, _deep_freeze(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_deep_freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_deep_freeze(v) for v in value)
    if isinstance(value, _SUPPORTED_SCALAR_TYPES):
        return value
    raise UncanonicalizableValueError(
        "Unsupported type during deep-freeze: " + str(type(value)) + " (value: " + repr(value) + "). "
        "All ExperimentConfig field values must be str/int/float/bool, or nested list/tuple/dict of those."
    )


def compute_config_hash(config_fields: dict) -> str:
    """
    config_fields: a dict of {field_name: field_value} for every field
    EXCEPT config_hash itself (which doesn't exist yet during its own
    computation). All values must already be deep-frozen (tuples, not
    lists/dicts) by the time this is called.

    Returns: a SHA-256 hex digest, deterministic across runs/environments
    for identical input.
    """
    canonical_dict = {k: _canonicalize(v) for k, v in sorted(config_fields.items())}
    canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
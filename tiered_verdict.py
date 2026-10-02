"""
tiered_verdict.py -- the tiered grading scheme "tiered_v1" (adopted 2026-10-02; CLAUDE.md Section 1).

Replaces the flat-OR rule (any failed robustness check -> REJECTED) for experiments that DECLARE it
before their hash locks. Experiments registered without the declaration keep their legacy rules
(verdict.py), unchanged: this module never re-grades an existing experiment.

FOUR TIERS
  REJECTED                          clean, decisive negative; the only "closed forever" outcome
  HELD                              could not cleanly resolve; resumable (the recyclable signal library)
  VALIDATED_SMALL_SIZE_MONITOR      primary bar + hard gates pass; some soft-check inconsistency
  VALIDATED_FULL_CONFIDENCE         primary bar + hard gates + every soft check pass
plus INCOMPLETE, which is not a verdict: a declared result is missing.

THE DECLARATION (one ExperimentConfig.parameters key, "tiered_grading", hashed with the plan):
  scheme                              "tiered_v1"
  hypothesized_sign                   "+" or "-"
  alpha_one_sided                     0 < alpha <= 0.05 (never looser than the project's existing bar)
  effect_size_floor                   > 0, in the primary statistic's units, hypothesized-direction terms
  power_at_floor                      design power at the floor effect (from POWER_ANALYSIS)
  min_abs_t_stat                      0 = not used; e.g. 3.0 for the Harvey-Liu-Zhu bar
  hard_gates                          1-3 declared robustness checks; failing ANY -> REJECTED
  soft_checks                         every other declared robustness check
  max_soft_failures_for_small_size    soft failures tolerated at VALIDATED_SMALL_SIZE_MONITOR
hard_gates + soft_checks must partition declared_robustness_checks exactly.

GRADING ORDER (grade())
  1. any declared result missing                          -> INCOMPLETE
  2. any hard gate failed                                 -> REJECTED (no exceptions)
  3. primary effect in the wrong direction (signed effect <= 0):
       design adequately powered (power_at_floor >= 0.80), or the opposite direction is itself
       significant at alpha                               -> REJECTED (decisive wrong direction)
       otherwise                                          -> HELD (underpowered; sign not informative)
  4. primary bar not met (not significant, below the floor, or |t| < min_abs_t_stat):
       adequately powered AND the confidence bound excludes the floor (an effect >= floor is ruled
       out)                                               -> REJECTED (decisive null)
       otherwise                                          -> HELD
  5. primary bar met: soft failures k
       k == 0                                             -> VALIDATED_FULL_CONFIDENCE
       1 <= k <= max_soft_failures_for_small_size         -> VALIDATED_SMALL_SIZE_MONITOR
       k  > max_soft_failures_for_small_size              -> HELD (inconsistent; no confound shown)

Step 4's "decisive null" is the framework's reading of "clean, decisive negative" for a right-
signed result: when the design had >= 80% power and the data exclude an effect at the floor,
calling it HELD would make HELD a place where adequately tested ideas never die.

DEPLOYMENT MEANING (informational; this module has no execution or capital capability, and nothing
here makes the project ready for live capital -- that readiness is assessed separately):
  VALIDATED_FULL_CONFIDENCE    -> eligible for the graduated ladder, starting small with tight
                                  limits; scale only if live results match research predictions
  VALIDATED_SMALL_SIZE_MONITOR -> eligible for the smallest rung only, with closer monitoring;
                                  the soft-check failures define what to monitor
  HELD                         -> signal library; resuming needs a new versioned pre-registration
  REJECTED                     -> closed; not resumed in this form
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

SCHEME = "tiered_v1"
REJECTED = "REJECTED"
HELD = "HELD"
VALIDATED_SMALL = "VALIDATED_SMALL_SIZE_MONITOR"
VALIDATED_FULL = "VALIDATED_FULL_CONFIDENCE"
INCOMPLETE = "INCOMPLETE"
TIERS = (REJECTED, HELD, VALIDATED_SMALL, VALIDATED_FULL)

ADEQUATE_POWER = 0.80        # framework constant, deliberately NOT declarable per experiment
MAX_ALPHA = 0.05
MIN_HARD_GATES, MAX_HARD_GATES = 1, 3

DEPLOYMENT_MEANING = {
    VALIDATED_FULL: ("Eligible for graduated deployment: start at small, tightly limited capital; compare live "
                     "results with the research prediction; scale only if they match. Live-capital readiness "
                     "of the project itself is a separate assessment."),
    VALIDATED_SMALL: ("Eligible for the smallest deployment rung only, with closer monitoring of the failed soft "
                      "checks; no scale-up until live results match the research prediction."),
    HELD: "Signal library: not closed. Resuming needs a new, versioned pre-registration (and a hypothesis slot).",
    REJECTED: "Closed: a clean, decisive negative. Not resumed in this form.",
}


class InvalidTieredDeclarationError(Exception):
    pass


@dataclass(frozen=True)
class TieredDeclaration:
    hypothesized_sign: int
    alpha_one_sided: float
    effect_size_floor: float
    power_at_floor: float
    min_abs_t_stat: float
    hard_gates: Tuple[str, ...]
    soft_checks: Tuple[str, ...]
    max_soft_failures_for_small_size: int


@dataclass(frozen=True)
class PrimaryResult:
    """All effect quantities in the primary statistic's units, signed so that POSITIVE means the
    hypothesized direction (the executor applies the sign; grade() re-checks consistency)."""
    estimate: float                 # raw estimate (e.g. correlation), as computed
    p_one_sided: float              # p-value in the hypothesized direction
    p_opposite_one_sided: float     # p-value in the opposite direction
    confidence_bound: float         # one-sided (1 - alpha) bound on the effect, in hypothesized-direction
                                    # terms: the LARGEST effect in the hypothesized direction consistent
                                    # with the data (for sign "+", the upper bound)
    n: int
    t_stat: Optional[float] = None  # hypothesized-direction t; required when min_abs_t_stat > 0


@dataclass(frozen=True)
class TieredVerdict:
    status: str
    reasoning: str
    deployment_meaning: Optional[str]
    hard_gate_results: Dict[str, bool] = field(default_factory=dict)
    soft_check_results: Dict[str, bool] = field(default_factory=dict)
    soft_failures: Tuple[str, ...] = ()


def _get(params, key):
    """Look up a key in a deep-frozen parameters tuple-of-pairs (or a plain dict)."""
    if isinstance(params, dict):
        return params.get(key)
    for pair in params or ():
        if isinstance(pair, (tuple, list)) and len(pair) == 2 and pair[0] == key:
            return pair[1]
    return None


def declaration_from_parameters(parameters) -> Optional[dict]:
    raw = _get(parameters, "tiered_grading")
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    return {k: v for k, v in raw}


def validate_declaration(parameters, declared_robustness_checks) -> Optional[TieredDeclaration]:
    """Returns None if the config does not use tiered grading; raises if it declares it badly."""
    d = declaration_from_parameters(parameters)
    if d is None:
        return None
    E = InvalidTieredDeclarationError
    required = {"scheme", "hypothesized_sign", "alpha_one_sided", "effect_size_floor", "power_at_floor",
                "min_abs_t_stat", "hard_gates", "soft_checks", "max_soft_failures_for_small_size"}
    missing, extra = required - set(d), set(d) - required
    if missing or extra:
        raise E(f"tiered_grading keys: missing {sorted(missing)}, unexpected {sorted(extra)}")
    if d["scheme"] != SCHEME:
        raise E(f"tiered_grading.scheme must be {SCHEME!r}, got {d['scheme']!r}")
    if d["hypothesized_sign"] not in ("+", "-"):
        raise E("hypothesized_sign must be '+' or '-'")
    a = d["alpha_one_sided"]
    if not isinstance(a, (int, float)) or not (0 < a <= MAX_ALPHA):
        raise E(f"alpha_one_sided must be in (0, {MAX_ALPHA}] -- tiered grading never loosens the significance bar")
    if not isinstance(d["effect_size_floor"], (int, float)) or d["effect_size_floor"] <= 0:
        raise E("effect_size_floor must be > 0")
    if not isinstance(d["power_at_floor"], (int, float)) or not (0 <= d["power_at_floor"] <= 1):
        raise E("power_at_floor must be in [0, 1]")
    if not isinstance(d["min_abs_t_stat"], (int, float)) or d["min_abs_t_stat"] < 0:
        raise E("min_abs_t_stat must be >= 0 (0 = not used)")
    hard, soft = tuple(d["hard_gates"]), tuple(d["soft_checks"])
    if not (MIN_HARD_GATES <= len(hard) <= MAX_HARD_GATES):
        raise E(f"hard_gates must list {MIN_HARD_GATES}-{MAX_HARD_GATES} checks (deliberately minimal); got {len(hard)}")
    if len(set(hard)) != len(hard) or len(set(soft)) != len(soft):
        raise E("hard_gates / soft_checks contain duplicates")
    if set(hard) & set(soft):
        raise E(f"checks declared both hard and soft: {sorted(set(hard) & set(soft))}")
    declared = set(declared_robustness_checks)
    if set(hard) | set(soft) != declared or len(declared) != len(tuple(declared_robustness_checks)):
        raise E("hard_gates + soft_checks must partition declared_robustness_checks exactly; "
                f"unclassified {sorted(declared - set(hard) - set(soft))}, "
                f"not declared {sorted((set(hard) | set(soft)) - declared)}")
    k = d["max_soft_failures_for_small_size"]
    if not isinstance(k, int) or isinstance(k, bool) or k < 0 or (soft and k >= len(soft)) or (not soft and k != 0):
        raise E("max_soft_failures_for_small_size must be an int in [0, len(soft_checks) - 1] (0 if there are none)")
    return TieredDeclaration(1 if d["hypothesized_sign"] == "+" else -1, float(a), float(d["effect_size_floor"]),
                             float(d["power_at_floor"]), float(d["min_abs_t_stat"]), hard, soft, k)


def grade(decl: TieredDeclaration, primary: Optional[PrimaryResult],
          check_results: Dict[str, Optional[bool]]) -> TieredVerdict:
    """PURE. check_results maps each declared check name to survived True/False (None/absent = not run)."""
    hard_r = {g: check_results.get(g) for g in decl.hard_gates}
    soft_r = {c: check_results.get(c) for c in decl.soft_checks}
    missing = [n for n, v in {**hard_r, **soft_r}.items() if v is None]
    if primary is None or missing:
        return TieredVerdict(INCOMPLETE, "not graded: missing " + ("primary result" if primary is None else "")
                             + (" and " if primary is None and missing else "") + (f"checks {missing}" if missing else ""),
                             None, hard_r, soft_r)
    if decl.min_abs_t_stat > 0 and primary.t_stat is None:
        return TieredVerdict(INCOMPLETE, "not graded: min_abs_t_stat declared but no t_stat reported", None, hard_r, soft_r)
    soft_fail = tuple(c for c, v in soft_r.items() if v is False)

    def out(status, why):
        return TieredVerdict(status, why, DEPLOYMENT_MEANING[status], hard_r, soft_r, soft_fail)

    failed_hard = [g for g, v in hard_r.items() if v is False]
    if failed_hard:
        return out(REJECTED, f"hard gate(s) failed: {failed_hard} -- automatic REJECTED")

    eff = primary.estimate * decl.hypothesized_sign       # positive = hypothesized direction
    powered = decl.power_at_floor >= ADEQUATE_POWER
    if eff <= 0:
        if powered:
            return out(REJECTED, f"primary effect {primary.estimate:+.4g} is in the wrong direction and the design was "
                                 f"adequately powered (power at floor {decl.power_at_floor:.2f} >= {ADEQUATE_POWER})")
        if primary.p_opposite_one_sided < decl.alpha_one_sided:
            return out(REJECTED, f"primary effect {primary.estimate:+.4g} is significantly in the wrong direction "
                                 f"(p_opposite {primary.p_opposite_one_sided:.4g} < {decl.alpha_one_sided})")
        return out(HELD, f"primary effect {primary.estimate:+.4g} is in the wrong direction but the design was "
                         f"underpowered (power at floor {decl.power_at_floor:.2f}) and the reversal is not significant")

    significant = primary.p_one_sided < decl.alpha_one_sided
    t_ok = decl.min_abs_t_stat == 0 or (primary.t_stat is not None and primary.t_stat >= decl.min_abs_t_stat)
    floor_ok = eff >= decl.effect_size_floor
    if not (significant and t_ok and floor_ok):
        why = []
        if not significant:
            why.append(f"p {primary.p_one_sided:.4g} >= alpha {decl.alpha_one_sided}")
        if not t_ok:
            why.append(f"t {primary.t_stat} < required {decl.min_abs_t_stat}")
        if not floor_ok:
            why.append(f"effect {eff:.4g} < floor {decl.effect_size_floor}")
        if powered and primary.confidence_bound < decl.effect_size_floor:
            return out(REJECTED, "primary bar not met (" + "; ".join(why) + f"); adequately powered design and the "
                                 f"confidence bound {primary.confidence_bound:.4g} excludes the floor -- decisive null")
        return out(HELD, "primary bar not met (" + "; ".join(why) + "); not a decisive negative ("
                         + ("underpowered" if not powered else
                            f"confidence bound {primary.confidence_bound:.4g} does not exclude the floor") + ")")

    k = len(soft_fail)
    if k == 0:
        return out(VALIDATED_FULL, "primary bar, all hard gates and all soft checks passed")
    if k <= decl.max_soft_failures_for_small_size:
        return out(VALIDATED_SMALL, f"primary bar and hard gates passed; {k} soft check(s) failed {list(soft_fail)} "
                                    f"(<= {decl.max_soft_failures_for_small_size} tolerated)")
    return out(HELD, f"primary bar and hard gates passed, but {k} soft checks failed {list(soft_fail)} "
                     f"(> {decl.max_soft_failures_for_small_size} tolerated); inconsistent, no confound demonstrated")

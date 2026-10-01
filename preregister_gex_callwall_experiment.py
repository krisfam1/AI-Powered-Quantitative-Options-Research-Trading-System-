from dotenv import load_dotenv
load_dotenv()

"""
DRAFT pre-registration for the call-wall-distance GEX hypothesis --
the next formal experiment, chosen 2026-09-21 to replace V1 (now
formally CLOSED: no demonstrated edge, see CLAUDE.md Section 18).

Modeled directly on preregister_experiment1.py's structure and
ExperimentConfig's actual validated fields -- not a paraphrase.

THIS FILE CONSTRUCTS AND PRINTS THE CONFIG FOR REVIEW ONLY.
IT DOES NOT CALL preregister_experiment() ANYWHERE. Per explicit
instruction, the actual test must not run yet -- this script cannot
register or execute anything even if run end to end. A real
preregistration call is a deliberate, separate future step, only
after this draft is reviewed and approved.

WHY THIS ORDER MATTERS: Phase 6/7's DB rows are explicitly self-labeled
"RETROACTIVE BACKFILL... does NOT constitute genuine preregistration"
(CLAUDE.md Section 5/12) -- real, honest research, but methodologically
weaker than a locked-before-results design. This experiment is meant to
avoid that gap: the config below, once actually preregistered, gets a
canonical config_hash computed from its EXACT frozen fields (via
canonical_hash.py) BEFORE the correlation between call-wall-distance and
forward returns is ever computed or looked at.
"""

from experiment_config import ExperimentConfig

# ---------------------------------------------------------------------------
# SIGNAL DEFINITION -- verified 2026-09-21 by reading gex_lookup.py in full,
# not from memory or a docstring summary.
#
#   call_wall_distance_pct = (call_wall_strike - spot_price) / spot_price * 100
#
# Computed by gex_lookup.py:get_gex_for_signal(ticker, signal_timestamp) from
# the T-1 (real previous US trading day) validated GEX snapshot in
# gex_data_cache.db:gex_metrics, sign_convention="model_a" (the module's own
# PRIMARY_SIGN_CONVENTION default -- "flipped" also exists in the DB but is
# not this module's default output).
#
# NO-LOOKAHEAD GUARANTEE: gex_lookup.py enforces this with an EXECUTABLE
# assertion (not just a docstring promise) -- `assert snapshot_date_obj <
# signal_date` and `== t_minus_1` -- confirmed by direct read this session.
#
# DATA CURRENTLY AVAILABLE (RE-CHECKED 2026-09-22, both databases queried
# directly -- UPDATED from the original 2026-09-21 draft, see note below):
#   Historical (gex_data_cache.db:gex_metrics): 850 rows (was 748), 6
#     tickers, 2026-06-10 to 2026-09-21 (was 2026-09-08), both sign
#     conventions computed. This is GEX-snapshot coverage -- NOT yet joined
#     against V1-qualifying signal occurrences; the actual joined N is
#     computed at Stage 1 execution time, not assumed here.
#   Prospective (prospective_gex_validation.db:raw_signals): unchanged from
#     the original draft assessment, Stage 2 remains untouched/separate.
#
# STAGE 1 DATASET-DEFINITION UPDATE, 2026-09-22 (see CLAUDE.md Section 32
# for the full reasoning, recorded BEFORE this update was applied to this
# file): gex_metrics grew from 748 to 850 rows via the approved incremental
# backfill (CLAUDE.md Section 40), and now keeps growing daily. date_range,
# train_period, and current_historical_gex_snapshot_rows below are updated
# to match the table's actual current extent at the time Stage 1 is run --
# CLAUDE.md's reasoning: no result was ever computed against the original
# 748-row set, and the added dates were already-elapsed, immutable calendar
# history before this config was drafted, so no lookahead is introduced by
# widening the window before running. This IS a substantive change to the
# locked config (a new config_hash, printed below, supersedes the original
# 9820ed6e18c11f7fa069a931490823398081e469ee5c01c95cec7009b3745fde) --
# flagged explicitly, not silently changed.
# ---------------------------------------------------------------------------

NOTES = (
    "PRE-REGISTRATION DRAFT, not yet submitted. Two-stage design chosen "
    "specifically to avoid Phase 6/7's backfilled-after-the-fact methodology "
    "gap (their own DB rows self-label as non-preregistered). "
    "STAGE 1 (historical, available now): call-wall-distance vs. forward "
    "return among V1-qualifying signals in the existing 2026-06-10 to "
    "2026-09-08 GEX-covered window. Locked BEFORE this correlation is "
    "computed or inspected -- config_hash below is the proof of that. "
    "STAGE 2 (prospective, true out-of-sample): replication on GEX signals "
    "logged by prospective_gex_pipeline.py AFTER this config's preregistration "
    "timestamp only -- genuinely never-seen data, not just held out during "
    "analysis. Current prospective n=11 is far below the minimum sample size "
    "declared in parameters (min_n_per_stage=100) -- Stage 2 is NOT YET "
    "RUNNABLE and must wait for further forward accumulation. See the "
    "honest assessment in this script's printed report."
)

config = ExperimentConfig(
    experiment_id="gex_callwall_distance_v1_20260921",
    experiment_type="signal_research",
    hypothesis=(
        "Among V1-qualifying call signals, T-1 call-wall-distance (call_wall_distance_pct, "
        "the signed percentage distance from spot to the nearest identified call-gamma-wall "
        "strike, via gex_lookup.py's Method B true-zero-gamma methodology) is negatively "
        "associated with forward returns at short-to-medium horizons -- i.e., signals firing "
        "closer to a call wall above spot show systematically SUPPRESSED forward returns "
        "relative to signals with more distance to the nearest wall, consistent with the "
        "standard GEX-literature theory that dealer hedging flows create local resistance "
        "near large positive-gamma strikes."
    ),
    research_question=(
        "Does call-wall-distance at T-1 carry incremental predictive information about "
        "forward returns for V1-qualifying signals, beyond what Phase 6 already established "
        "the raw entry signal alone does NOT have (T_obs=-0.2569%, p=0.996)?"
    ),
    dataset_version="gex_metrics_v1_20260610_20260921_plus_prospective_forward_only",
    date_range=("2026-06-10", "2026-09-21"),  # Stage 1 (historical, UPDATED 2026-09-22 to match the table's current extent -- see dataset-definition note above); Stage 2 uses signals logged strictly after this config's preregistration timestamp, open-ended going forward
    universe=["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"],
    option_type="call",  # matches V1's frozen calls-only convention; this experiment does not touch V1's direction logic
    features_used=[
        ("call_wall_distance_pct", "1.0"),
    ],
    parameters={
        "gex_source": "gex_lookup.py:get_gex_for_signal, sign_convention=model_a",
        "signal_qualification": "V1's frozen gate -- bullish SPY regime + 20-bar breakout + entry_score>=20 (entry_scorer.py), matching portfolio_backtest.py's pricing_mode=v1 exactly, per CLAUDE.md Section 15",
        "target_horizons_bars": [5, 10, 20, 50],  # matches prospective_gex_pipeline.py's own HORIZONS_BARS, for direct comparability between stages
        "primary_horizon_bars": 20,  # matches Phase 6's primary horizon, for comparability against the already-established no-standalone-edge finding
        "secondary_horizons_bars": [5, 10, 50],
        "primary_test": "monte_carlo_day_clustered_one_sided",  # matches Phase 6's already-validated methodology, not re-derived
        "monte_carlo_replicates": 1000,
        "random_seeds_note": "2 seeds required for reproducibility check, matching Phase 6 precedent -- see random_seeds field",
        "bucket_split": "median_split -- near-wall (below-median |call_wall_distance_pct|) vs far-wall (above-median), computed AFTER pooling all qualifying signals, direction of test is near-wall-suppressed per hypothesis",
        "min_n_per_stage": 100,  # BELOW THIS: experiment_status = NOT TESTABLE for that stage, do not interpret any result computed anyway
        "min_n_prospective_for_stage2": 100,
        "current_historical_gex_snapshot_rows": 850,  # UPDATED 2026-09-22 (was 748) -- raw count, NOT yet joined against qualifying signals -- joined N unknown until run
        "current_prospective_rows": 11,  # as of 2026-09-21, pre-timezone-fix-recovery; Stage 2 untouched by this update
        "bonferroni_family_size": 4,  # 4 horizons tested (5/10/20/50-bar) -- alpha corrected across all four, not just the primary
        "alpha_uncorrected": 0.05,
        "effect_size_threshold_relative_return_gap_pct": 0.5,  # minimum |near-wall - far-wall| mean forward-return gap, in percentage points, to count as economically meaningful even if statistically significant
    },
    model_version=None,
    pricing_methodology="n/a_underlying_return_prediction_only",  # Stage 1/2 as specified test UNDERLYING forward returns, not option P&L -- deliberately isolates the GEX signal's own predictive content from V1's separate, already-closed pricing/execution questions (Section 13)
    execution_assumptions="none -- this experiment does not touch option pricing, spread, or execution; a separate follow-on experiment would be needed to translate any validated underlying-return edge into an actual option P&L claim",
    train_period=("2026-06-10", "2026-09-21"),  # Stage 1 IS the full historical window -- no further split within it, since Stage 2 (prospective) is the true holdout, not a carve-out of Stage 1
    validation_period=None,
    test_period=None,  # deliberately None at preregistration time -- Stage 2's test period is open-ended ("whatever accumulates after this config's timestamp"), cannot be dated in advance; oos_validation_claimed is therefore False until Stage 2 actually runs
    random_seeds=[42, 43],  # matches Phase 6's exact seed pair, for direct reproducibility-methodology comparability
    code_version="gex_callwall_v1_draft",
    testing_family_declaration="INDEPENDENT_SINGLE",
    applicability_lock=[
        ("data_integrity", True), ("lookahead_audit", True), ("timestamp_safety", True),
        ("sample_size_adequacy", False),  # UNKNOWN until the actual join is run -- see min_n_per_stage
        ("statistical_testing", False), ("reproduction", False),
        ("primary_test_significant", False), ("effect_size_meets_threshold", False),
        ("multiple_testing_survived", False), ("robustness_survived", False),
        ("oos_survived", False),
        ("primary_performance_test_significant", False), ("concentration_check", False),
        ("pricing_accuracy_meets_threshold", False), ("pricing_coverage_meets_threshold", False),
    ],
    oos_validation_claimed=False,  # Stage 2 (the genuine OOS test) has not run -- current prospective n=11 is far below min_n_prospective_for_stage2=100
    declared_robustness_checks=[
        "leave_one_ticker_out", "alternate_horizon:5bar", "alternate_horizon:10bar", "alternate_horizon:50bar",
        "sign_convention:flipped",  # both sign conventions are computed and stored (374 rows each) -- check the finding isn't an artifact of the model_a convention specifically
    ],
)

# ---------------------------------------------------------------------------
# PRE-SPECIFIED SUCCESS / FAILURE / INCONCLUSIVE CRITERIA -- fixed here,
# before any result exists. Do not edit these thresholds after seeing data.
# ---------------------------------------------------------------------------
DECISION_RULES = """
VALIDATED requires ALL of:
  1. Stage 1 joined N >= 100 (min_n_per_stage)
  2. Primary test (20-bar horizon) significant at Bonferroni-corrected
     alpha = 0.05 / 4 = 0.0125 (bonferroni_family_size=4), one-sided in the
     hypothesized direction (near-wall suppressed)
  3. Effect size >= 0.5 percentage points mean return gap (economically
     meaningful, not just statistically detectable)
  4. Survives ALL declared robustness checks (leave-one-ticker-out, the three
     secondary horizons, both sign conventions) in the same direction
  5. Stage 2 (prospective, n >= 100, collected strictly after this config's
     preregistration timestamp) replicates the same direction, even if not
     at the same significance level (true OOS confirmation, not just
     historical significance)

REJECTED if:
  - Stage 1 N >= 100 but the primary test is not significant at the
    corrected alpha, OR effect size is below threshold, OR the direction
    reverses under any declared robustness check

INCONCLUSIVE if:
  - Stage 1 N < 100 (do not interpret whatever number comes out anyway)
  - Stage 1 passes but Stage 2 cannot yet be run (current state, 2026-09-21:
    prospective n=11 << 100) -- experiment stays OPEN, not closed, pending
    further forward data accumulation
  - Stage 1 and Stage 2 (once both exist) disagree in direction without a
    clear, pre-specified tiebreaker (none is specified here -- a genuine
    conflict would require a NEW, separately pre-registered follow-up, not
    an ad hoc resolution)
"""

print("=" * 100)
print("DRAFT CONFIG -- FOR REVIEW, NOT YET PREREGISTERED")
print("=" * 100)
print("experiment_id: " + config.experiment_id)
print("experiment_type: " + config.experiment_type)
print("hypothesis: " + config.hypothesis)
print("research_question: " + config.research_question)
print("universe: " + str(config.universe))
print("date_range (Stage 1 historical): " + str(config.date_range))
print("features_used: " + str(config.features_used))
print("testing_family_declaration: " + config.testing_family_declaration)
print("oos_validation_claimed: " + str(config.oos_validation_claimed))
print("applicability_lock: " + str(config.applicability_lock))
print("declared_robustness_checks: " + str(config.declared_robustness_checks))
print("\nCONFIG HASH (computed by the real, unmodified canonical_hash.py -- proves this exact")
print("config, not a paraphrase, is what would be locked): " + config.config_hash)
print("\n" + "=" * 100)
print("DECISION RULES (pre-specified, fixed before any result exists)")
print("=" * 100)
print(DECISION_RULES)
print("=" * 100)
print("NOT PREREGISTERED. This script never calls preregister_experiment() or")
print("run_experiment() -- registering this config into the real framework is a")
print("separate, deliberate future step, only after this draft is reviewed.")
print("=" * 100)

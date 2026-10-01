from dotenv import load_dotenv
load_dotenv()

"""
DRAFT pre-registration for a Random-Forest-vs-Ridge forward-realized-
volatility hypothesis -- scoped 2026-09-25, directly prompted by a
robustness-check finding in the now-closed xgboost_volatility_prediction_
v1_20260925 experiment (CLAUDE.md Section 45, REJECTED).

THIS FILE CONSTRUCTS AND PRINTS THE CONFIG FOR REVIEW ONLY. IT DOES NOT
CALL preregister_experiment() OR run_experiment() ANYWHERE.

===========================================================================
WHY THIS EXPERIMENT, AND THE HONEST DISCLOSURE ABOUT NOT BEING FULLY BLIND:
===========================================================================

The closed XGBoost-volatility experiment (Model A=Ridge, Model B=XGBoost,
8 features, same target) was REJECTED on its own literal decision rules --
but its `alternate_model:random_forest` robustness check showed Random
Forest, NOT XGBoost, clearing every bar that XGBoost missed: R2=+0.0708
(genuinely positive, beats "predict the mean"), delta vs. Ridge=+0.398,
p=2.0e-7. Its `leave_one_ticker_out` check showed XGBoost's aggregate
result was dragged deeply negative specifically by AMD and MSTR (deltas
-0.55 to -1.42), while excluding AMD or SMCI instead flipped XGBoost's own
result strongly positive (+0.48, +0.38) -- a real per-ticker heterogeneity
problem, not noise (shuffled-target placebo came back clean, p=0.983, so
the pattern isn't a pipeline artifact).

MECHANISM, STATED EXPLICITLY: boosting (XGBoost) builds trees sequentially,
each one correcting the residual of the last -- a single ticker/period with
unusually large or idiosyncratic realized-vol swings can dominate later
boosting rounds and distort the whole ensemble's fit. Bagging (Random
Forest) instead averages many independently-grown trees trained on
bootstrap resamples -- a mechanism specifically designed to be more robust
to exactly this kind of per-subgroup instability, since no single
influential subsample can dominate every tree the way a hard residual can
dominate every boosting round. This is a genuine, falsifiable, mechanistic
reason to expect Random Forest might behave differently on this same
noisy, ticker-heterogeneous dataset -- not a coin flip dressed up as a
hypothesis.

HONEST METHODOLOGICAL CAVEAT, stated up front rather than glossed over:
this hypothesis is NOT fully blind -- it is directly informed by a
robustness-check finding from a closed, related (but model-class-distinct)
experiment on the SAME dataset. That is a real, disclosed limitation on
how much independent confirming weight a positive result here should
carry; it does NOT, however, make the result predetermined or untestable
-- Random Forest could just as easily show the SAME AMD/SMCI-driven
instability XGBoost did (bagging reduces but does not eliminate the
influence of a systematically different subgroup), and this design commits
in advance to reporting that outcome plainly if it occurs. Because this
directional expectation already exists, `leave_one_ticker_out` is declared
MANDATORY here (not merely one of several robustness checks picked
after the fact) -- explicitly so a repeat of the AMD/SMCI pattern cannot
be treated as a surprise finding requiring a NEW check to be invented
after seeing it, the way the original hypothesis was discovered.

===========================================================================
DATA: NO NEW COLLECTION. Reuses xgboost_volatility_dataset.db's already-
generated, already-verified 4,027-row dataset (Section 45) EXACTLY as-is
-- same 8 features, same 3 target horizons, same 6-ticker universe, same
2023-10-02-to-2026-07-15 usable window. Verified before writing this
config, not assumed: the dataset's own last observation is 2026-07-15
(confirmed directly from the closed XGBoost-volatility Stage 1 run's
split log), which is the maximum date the 50-day-forward target's own
computability allows given today's (2026-09-25) last available daily
bar -- there is NO already-collected slice of MORE RECENT dates sitting
unused in this dataset that could serve as a "free" Stage 2. A genuine
Stage 2 therefore cannot be carved out of what already exists; it has to
be a real, currently-EMPTY rolling window (see Stage 2 design below).
===========================================================================

STAGE 2 DESIGN, included per explicit instruction since it is genuinely
feasible without any NEW data-generation script (the existing
generate_xgboost_volatility_dataset.py already computes its own END_DATE
as "today" dynamically -- rerunning it unmodified in the future will
naturally extend the dataset forward with zero code changes needed).
Fixed start = 2026-07-16 (the day immediately after Stage 1's own last
observation -- no gap, no overlap). Open end, determined at whatever
future moment Stage 2 is actually run via a data-EXISTENCE check only
(how many NEW (ticker, day) rows exist past 2026-07-16 once the dataset
is regenerated -- never by inspecting any Ridge-vs-RF result, so the stop
decision cannot be influenced by a favorable-looking peek). Continue until
N>=100, then lock and run the primary test once against that realized set
-- same discipline as iv_term_structure_slope_v1_20260921's Stage 2
(CLAUDE.md Section 33) and every other rolling-Stage-2 experiment in this
project.

TIMING ESTIMATE, disclosed as an estimate not a promise: the 50-day-
forward-target constraint means the FIRST new Stage-2 candidate row
(2026-07-16) only becomes computable once ~50 MORE trading days exist
past it -- arithmetically, that boundary lands close to TODAY (2026-09-25)
already, not months out. Reaching the full N>=100 (approx. 17 more real
trading days x 6 tickers, since each new trading day unlocks about 6 new
candidate rows) is plausibly a MATTER OF WEEKS, not the months GEX's own
Stage 2 needed (GEX depends on a rare qualifying signal; this only needs
elapsed calendar time, the same favorable timing profile IV term
structure's own Stage 2 has).
"""

from experiment_config import ExperimentConfig

NOTES = (
    "PRE-REGISTRATION DRAFT, not yet submitted. Directly motivated by a "
    "robustness-check finding in the closed, REJECTED "
    "xgboost_volatility_prediction_v1_20260925 (Section 45) -- NOT a retune "
    "of that experiment (different model class swapped in as Model B, same "
    "data/features/target reused unmodified, own hash). "
    "MECHANISM: bagging (Random Forest) averages independently-bootstrapped "
    "trees, a mechanism specifically more robust to a subgroup (AMD/SMCI) "
    "dominating the fit than boosting (XGBoost)'s sequential residual-"
    "correction is -- stated explicitly as the falsifiable reason to expect "
    "a different result, not assumed. "
    "HONEST CAVEAT: this hypothesis is NOT fully blind -- informed by a "
    "prior, model-class-distinct experiment's robustness-check finding on "
    "the same data. leave_one_ticker_out is therefore declared MANDATORY "
    "up front specifically so an AMD/SMCI repeat cannot be treated as a "
    "surprise requiring a new check invented after the fact. "
    "DATA: zero new collection -- reuses xgboost_volatility_dataset.db's "
    "verified 4,027-row Stage 1 dataset exactly as-is (same 8 features, "
    "same 3 horizons, same 6-ticker universe, same window). "
    "STAGE 2: a genuinely empty, real rolling window (fixed start "
    "2026-07-16, open end via data-existence check only, N>=100 lock-and-"
    "test-once) -- verified before writing this config that no already-"
    "collected slice of unused-more-recent dates exists to shortcut this "
    "(the dataset's own last observation, 2026-07-15, is already the max "
    "the 50-day-forward target's computability allows against today's last "
    "daily bar). Populated later by rerunning the SAME, unmodified "
    "generate_xgboost_volatility_dataset.py -- no new script needed. "
    "Timing estimate (disclosed as an estimate): plausibly weeks, not "
    "months, since the 50-day-forward constraint means the boundary is "
    "already close to today and only elapsed trading days (not a rare "
    "signal) are needed. "
    "Model A/B/primary-test/effect-size/Bonferroni/min-N/seeds ALL REUSED "
    "VERBATIM from xgboost_volatility_prediction_v1_20260925 for direct "
    "comparability, except Model B (XGBoost->Random Forest) and the "
    "robustness-check model swap (random_forest->xgboost, closing the loop "
    "from the closed experiment)."
)

config = ExperimentConfig(
    experiment_id="randomforest_volatility_prediction_v1_20260925",
    experiment_type="signal_research",
    hypothesis=(
        "Random Forest -- a bagging, interaction-aware, nonlinear model -- predicts forward "
        "realized volatility with lower error than a Ridge linear regression using the "
        "IDENTICAL 8-feature set (IV term-structure slope, OI skew, trailing realized "
        "volatility, real-IV Greeks). This is directly motivated by xgboost_volatility_"
        "prediction_v1_20260925's own robustness-check finding (Section 45, REJECTED) that "
        "Random Forest -- not XGBoost -- cleared every VALIDATED bar on the same data, and "
        "that XGBoost's own failure was concentrated in two specific tickers (AMD, SMCI), "
        "consistent with a bagging-vs-boosting robustness-to-subgroup-heterogeneity "
        "mechanism, stated explicitly, not assumed. Same isolation discipline as the closed "
        "experiment: both models see the SAME standardized inputs, isolating model class "
        "(bagging vs. linear) as the one tested variable, not feature richness."
    ),
    research_question=(
        "Does Random Forest meaningfully outperform Ridge regression, IDENTICAL feature "
        "set, at predicting forward realized volatility for this project's 6-ticker "
        "universe -- and does that advantage (if any) survive a shuffled-target leakage "
        "check, generalize across all 6 tickers WITHOUT the AMD/SMCI-driven instability "
        "the closed XGBoost experiment showed, hold under XGBoost as an alternate model, "
        "and replicate on a genuinely separate, later, out-of-sample rolling window?"
    ),
    dataset_version="xgboost_volatility_v1_20231002_present_6ticker_new_generation_pass",  # IDENTICAL dataset_version to the closed experiment -- literally the same generated data, zero new collection
    date_range=("2023-10-02", "2026-07-15"),  # Stage 1 -- the closed experiment's own verified dataset extent, not re-derived; Stage 2 is separately defined in parameters.stage2_window_definition below, starting the day after this ends
    universe=["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"],
    option_type="call",
    features_used=[
        ("term_structure_slope_pct", "1.0"), ("oi_skew", "1.0"), ("trailing_realized_vol_20d", "1.0"),
        ("delta", "1.0"), ("gamma", "1.0"), ("theta", "1.0"), ("charm", "1.0"), ("vega_per_1pct_iv", "1.0"),
    ],  # IDENTICAL to xgboost_volatility_prediction_v1_20260925 -- reused verbatim, not redefined
    parameters={
        "target_metric": "realized_volatility_forward_20d",
        "target_definition": "IDENTICAL to xgboost_volatility_prediction_v1_20260925 -- standard annualized stdev of daily log returns over the forward window",
        "target_horizons_bars": [10, 20, 50],
        "primary_horizon_bars": 20,
        "secondary_horizons_bars": [10, 50],
        "data_reuse": "ZERO new data collection -- reuses xgboost_volatility_dataset.db's existing 4,027-row volatility_training_examples table (Stage 1) exactly as generated for xgboost_volatility_prediction_v1_20260925, unmodified. Verified before writing this config that no unused more-recent slice exists to shortcut Stage 2 -- see module docstring.",
        "model_a_primary": "Ridge regression on the full 8-feature set (standardized), IDENTICAL specification to xgboost_volatility_prediction_v1_20260925's Model A",
        "model_b_primary": "Random Forest regression on the SAME 8-feature set (standardized) -- bagging, not boosting, chosen specifically because the closed experiment's own alternate_model:random_forest check showed RF clearing every bar XGBoost missed on this exact data/feature/target combination",
        "mechanism_hypothesis": "Bagging (bootstrap-aggregated independent trees) is structurally more robust to a subgroup of observations (a specific ticker's idiosyncratic volatility behavior) dominating the fit than boosting (sequential residual correction) is -- stated explicitly as the falsifiable reason for this hypothesis, sourced directly from the closed experiment's leave_one_ticker_out finding (AMD/SMCI exclusion flipped XGBoost's result strongly positive), not invented post-hoc",
        "rf_regularization": "NOT default hyperparameters -- max_depth in {4,6,8}, min_samples_leaf in {5,10}, max_features in {sqrt,log2}, tuned via nested CV on train+val only -- SAME grid already used as the robustness-check RF in both prior XGBoost experiments, reused for consistency, not newly invented",
        "cross_validation": "NESTED cross-validation on TRAIN+VALIDATION only (chronological, purged, TimeSeriesSplit inner loop), test period never touches hyperparameter selection -- same discipline as both prior XGBoost experiments",
        "primary_test": "paired_wilcoxon_on_per_observation_absolute_error",  # IDENTICAL to xgboost_volatility_prediction_v1_20260925
        "primary_significance_alpha_uncorrected": 0.05,
        "bonferroni_family_size": 3,
        "primary_significance_alpha_corrected": 0.0167,
        "effect_size_threshold_r2_delta": 0.05,  # IDENTICAL threshold, reused not weakened
        "min_n_per_stage": 100,  # applies to BOTH Stage 1 (already comfortably cleared -- primary test set was 174 in the closed experiment on this identical data) and Stage 2 (not yet cleared, see stage2 fields below)
        "primary_test_set_construction": "IDENTICAL locked, non-overlapping mechanism to xgboost_volatility_prediction_v1_20260925 -- first observation per (ticker, ISO calendar week) within the Stage 1 test-period pool. Full untinned test set descriptive only.",
        "leave_one_ticker_out_mandatory_disclosure": "Declared MANDATORY here, not merely included, BECAUSE a directional expectation already exists from the closed XGBoost experiment's own AMD/SMCI finding on the same underlying data -- explicitly so a repeat of that pattern is treated as a pre-specified check result, not a surprise finding requiring post-hoc justification. See module docstring's honest-caveat section.",
        "robustness_alternate_model_choice": "XGBoost -- deliberately the SWAPPED role from the closed experiment (which used Random Forest as ITS alternate-model check) -- closes the loop by directly asking whether XGBoost, now in the alternate-model slot, corroborates or contradicts Random Forest's primary result on identical data",
        "shuffled_target_placebo_note": "MANDATORY per CLAUDE.md Section 1's rule (Random Forest target randomly permuted in train+val before fitting; PASS condition is the INVERSE of the other checks -- no significant Model-B-beats-Model-A effect should appear)",
        "stage2_window_definition": (
            "ROLLING, not a fixed literal -- FIXED START 2026-07-16 (the day immediately "
            "after Stage 1's own dataset ends, 2026-07-15 -- no gap, no overlap), OPEN END "
            "determined at whatever moment Stage 2 is actually executed via a data-EXISTENCE "
            "check only (rerun generate_xgboost_volatility_dataset.py unmodified, count how "
            "many NEW rows exist past 2026-07-16 -- never by inspecting any Ridge-vs-RF "
            "result). Continue until Stage-2 joined N>=100, then LOCK the exact realized set "
            "and run the primary test ONCE against it -- same discipline as "
            "iv_term_structure_slope_v1_20260921's Stage 2 (CLAUDE.md Section 33)."
        ),
        "stage2_readiness_as_of_20260925": "NOT YET READY -- zero Stage-2 rows currently exist (verified: Stage 1's own dataset ends exactly at 2026-07-15, the max the 50-day-forward target's computability allows against today's last daily bar). Estimated wait: plausibly WEEKS (roughly 17 more real trading days x 6 tickers needed to reach N>=100), not the months GEX's own Stage 2 needed -- this only requires elapsed calendar time, not a rare qualifying signal. A disclosed ESTIMATE, to be re-checked periodically via the same data-existence query, never assumed.",
    },
    model_version=None,
    pricing_methodology="n/a_realized_volatility_prediction_only",
    execution_assumptions="none -- does not touch option pricing, spread, sizing, or execution; identical scope-isolation choice to xgboost_volatility_prediction_v1_20260925",
    train_period=("2023-10-02", "2025-06-16"),  # Stage 1, REAL boundary (not a placeholder) -- reused directly from xgboost_volatility_prediction_v1_20260925's own actual executed split on this identical dataset, since re-splitting the SAME 4,027 rows the SAME way (60/20/20 by real day-count) necessarily reproduces the same boundary
    validation_period=("2025-06-17", "2025-12-30"),  # ~20%, same reused-boundary reasoning
    test_period=("2025-12-31", "2026-07-15"),  # ~20%, same reused-boundary reasoning -- Stage 1's own LOCKED historical range; Stage 2 (separately defined in parameters.stage2_window_definition) starts the day after this ends, 2026-07-16
    random_seeds=[42, 43],
    code_version="randomforest_volatility_prediction_v1_draft",
    testing_family_declaration="INDEPENDENT_SINGLE",
    applicability_lock=[
        ("data_integrity", True), ("lookahead_audit", True), ("timestamp_safety", True),
        ("sample_size_adequacy", False),  # Stage 1 N is very likely >=100 (same dataset as the closed experiment, whose primary test set was 174) but kept False at draft time anyway -- matching this project's established convention of not marking applicability_lock flags True until Stage 1 actually executes and confirms them, even when prior knowledge makes the outcome highly likely
        ("statistical_testing", False), ("reproduction", False),
        ("primary_test_significant", False), ("effect_size_meets_threshold", False),
        ("multiple_testing_survived", False), ("robustness_survived", False),
        ("oos_survived", False),
        ("primary_performance_test_significant", False), ("concentration_check", False),
        ("pricing_accuracy_meets_threshold", False), ("pricing_coverage_meets_threshold", False),
    ],
    oos_validation_claimed=False,  # Stage 1's test_period is a LOCKED historical range on already-existing data, same reasoning as xgboost_volatility_prediction_v1_20260925 -- genuine prospective replication is Stage 2's job, tracked separately in parameters/DECISION_RULES, not this field
    declared_robustness_checks=[
        "shuffled_target_placebo",  # MANDATORY, CLAUDE.md Section 1
        "leave_one_ticker_out",  # MANDATORY, explicitly BECAUSE a directional expectation already exists -- see NOTES/docstring
        "alternate_model:xgboost",  # SWAPPED role from the closed experiment, closes the loop
        "alternate_horizon:10day",
        "alternate_horizon:50day",
    ],
)

DECISION_RULES = """
STAGE 1 VALIDATED requires ALL of:
  1. Primary (locked, non-overlapping) test-set N >= min_n_per_stage=100
     -- ALREADY KNOWN to be satisfied (174, identical dataset to the
     closed XGBoost experiment) -- confirmed at Stage 1 execution time,
     not merely assumed from the prior experiment's number
  2. Model B (Random Forest) significantly outperforms Model A (Ridge),
     SAME 8-feature set, on the PRIMARY (20-day) test set: paired one-
     sided Wilcoxon on per-observation absolute error, alpha_corrected=
     0.0167 (Bonferroni family of 3 horizons)
  3. Effect size: R-squared(Model B) - R-squared(Model A) >= 0.05
  4. Survives ALL 5 declared robustness checks in the same direction:
     shuffled_target_placebo shows NO significant effect (inverse pass
     condition), leave_one_ticker_out (ALL 6 exclusions, including
     specifically AMD and SMCI -- a repeat of the closed experiment's
     AMD/SMCI-driven reversal here counts as a FAILURE of this check,
     not a footnote), alternate_model:xgboost, alternate_horizon:10day,
     alternate_horizon:50day
  5. No single ticker or contiguous sub-period drives the entire primary-
     test effect (concentration_check)

STAGE 1 REJECTED if:
  - Primary N >= 100 but the primary test is not significant at the
    corrected alpha, OR effect size is below 0.05, OR direction reverses
    under any of the first four robustness checks, OR
    shuffled_target_placebo DOES show a significant effect (flagged
    separately as a pipeline/leakage problem)

OVERALL VALIDATED additionally requires:
  6. Stage 2 (rolling window starting 2026-07-16, open end -- see
     parameters.stage2_window_definition; N>=100 required, stop-and-lock
     via data-existence check only, never by peeking at the result)
     replicates the same direction and clears the same effect-size/
     significance bars independently

OVERALL INCONCLUSIVE if:
  - Stage 1 passes but Stage 2 has not yet reached N>=100 (CURRENT STATE
    as of 2026-09-25: Stage 2 has ZERO rows -- re-check periodically via
    the same data-existence query used for every other rolling-Stage-2
    experiment in this project)
  - Stage 1 and Stage 2 disagree in direction without a pre-specified
    tiebreaker (none specified -- would require a new, separately
    pre-registered follow-up)
"""

print("=" * 100)
print("DRAFT CONFIG -- FOR REVIEW, NOT YET PREREGISTERED")
print("=" * 100)
print("experiment_id: " + config.experiment_id)
print("experiment_type: " + config.experiment_type)
print("hypothesis: " + config.hypothesis)
print("research_question: " + config.research_question)
print("universe: " + str(config.universe))
print("date_range (Stage 1): " + str(config.date_range))
print("train_period: " + str(config.train_period))
print("validation_period: " + str(config.validation_period))
print("test_period (Stage 1): " + str(config.test_period))
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
print("run_experiment() -- registering this config into the real framework, and")
print("running Stage 1, are separate, deliberate future steps. NO DATA TOUCHED.")
print("=" * 100)

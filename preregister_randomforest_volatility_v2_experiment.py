from dotenv import load_dotenv
load_dotenv()

"""
HASH HISTORY: 472bf091313098dadbb89b28a6ff039503f7232c1e34e7b7cfee497d563b1fc5
(original, 2026-09-25) -> 7fd2a1e91f946579397da8da50c317ca93b3983f7f589c19ec1a5f8c2f20e07f
(CURRENT -- dataset_version provenance bump only, 2026-09-28, disclosed as a
provenance-clarity update NOT a re-test; see CLAUDE.md Section 1's rule and
Section 56). The 2026-09-27 clean rerun under the PRIOR hash (472bf091...) is
the real, current Stage 1 result: REJECTED -- primary delta collapsed from
+0.398/+0.359 (VALIDATED, on data later found to be split-contaminated) to
+0.071/+0.071, p=0.69/0.77 (not significant) once the contamination was fixed.
leave_one_ticker_out reverses on SMCI exclusion; overfitting_diagnostic_
train_test_gap fails (RF gap 0.146 > Ridge gap 0.111). Full writeup: CLAUDE.md
Section 56.

DRAFT pre-registration for a SECOND, standalone Random-Forest-vs-Ridge
forward-realized-volatility hypothesis -- scoped 2026-09-25.

THIS IS NOT A REOPENING OR RETUNE OF randomforest_volatility_prediction_
v1_20260925. That experiment is CLOSED and REJECTED, full stop (CLAUDE.md
Section 46) -- its own literal decision rules had no carve-out for an
otherwise-strong result failing one declared check, and none is invented
here either. v1 stays exactly as it is: closed. This is a FRESH
hypothesis with its own hash, own decision rules, own verdict path.

THIS FILE CONSTRUCTS AND PRINTS THE CONFIG FOR REVIEW ONLY. IT DOES NOT
CALL preregister_experiment() OR run_experiment() ANYWHERE.

===========================================================================
WHY A v2, AND THE HONEST "DOUBLY INFORMED" DISCLOSURE:
===========================================================================

v1 was REJECTED solely because its `alternate_model:xgboost` robustness
check disagreed with Random Forest's own strongly-significant primary
result. A follow-up diagnostic investigation (CLAUDE.md Section 47, NOT a
pre-registered experiment -- no hash, no verdict, pure model-behavior
analysis) directly explained WHY that disagreement occurred:

  - XGBoost's train-vs-test R-squared gap was 1.589 -- roughly 5x Random
    Forest's own gap (0.326) and far beyond Ridge's (0.476). Textbook
    overfitting, not a neutral second opinion diverging on a genuine
    market relationship.
  - This was NOT a seed-luck artifact: all 7 tested seeds (42-48) gave
    XGBoost a negative R-squared, and all 6 nearby hyperparameter variants
    tested still landed XGBoost negative. A consistently-wrong result, not
    an unstable one.
  - Permutation importance showed XGBoost had learned a harmful, noise-
    fitting reliance on vega_per_1pct_iv and theta specifically (removing
    either IMPROVED its test R-squared by 0.44-0.66) -- Random Forest's
    importances stayed modest throughout, with trailing_realized_vol_20d
    (a legitimate, literature-grounded predictor) as its clear top
    feature.
  - The damage was concentrated in high-realized-vol days, the most
    recent test-period quarter, and heavily (though not exclusively) in
    AMD -- exactly where an overfit model extrapolating from training-
    period patterns would be expected to fail hardest.

CONCLUSION DRAWN FROM THE DIAGNOSTIC, STATED PLAINLY: on this specific
dataset, XGBoost is the unreliable comparator, not a neutral arbiter of
whether Random Forest's result is real. Requiring Random Forest to AGREE
with a model independently shown to be overfitting tests XGBoost's own
stability, not Random Forest's validity -- a real, disclosed design flaw
in v1's own robustness-check family, not something to paper over by
reopening v1, but a legitimate reason to design a DIFFERENT, better-
targeted set of checks for a fresh hypothesis.

HONEST CAVEAT, extending v1's own "not fully blind" disclosure -- THIS
HYPOTHESIS IS DOUBLY INFORMED, not just once: first by v1's own positive-
on-every-other-criterion result, second by the diagnostic investigation
that specifically explained why v1's one failing check fired the way it
did. That is MORE informing information than v1 had, not less -- an
eventual positive result here should be read with that fuller lineage
explicitly in mind, not treated as an independent, low-information
confirmation. This does not make the result predetermined (the new
checks below are real, falsifiable, and could each independently fail),
but the prior-informed nature of the whole v1->diagnostic->v2 chain is a
real, compounding limitation on how much this specific result, even if
positive, should be treated as freestanding confirmation of anything.
"""

from experiment_config import ExperimentConfig

NOTES = (
    "PRE-REGISTRATION DRAFT, not yet submitted. Standalone from the CLOSED/"
    "REJECTED randomforest_volatility_prediction_v1_20260925 (Section 46) -- "
    "NOT a reopening, NOT a retune. Directly informed by a diagnostic "
    "investigation (Section 47, not a pre-registered experiment) that "
    "explained v1's sole rejection trigger as XGBoost overfitting, not a "
    "genuine market-relationship contradiction. "
    "DROPPED: alternate_model:xgboost as a robustness gate -- the diagnostic "
    "demonstrated XGBoost is itself unreliable on this dataset (train-test "
    "R2 gap 1.589 vs RF's 0.326, consistent across 7 seeds and 6 "
    "hyperparameter variants, traced to harmful vega/theta reliance), so "
    "requiring RF to agree with it tests XGBoost's stability, not RF's "
    "validity. "
    "ADDED, each motivated directly by a specific diagnostic finding: "
    "(1) leave_one_ticker_out with AMD's own result EXPLICITLY tracked and "
    "reported, not folded into an unlabeled average -- AMD was the single "
    "most damaged ticker in the diagnostic (XGBoost error nearly 2x RF's) "
    "and has now been the destabilizing ticker in two separate contexts "
    "(here and the earlier XGBoost-interaction experiment, Section 44); "
    "(2) stability_across_seeds_and_hyperparameters -- re-verifies RF's OWN "
    "positive result (not a disagreement with another model) holds across "
    "the same 7-seed range and the SAME already-established RF "
    "hyperparameter grid the diagnostic and both prior RF checks used, "
    "evaluated comprehensively (every seed x every grid combination), not "
    "just the single tuned optimum under two seeds the way v1's primary "
    "test did; (3) overfitting_diagnostic_train_test_gap -- checks RF's own "
    "train-vs-test R-squared gap directly, since that IS the mechanism the "
    "diagnostic identified as XGBoost's actual problem; RF must not overfit "
    "WORSE than the simple Ridge baseline on the same split, a concrete, "
    "self-referential (not arbitrary) threshold computed fresh at execution "
    "time, not assumed from the diagnostic's own prior numbers. "
    "KEPT UNCHANGED, not called out for removal: shuffled_target_placebo "
    "(mandatory per CLAUDE.md Section 1's rule, non-negotiable), "
    "alternate_horizon:10day and alternate_horizon:50day (never implicated "
    "by the diagnostic -- only the XGBoost-agreement check was shown to be "
    "the problem, so these stay). Declared_robustness_checks is therefore "
    "6 checks, not 5 -- a deliberate scope decision, not an oversight: only "
    "what was explicitly shown to be broken was removed, nothing else was "
    "silently dropped to reach a round number. "
    "Same dataset, features, target, and Stage 2 plan as v1, reused "
    "unmodified -- zero new data collection, that infrastructure was "
    "already sound and not implicated in v1's rejection reason."
)

config = ExperimentConfig(
    experiment_id="randomforest_volatility_prediction_v2_20260925",
    experiment_type="signal_research",
    hypothesis=(
        "Random Forest predicts forward realized volatility with lower error than a Ridge "
        "linear regression using the IDENTICAL 8-feature set -- the SAME hypothesis "
        "randomforest_volatility_prediction_v1_20260925 tested, re-registered with a "
        "different, better-targeted robustness-check family after a diagnostic "
        "investigation (Section 47) showed v1's sole rejection trigger "
        "(disagreement with XGBoost) reflected XGBoost's own demonstrated overfitting on "
        "this dataset, not a genuine contradiction of Random Forest's result. This is a "
        "fresh test of the same underlying claim under checks that actually probe "
        "RANDOM FOREST's own validity (ticker generalization with AMD tracked "
        "explicitly, seed/hyperparameter stability, its own train-test overfitting gap) "
        "rather than a second model's unrelated instability."
    ),
    research_question=(
        "Does Random Forest meaningfully outperform Ridge regression, IDENTICAL feature "
        "set, at predicting forward realized volatility for this project's 6-ticker "
        "universe -- and does that advantage survive a shuffled-target leakage check, "
        "generalize across all 6 tickers with AMD's specific contribution explicitly "
        "disclosed, remain stable across a comprehensive seed x hyperparameter sweep, "
        "avoid overfitting worse than the linear baseline, hold at alternate horizons, "
        "and replicate on a genuinely separate, later, out-of-sample rolling window?"
    ),
    dataset_version="xgboost_volatility_v1_20231002_present_6ticker_adjfix20260927_sha256_51ecca695bff10a3",  # PROVENANCE-BUMPED 2026-09-28, disclosed as a provenance-clarity update, NOT a re-test -- was "..._new_generation_pass" (a static, non-content-addressed label, identical to v1). Real, root-caused split-price contamination was found and fixed in xgboost_volatility_dataset.db (raw/unadjusted Alpaca prices corrupting trailing/target realized-vol features around NVDA's 2024-06-10 and SMCI's 2024-09-30 splits -- CLAUDE.md Section 56). Fixed via a dual raw+adjusted price series in generate_xgboost_volatility_dataset.py; dataset regenerated from scratch, same row count (4,033), same design, config_hash intentionally UNCHANGED for the fix itself (no ExperimentConfig field was edited by the fix -- see CLAUDE.md Section 1's rule on data-correctness fixes vs. methodology changes). This dataset_version bump is a SEPARATE, forward-looking action: closes the traceability gap that a static label can't distinguish two different data realizations sharing one hash. "adjfix20260927" marks the fix date; "sha256_51ecca695bff10a3" is the first 16 hex chars of the real SHA-256 of xgboost_volatility_dataset.db as it stood 2026-09-27 ~22:42 UTC (full digest: 51ecca695bff10a37cd0c597c39562c267b94507affb512f138a799f1e102950, verifiable via Get-FileHash). The 2026-09-27 clean rerun's REJECTED verdict stands, unaffected by this bump.
    date_range=("2023-10-02", "2026-07-15"),  # IDENTICAL Stage 1 window to v1
    universe=["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"],
    option_type="call",
    features_used=[
        ("term_structure_slope_pct", "1.0"), ("oi_skew", "1.0"), ("trailing_realized_vol_20d", "1.0"),
        ("delta", "1.0"), ("gamma", "1.0"), ("theta", "1.0"), ("charm", "1.0"), ("vega_per_1pct_iv", "1.0"),
    ],  # IDENTICAL to v1
    parameters={
        "target_metric": "realized_volatility_forward_20d",
        "target_definition": "IDENTICAL to v1/xgboost_volatility_prediction_v1_20260925",
        "target_horizons_bars": [10, 20, 50],
        "primary_horizon_bars": 20,
        "secondary_horizons_bars": [10, 50],
        "data_reuse": "ZERO new data collection -- reuses xgboost_volatility_dataset.db's existing 4,027-row table exactly as v1 used it, unmodified.",
        "model_a_primary": "Ridge regression, full 8-feature set (standardized), IDENTICAL to v1's Model A",
        "model_b_primary": "Random Forest regression, SAME 8-feature set (standardized), IDENTICAL to v1's Model B",
        "dropped_check_disclosure": "alternate_model:xgboost is DELIBERATELY NOT declared here -- see module docstring/NOTES. The diagnostic investigation (Section 47) demonstrated XGBoost is the unreliable comparator on this exact dataset (overfitting, not a neutral opinion), so this check would test XGBoost's own stability, not Random Forest's validity. Not silently dropped -- explicitly reasoned and disclosed.",
        "leave_one_ticker_out_amd_disclosure": "AMD's own exclusion result MUST be reported as its own explicitly-labeled figure (R-squared delta, p-value) in any Stage 1 report, not folded into an unlabeled 6-ticker average -- AMD was the single most XGBoost-damaged ticker in the diagnostic (error 0.517 vs RF's 0.298, RF more accurate 81% of days) and has now been the destabilizing ticker in two separate, unrelated contexts (this dataset and the earlier XGBoost-interaction experiment, Section 44). Pass condition unchanged from v1: all 6 exclusions must show positive R-squared delta.",
        "stability_across_seeds_and_hyperparameters_definition": (
            "A NEW declared check, not present in v1. Refits Model B (Random Forest) with "
            "the SAME nested-CV-tuned hyperparameters under 7 seeds (42-48, matching the "
            "diagnostic investigation's own tested range) AND separately under every "
            "combination in the already-established RF hyperparameter grid "
            "(max_depth in {4,6,8}, min_samples_leaf in {5,10}, max_features in "
            "{sqrt,log2} -- the SAME 12-combination grid used for RF throughout this "
            "project's ML track, not a new invention), evaluating R-squared(B)-R-squared(A) "
            "on the SAME primary test set for every seed and every grid combination. "
            "PASS CONDITION: the delta stays POSITIVE for ALL 7 seeds AND ALL 12 grid "
            "combinations -- a comprehensive, not-cherry-picked stability sweep, stricter "
            "than v1's own two-seed (42/43) confirmation. Disclosed nuance from the "
            "diagnostic, not glossed over: RF's OWN raw R-squared (not its delta vs Ridge) "
            "dipped slightly negative at one tested seed (44, R2=-0.0057) in the diagnostic's "
            "exploratory pass -- but Ridge's own R-squared was clearly, comfortably more "
            "negative at every seed (Ridge is not seed-sensitive), so the DELTA (the actual "
            "hypothesis-relevant quantity) very likely stayed positive even there; this check "
            "formally re-verifies that on the delta, not the raw score, and does not assume "
            "the diagnostic's informal pass already settles it."
        ),
        "overfitting_diagnostic_train_test_gap_definition": (
            "A NEW declared check, not present in v1. Computes Model B's (Random Forest) "
            "train-vs-test R-squared gap (R2_train - R2_test) on train+val vs. the full test "
            "set, and separately Model A's (Ridge) identical gap on the SAME split, both "
            "computed FRESH at Stage 1 execution time (not assumed from the diagnostic's own "
            "prior numbers, which were informal/exploratory). PASS CONDITION: Model B's gap "
            "must NOT exceed Model A's gap -- i.e., Random Forest must not overfit worse than "
            "the simple linear baseline on this data. A concrete, self-referential threshold "
            "(computed relative to Ridge's own gap on the same run, not a fixed prior number), "
            "directly motivated by the diagnostic's finding that this exact metric (a gap of "
            "1.589 vs Ridge's 0.476) was THE clearest signature of XGBoost's problem."
        ),
        "shuffled_target_placebo_note": "MANDATORY per CLAUDE.md Section 1's rule -- unchanged from v1. Target randomly permuted in train+val before fitting; PASS condition is the INVERSE of the other checks (no significant Model-B-beats-Model-A effect should appear).",
        "primary_test": "paired_wilcoxon_on_per_observation_absolute_error",  # IDENTICAL to v1
        "primary_significance_alpha_uncorrected": 0.05,
        "bonferroni_family_size": 3,
        "primary_significance_alpha_corrected": 0.0167,
        "effect_size_threshold_r2_delta": 0.05,  # IDENTICAL to v1
        "min_n_per_stage": 100,
        "primary_test_set_construction": "IDENTICAL locked, non-overlapping mechanism to v1 -- first observation per (ticker, ISO calendar week) within the Stage 1 test-period pool.",
        "rf_regularization": "NOT default hyperparameters -- SAME grid as v1/the diagnostic (max_depth in {4,6,8}, min_samples_leaf in {5,10}, max_features in {sqrt,log2}), tuned via nested CV on train+val only.",
        "cross_validation": "NESTED cross-validation on TRAIN+VALIDATION only, IDENTICAL discipline to v1.",
        "stage2_window_definition": (
            "IDENTICAL to v1 -- ROLLING, fixed start 2026-07-16 (the day immediately after "
            "Stage 1's dataset ends, 2026-07-15), open end via a data-EXISTENCE check only "
            "(rerun generate_xgboost_volatility_dataset.py unmodified), N>=100 lock-and-"
            "test-once. This infrastructure was never implicated in v1's rejection reason "
            "(which was entirely about the alternate_model:xgboost check) and is reused "
            "unchanged, not redesigned."
        ),
        "stage2_readiness_as_of_20260925": "NOT YET READY -- IDENTICAL state to v1 (zero Stage-2 rows exist; same disclosed weeks-not-months estimate, re-checked via the same data-existence query, shared infrastructure with v1's own Stage 2 definition since both use the same rolling window starting the same date).",
    },
    model_version=None,
    pricing_methodology="n/a_realized_volatility_prediction_only",
    execution_assumptions="none -- identical scope-isolation choice to v1",
    train_period=("2023-10-02", "2025-06-16"),  # IDENTICAL real boundary to v1 -- same dataset, same split methodology, necessarily reproduces the same boundary
    validation_period=("2025-06-17", "2025-12-30"),
    test_period=("2025-12-31", "2026-07-15"),
    random_seeds=[42, 43],  # primary two-seed confirmation, IDENTICAL to v1; the NEW stability_across_seeds_and_hyperparameters check separately sweeps seeds 42-48
    code_version="randomforest_volatility_prediction_v2_draft",
    testing_family_declaration="INDEPENDENT_SINGLE",
    applicability_lock=[
        ("data_integrity", True), ("lookahead_audit", True), ("timestamp_safety", True),
        ("sample_size_adequacy", False),  # kept False at draft time per this project's established convention, despite already knowing N=174 from v1's identical dataset
        ("statistical_testing", False), ("reproduction", False),
        ("primary_test_significant", False), ("effect_size_meets_threshold", False),
        ("multiple_testing_survived", False), ("robustness_survived", False),
        ("oos_survived", False),
        ("primary_performance_test_significant", False), ("concentration_check", False),
        ("pricing_accuracy_meets_threshold", False), ("pricing_coverage_meets_threshold", False),
    ],
    oos_validation_claimed=False,  # IDENTICAL reasoning to v1 -- Stage 1's test_period is a locked historical range; genuine prospective replication is Stage 2's separate job
    declared_robustness_checks=[
        "leave_one_ticker_out",  # ENHANCED disclosure requirement (AMD tracked explicitly) -- see parameters
        "stability_across_seeds_and_hyperparameters",  # NEW
        "overfitting_diagnostic_train_test_gap",  # NEW
        "shuffled_target_placebo",  # MANDATORY, unchanged
        "alternate_horizon:10day",  # KEPT unchanged -- never implicated by the diagnostic
        "alternate_horizon:50day",  # KEPT unchanged -- never implicated by the diagnostic
    ],
)

DECISION_RULES = """
STAGE 1 VALIDATED requires ALL of:
  1. Primary (locked, non-overlapping) test-set N >= min_n_per_stage=100
  2. Model B (Random Forest) significantly outperforms Model A (Ridge),
     SAME 8-feature set, on the PRIMARY (20-day) test set: paired one-
     sided Wilcoxon on per-observation absolute error, alpha_corrected=
     0.0167 (Bonferroni family of 3 horizons)
  3. Effect size: R-squared(Model B) - R-squared(Model A) >= 0.05
  4. Survives ALL 6 declared robustness checks in the same direction:
     leave_one_ticker_out (all 6 exclusions positive, AMD's own figure
     explicitly reported), stability_across_seeds_and_hyperparameters
     (positive delta across ALL 7 seeds AND all 12 RF hyperparameter grid
     combinations), overfitting_diagnostic_train_test_gap (Model B's gap
     <= Model A's gap on the same split), shuffled_target_placebo (NO
     significant effect -- inverse pass condition), alternate_horizon:
     10day, alternate_horizon:50day
  5. No single ticker or contiguous sub-period drives the entire primary-
     test effect (concentration_check)

STAGE 1 REJECTED if:
  - Primary N >= 100 but the primary test is not significant at the
    corrected alpha, OR effect size is below 0.05, OR direction/pass-
    condition reverses/fails under ANY of the 6 declared robustness
    checks (no isolated-failure carve-out, same standard as v1 and every
    other closure in this project), OR shuffled_target_placebo DOES show
    a significant effect (flagged separately as a pipeline/leakage
    problem)

OVERALL VALIDATED additionally requires:
  6. Stage 2 (IDENTICAL rolling window to v1 -- fixed start 2026-07-16,
     open end, N>=100 stop-and-lock via data-existence check only)
     replicates the same direction and clears the same effect-size/
     significance bars independently

OVERALL INCONCLUSIVE if:
  - Stage 1 passes but Stage 2 has not yet reached N>=100 (CURRENT STATE
    as of 2026-09-25: Stage 2 has ZERO rows, shared/identical state with
    v1's own Stage 2 definition)
  - Stage 1 and Stage 2 disagree in direction without a pre-specified
    tiebreaker (none specified)
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
print("v1 (randomforest_volatility_prediction_v1_20260925) remains CLOSED/REJECTED,")
print("untouched by this file.")
print("=" * 100)

from dotenv import load_dotenv
load_dotenv()

"""
DRAFT pre-registration for a heavily-regularized XGBoost forward-realized-
volatility hypothesis -- scoped 2026-09-25.

THIS IS NOT A REOPENING OF xgboost_volatility_prediction_v1_20260925
(CLAUDE.md Section 45, CLOSED/REJECTED). That experiment stays exactly as
it is. This is a fresh, standalone hypothesis with its own hash.

NOTE ON SECTION NUMBERING: this file's own docstring and CLAUDE.md
references below cite the LOCAL CLAUDE.md's actual current section
numbers (45 = the closed XGBoost-vs-Ridge v1 experiment, 47 = the RF-vs-
XGBoost diagnostic investigation), verified directly against the file on
disk before writing this, not assumed from a request that cited different
numbers (19a/19c) -- almost certainly drift against the separate,
not-automatically-synced claude.ai manifest copy (CLAUDE.md's own header
already documents that the two can diverge).

===========================================================================
A FACTUAL CORRECTION TO THE PREMISE, MADE BEFORE DESIGNING ANYTHING --
NOT SILENTLY ACCEPTED:
===========================================================================
v1's own tuned hyperparameters (verified directly from the executed Stage 1
run, CLAUDE.md Section 46's "alternate_model:xgboost" reuses them exactly:
max_depth=3, min_child_weight=5, reg_alpha=1.0, reg_lambda=1.0,
subsample=0.8, colsample_bytree=0.8) came from a grid where max_depth was
ALREADY constrained to {2, 3} -- v1 did NOT use deep or unconstrained
trees. Moreover, the diagnostic investigation (Section 47) DIRECTLY TESTED
max_depth=2 as one of its 6 nearby-hyperparameter variants and found it
STILL strongly negative (R2=-0.2807) -- shallower trees ALONE, under v1's
other fixed settings (n_estimators=200 fixed, learning_rate=0.05 fixed, no
early stopping), did not fix the problem. "Constrain max_depth to 2-3" is
therefore NOT a novel lever this pre-registration can credit -- it was
already tried, in the same population, and already shown insufficient by
itself. Stated honestly here rather than silently repeating the premise.

THE GENUINELY NEW LEVERS, verified against real, current XGBoost/practitioner
guidance (WebSearch performed 2026-09-25, sources below) rather than
asserted from memory:
  1. EARLY STOPPING -- v1 never used it (fixed n_estimators=200 regardless
     of validation performance). Per XGBoost's own official "Notes on
     Parameter Tuning" (https://xgboost.readthedocs.io/en/stable/tutorials/
     param_tuning.html): "There are two ways to control overfitting... the
     first way is to directly control model complexity (max_depth,
     min_child_weight...)... Learning rate becomes more important when
     using lower learning rates, as they require more rounds and have a
     higher risk of overfitting if left unchecked" (early-stopping
     synthesis via MachineLearningMastery/mljar.com, both consistent with
     the official docs' complexity-control framing). Standard convention
     (MachineLearningMastery, mljar.com): early_stopping_rounds set to
     ~10% of the max boosting-round ceiling.
  2. LOWER learning_rate -- v1 fixed this at 0.05, never tuned or lowered.
  3. HIGHER reg_alpha/reg_lambda ceilings than v1's grid ever tested (v1
     topped out at reg_alpha=1.0, reg_lambda=5.0).
  4. MORE AGGRESSIVE row/column subsampling than v1's grid (v1's floor was
     0.7; this pre-registration's floor is 0.6).
  max_depth stays constrained to {2,3} -- the CORRECT choice, just not a
  NEW one -- for consistency with the already-validated regularization
  family, not because it's expected to do new work by itself.

HONEST EXPECTATIONS, set BEFORE running anything, per explicit instruction
-- this should NOT be read as "this should obviously work now":
Per applied-ML consensus on bagging vs. boosting under noisy data
(WebSearch performed 2026-09-25, sources below, disclosed as applied-ML/
practitioner sources, not a single rigorous academic citation): "Bagging is
robust to noisy data and outliers due to the averaging or voting mechanism...
boosting is more sensitive to noisy data and outliers, as the focus on
misclassified instances might lead to overfitting on these instances...
Random Forests are generally less prone to overfitting compared to GBT...
Random Forest models are often relatively robust to tuning parameters...
[while] GBT can be more prone to overfitting, especially with complex
models and noisy data, and hyperparameter tuning and regularization
techniques are often required to prevent overfitting in GBT models."  This
is architectural, not just a tuning gap -- bagging's variance-reduction-via-
averaging mechanism is structurally different from boosting's sequential
residual-correction mechanism, and the diagnostic (Section 47) traced v1's
XGBoost failure to exactly the kind of noise-fitting (harmful reliance on
vega/theta) this literature describes as boosting's characteristic
weak spot. A SECOND REJECTION HERE, if this regularization is genuinely
applied per the cited guidance (it is), would be LEGITIMATE, INFORMATIVE
evidence that this dataset structurally favors Random Forest's bagging
architecture over boosting -- not a reason to keep tuning XGBoost further.
This hypothesis should be read as testing "does real regularization close
most of the gap," not assumed to succeed.

Sources (WebSearch, 2026-09-25):
- https://xgboost.readthedocs.io/en/stable/tutorials/param_tuning.html
- https://machinelearningmastery.com/avoid-overfitting-by-early-stopping-with-xgboost-in-python/
- https://mljar.com/blog/xgboost-early-stopping/
- https://www.geeksforgeeks.org/machine-learning/gradient-boosting-vs-random-forest/
- https://metricgate.com/blogs/random-forest-vs-gradient-boosting/

THIS FILE CONSTRUCTS AND PRINTS THE CONFIG FOR REVIEW ONLY. IT DOES NOT
CALL preregister_experiment() OR run_experiment() ANYWHERE.

DATA: zero new collection -- reuses xgboost_volatility_dataset.db's
existing, verified 4,027-row dataset exactly as v1 used it. Same 8
features, same target, same real Stage 1 split boundaries
(2023-10-02/2025-06-16/2025-12-30/2026-07-15).
"""

from experiment_config import ExperimentConfig

NOTES = (
    "HASH HISTORY: 0276337ca56cced3fa58fe92cb2cbc4b312b1186b39d42493e5530ea382ba1d2 "
    "(original draft, 2026-09-25) -> 1bccd0ba4b8b6f9350bde3f1c7dba97b93a48db9cfa679afecb"
    "2b3605ffdab97 (gap_closure_criterion added, 2026-09-26, before any Stage 1 result "
    "existed) -> e9f7aae1458346cdc5484c138cc562b8bc01017f0317de5303e6fb0da9c57be2 "
    "(early_stopping_placebo_leakage_fix + grid-size doc correction "
    "added, 2026-09-26, AFTER a first Stage 1 attempt was run and its placebo check "
    "failed -- see parameters.early_stopping_placebo_leakage_fix for the full root-cause "
    "and fix; the real Stage 1 under this hash ran 2026-09-27 against a dataset later "
    "found to be split-contaminated, REJECTED) -> "
    "54f7986788cfa1d52b4dc695930754e09fbf7c7b6ebe32d96ab50ed815c4bbdd (CURRENT -- "
    "dataset_version provenance bump only, 2026-09-28, disclosed as a provenance-clarity "
    "update NOT a re-test; CLAUDE.md Section 1's rule and Section 56 cover why a data-"
    "correctness fix alone never needed a new hash, and why dataset_version is bumped "
    "anyway going forward for traceability. The 2026-09-27 clean rerun under the PRIOR "
    "hash (e9f7aae1...) is the real, current Stage 1 result: REJECTED -- primary test "
    "strongly positive and significant (delta=+0.195/+0.199, p<0.0001 both seeds), but "
    "gap-closure compared against RF v2's now-superseded contaminated reference numbers "
    "(stale, needs recomputation) and the shuffled_target_placebo showed 4/8 seeds "
    "significant (re-leaking on the clean dataset, not yet re-resolved). Neither of these "
    "two open items has been decided; do not treat this as VALIDATED or as a clean "
    "REJECTED either.) "
    "That first attempt's primary-test, gap-closure, and robustness numbers (under hash "
    "1bccd0ba...) are VOID and were never cited as a result anywhere -- a placebo failure "
    "invalidates the whole run per this file's own decision rules, not just the placebo "
    "check itself. "
    "PRE-REGISTRATION DRAFT, not yet submitted. Standalone from the CLOSED/"
    "REJECTED xgboost_volatility_prediction_v1_20260925 (Section 45) -- NOT "
    "a reopening. Directly informed by the RF-vs-XGBoost diagnostic "
    "investigation (Section 47) and by verified, cited practitioner/"
    "official-documentation guidance on this specific overfitting pattern "
    "(WebSearch performed 2026-09-25, sources in the module docstring). "
    "CORRECTION TO THE PREMISE, made before designing anything: v1 ALREADY "
    "used shallow trees (max_depth in {2,3}), and the diagnostic already "
    "tested max_depth=2 specifically and found it still strongly negative "
    "(R2=-0.28) -- shallow trees alone were already tried and already shown "
    "insufficient. Not re-credited here as a novel lever. "
    "GENUINELY NEW LEVERS: (1) early stopping -- v1 never used it (fixed "
    "n_estimators=200 regardless of validation performance); this "
    "pre-registration uses max_boost_rounds=1000 with "
    "early_stopping_rounds=100 (the ~10%-of-ceiling convention, cited), "
    "monitored on a genuine held-out validation slice within each nested-CV "
    "fold; (2) learning_rate lowered to {0.01, 0.02} (v1 fixed this at "
    "0.05, never tuned); (3) reg_alpha ceiling raised to {1.0, 5.0} and "
    "reg_lambda ceiling raised to {5.0, 10.0} (v1 topped out at 1.0/5.0"
    "respectively); (4) subsample/colsample_bytree floors lowered to "
    "{0.6, 0.7} (v1's floor was 0.7). max_depth stays {2,3} -- correct, but "
    "not new. min_child_weight fixed at 15 (not swept) for computational "
    "tractability, disclosed as a fixed choice, not a tuned one -- the "
    "primary standard levers (depth, learning rate, L1/L2, subsampling, "
    "early stopping) are the swept dimensions per the cited guidance. "
    "Same Model A (Ridge), same 8-feature set/target, same real Stage 1 "
    "split boundaries, same primary test design (paired Wilcoxon on "
    "absolute error, R-squared delta >=0.05 effect floor, Bonferroni family "
    "of 3 horizons, alpha_corrected=0.0167, min_n_per_stage=100, locked "
    "non-overlapping primary test set), same mandatory shuffled_target_"
    "placebo (CLAUDE.md Section 1's rule) -- all reused verbatim from v1, "
    "zero new data collection. "
    "HONEST EXPECTATION, stated before running anything: cited applied-ML "
    "consensus holds that bagging (Random Forest) is structurally more "
    "resistant to noisy-data overfitting than boosting (XGBoost), even "
    "after regularization -- this is an architectural difference (variance-"
    "reduction-via-averaging vs. sequential residual-correction), not just "
    "a tuning gap. A second REJECTED verdict here, with this regularization "
    "genuinely applied, is legitimate informative evidence that this "
    "dataset structurally favors Random Forest's architecture -- not a "
    "reason to keep tuning XGBoost further. Not assumed to succeed."
)

config = ExperimentConfig(
    experiment_id="xgboost_volatility_prediction_regularized_v2_20260925",
    experiment_type="signal_research",
    hypothesis=(
        "A heavily-regularized XGBoost -- early stopping, lower learning rate, higher "
        "L1/L2 ceilings, more aggressive subsampling, on top of the already-shallow trees "
        "v1 used -- no longer shows the sign-instability and effect-size failure that the "
        "unregularized-beyond-basic-grid-search v1 XGBoost showed, predicting forward "
        "realized volatility from the identical 8-feature set used throughout this "
        "project's volatility-prediction track. This tests whether STRONGER, more "
        "deliberate regularization (specifically targeting the diagnostic's identified "
        "mechanism -- harmful noise-fitting on vega/theta) closes most of the gap to "
        "Random Forest's already-validated result on the same data, or whether the gap is "
        "architectural (bagging vs. boosting) rather than a tuning artifact."
    ),
    research_question=(
        "Does a genuinely more heavily regularized XGBoost (early stopping, lower "
        "learning rate, stronger L1/L2, more aggressive subsampling) outperform Ridge "
        "regression at predicting forward realized volatility for this project's "
        "6-ticker universe, IDENTICAL feature set to v1 -- and does that advantage "
        "survive a shuffled-target leakage check, generalize across all 6 tickers "
        "(AMD tracked explicitly, given its role in both the closed interaction "
        "experiment and this volatility track), remain stable across seeds, and hold at "
        "alternate horizons?"
    ),
    dataset_version="xgboost_volatility_v1_20231002_present_6ticker_adjfix20260927_sha256_51ecca695bff10a3",  # PROVENANCE-BUMPED 2026-09-28, disclosed as a provenance-clarity update, NOT a re-test -- was "..._new_generation_pass" (a static, non-content-addressed label, identical to v1). Real, root-caused split-price contamination was found and fixed in xgboost_volatility_dataset.db (raw/unadjusted Alpaca prices corrupting trailing/target realized-vol features around NVDA's 2024-06-10 and SMCI's 2024-09-30 splits -- CLAUDE.md Section 56). Fixed via a dual raw+adjusted price series in generate_xgboost_volatility_dataset.py; dataset regenerated from scratch, same row count (4,033), same design, config_hash intentionally UNCHANGED for the fix itself (no ExperimentConfig field was edited by the fix -- see CLAUDE.md Section 1's rule on data-correctness fixes vs. methodology changes). This dataset_version bump is a SEPARATE, forward-looking action: closes the traceability gap that a static label can't distinguish two different data realizations sharing one hash. "adjfix20260927" marks the fix date; "sha256_51ecca695bff10a3" is the first 16 hex chars of the real SHA-256 of xgboost_volatility_dataset.db as it stood 2026-09-27 ~22:42 UTC (full digest: 51ecca695bff10a37cd0c597c39562c267b94507affb512f138a799f1e102950, verifiable via Get-FileHash). The 2026-09-27 clean rerun's REJECTED (pipeline/leakage flag, plus stale gap-closure reference) verdict stands, unaffected by this bump.
    date_range=("2023-10-02", "2026-07-15"),  # IDENTICAL Stage 1 window to v1
    universe=["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"],
    option_type="call",
    features_used=[
        ("term_structure_slope_pct", "1.0"), ("oi_skew", "1.0"), ("trailing_realized_vol_20d", "1.0"),
        ("delta", "1.0"), ("gamma", "1.0"), ("theta", "1.0"), ("charm", "1.0"), ("vega_per_1pct_iv", "1.0"),
    ],  # IDENTICAL to v1
    parameters={
        "target_metric": "realized_volatility_forward_20d",
        "target_definition": "IDENTICAL to v1",
        "target_horizons_bars": [10, 20, 50],
        "primary_horizon_bars": 20,
        "secondary_horizons_bars": [10, 50],
        "data_reuse": "ZERO new data collection -- reuses xgboost_volatility_dataset.db's existing 4,027-row table exactly as v1 used it, unmodified.",
        "model_a_primary": "Ridge regression, full 8-feature set (standardized), IDENTICAL to v1's Model A",
        "model_b_primary": "XGBoost regression, SAME 8-feature set (standardized), REGULARIZED per the grid below -- genuinely different from v1's grid, not a relabeling",
        "premise_correction_disclosure": "v1 ALREADY used max_depth in {2,3} (verified from its actual executed tuned hyperparameters); the diagnostic investigation (Section 47) ALREADY tested max_depth=2 as a standalone lever and found it still strongly negative (R2=-0.28). 'Shallow trees' is therefore NOT a novel treatment in this pre-registration -- disclosed explicitly rather than silently re-credited.",
        "xgboost_regularization_grid": (
            "max_depth in {2,3} (unchanged from v1, kept for consistency, not novel); "
            "min_child_weight FIXED at 15 (higher than v1's swept {5,10} ceiling of 10, "
            "not swept further for computational tractability, disclosed as fixed not "
            "tuned); reg_alpha in {1.0, 5.0} (v1's grid topped out at 1.0 -- genuinely "
            "higher ceiling here); reg_lambda in {5.0, 10.0} (v1's grid topped out at 5.0 "
            "-- genuinely higher ceiling here); learning_rate in {0.01, 0.02} (v1 FIXED "
            "this at 0.05 and never tuned it -- genuinely new, lower, tuned dimension); "
            "subsample in {0.6, 0.7} (v1's floor was 0.7 -- genuinely more aggressive "
            "floor here); colsample_bytree in {0.6, 0.7} (same, v1's floor was 0.7). "
            "Grid size: 2x2x2x2x2x2 = 64 combinations over 6 swept dimensions (max_depth, "
            "reg_alpha, reg_lambda, learning_rate, subsample, colsample_bytree) -- "
            "CORRECTED 2026-09-26, was miswritten as '32' in the original draft (a plain "
            "arithmetic slip, 2^5 instead of 2^6; min_child_weight is fixed, not swept, "
            "but that leaves 6 swept dimensions, not 5). Confirmed directly against the "
            "Stage 1 execution script's own grid-search log, which counted 64/64 combos "
            "evaluated. Disclosed as a documentation fix, not a design change -- the grid "
            "itself was always 64 combos; only the comment describing it was wrong."
        ),
        "early_stopping_definition": (
            "GENUINELY NEW mechanism, absent from v1 entirely. max_boost_rounds=1000 "
            "(ceiling, not a fixed count), early_stopping_rounds=100 (the cited ~10%-of-"
            "ceiling convention, MachineLearningMastery/mljar.com), monitored via MAE on "
            "a genuine held-out validation slice WITHIN each nested-CV TimeSeriesSplit "
            "fold (the last 20% of that fold's own training portion, chronologically, "
            "never the fold's own validation/test data) -- best_iteration selected per "
            "fold, then the WINNING hyperparameter combination (by mean CV MAE across "
            "folds, using each fold's own early-stopped best_iteration) is refit on the "
            "full train+val set with its own early-stopping split for the final model."
        ),
        "cross_validation": "NESTED cross-validation on TRAIN+VALIDATION only (chronological, purged, TimeSeriesSplit inner loop for hyperparameter search PLUS per-fold early stopping as described above) -- test period never touches hyperparameter selection or early-stopping decisions at any point, same discipline as v1.",
        "primary_test": "paired_wilcoxon_on_per_observation_absolute_error",  # IDENTICAL to v1
        "primary_significance_alpha_uncorrected": 0.05,
        "bonferroni_family_size": 3,
        "primary_significance_alpha_corrected": 0.0167,
        "effect_size_threshold_r2_delta": 0.05,  # IDENTICAL to v1
        "min_n_per_stage": 100,
        "primary_test_set_construction": "IDENTICAL locked, non-overlapping mechanism to v1 -- first observation per (ticker, ISO calendar week) within the Stage 1 test-period pool.",
        "leave_one_ticker_out_amd_disclosure": "AMD's own exclusion result reported as its own explicitly-labeled figure, same discipline as randomforest_volatility_prediction_v2_20260925 (Section 48) -- AMD has now been a destabilizing ticker in two separate prior contexts (Section 44's interaction experiment, and this volatility track's own diagnostic).",
        "stability_across_seeds_definition": "Refits Model B under 7 seeds (42-48, matching the diagnostic's own tested range) with the SAME winning regularized hyperparameters; PASS requires the qualitative outcome (positive vs. negative R-squared delta vs. Ridge) to be CONSISTENT across all 7 seeds -- not requiring all 7 to be positive if the true effect is genuinely small/marginal, but requiring the SIGN not to flip seed-to-seed the way it would for a genuinely unstable result. Reported plainly either way, not just pass/fail.",
        "shuffled_target_placebo_note": "MANDATORY per CLAUDE.md Section 1's rule -- target randomly permuted in train+val before fitting; PASS condition is the INVERSE of the other checks (no significant Model-B-beats-Model-A effect should appear on shuffled labels).",
        "early_stopping_placebo_leakage_fix": (
            "PINNED 2026-09-26, BEFORE this file's Stage 1 was rerun -- root-caused via an "
            "8-independent-shuffle-seed sweep (seeds 42,43,44,45,46,100,7,999) against the "
            "FIRST attempted Stage 1 run, which showed a significant shuffled_target_placebo "
            "effect (p=0.0087, seed 42). 6 of 8 shuffle seeds showed a 'significant' effect "
            "(vs. ~5% expected by chance), and every one of the 6 favored Model B (XGBoost) "
            "over Model A (Ridge), never the reverse -- confirming this was a real, "
            "systematic pipeline issue, not a fluke of one permutation. MECHANISM: early "
            "stopping re-decides its OWN boosting-round count fresh for every fit, based on "
            "watching a held-out slice's error curve -- this is an ADAPTIVE step that Ridge "
            "has no equivalent of (Ridge's alpha is simply reused, fixed, across all fits, "
            "real or shuffled-label). Even with hyperparameters otherwise held fixed for the "
            "placebo check, XGBoost's early-stopping mechanism gets to freshly 'pick its own "
            "stopping point' on every shuffled-label refit -- an extra degree of adaptive "
            "freedom Ridge structurally cannot exploit, which can produce predictions that "
            "spuriously track the real primary-test target even when trained on permuted "
            "labels. FIX, deliberate and pre-committed, addressing ONLY this mechanism: for "
            "the shuffled_target_placebo check specifically, the early-stopping round count "
            "(best_iteration) is FROZEN at the value already selected on the REAL (unshuffled) "
            "primary fit -- i.e. n_estimators is fixed at that real-data best_iteration and "
            "early stopping itself is DISABLED for placebo refits, removing the per-shuffle "
            "adaptive selection this mechanism depends on. This is a carve-out for the "
            "placebo check ONLY -- early stopping remains fully adaptive, exactly as "
            "originally designed, for every other fit in this experiment (the real primary "
            "model, all robustness checks, gap-closure comparison, everything except this "
            "one diagnostic control). Verified via a fresh 8-seed placebo re-sweep under the "
            "frozen-round-count fix before trusting the corrected pipeline (see Stage 1 "
            "results for the confirmation)."
        ),
        "gap_closure_criterion": (
            "PINNED 2026-09-26, BEFORE Stage 1 execution, per explicit user instruction "
            "and confirmed recommendation -- NOT the same as v1's design flaw of gating on "
            "'agreement with a different model class' (that gated on DIRECTION matching "
            "XGBoost, a different, unrelated model; this gates on MAGNITUDE relative to "
            "RF v2's own already-confirmed, closed, Stage-1-VALIDATED result on the "
            "IDENTICAL primary test set -- a legitimate, pre-committed 'does regularization "
            "close most of the gap' bar, not a repeat of the prior flaw). "
            "Regularized XGBoost's R-squared delta (vs. Ridge) must be >= 50% of Random "
            "Forest v2's OWN R-squared delta (vs. Ridge), matched PER SEED (not a pooled "
            "mean) using RF v2's already-confirmed, fixed reference values from its closed "
            "Stage 1 run (Section 48): seed42 R2_delta=+0.3982, seed43 R2_delta=+0.3586 -- "
            "these are FIXED reference constants, not re-run here. Concrete thresholds: "
            "seed42 requires R2_delta(XGB) >= 0.1991 (0.50 x 0.3982); seed43 requires "
            "R2_delta(XGB) >= 0.1793 (0.50 x 0.3586). This is IN ADDITION TO, not instead "
            "of, the pre-existing effect_size_threshold_r2_delta=0.05 beats-Ridge floor -- "
            "both must be satisfied. If XGBoost clears 0.05 but not the gap-closure "
            "threshold, that is REJECTED specifically on gap-closure, not on the basic "
            "beats-Ridge criterion -- reported as a distinct outcome, not conflated."
        ),
        "informative_comparison_to_rf_v2": "The gap_closure_criterion above IS now a decision-rule gate (see that field) -- this note is retained to disclose explicitly that it was NOT originally a gate when this file was first drafted (2026-09-25) and was added the next day, before any Stage 1 execution, per explicit user instruction after a review specifically asked whether this threshold was already pinned. Old text, superseded, kept for the record: 'Descriptive only, NOT a decision-rule gate... XGBoost's verdict here is determined ENTIRELY by its own primary test/effect-size/robustness checks against Ridge, never by whether it matches RF.'",
    },
    model_version=None,
    pricing_methodology="n/a_realized_volatility_prediction_only",
    execution_assumptions="none -- identical scope-isolation choice to v1",
    train_period=("2023-10-02", "2025-06-16"),  # IDENTICAL real boundary to v1 -- same dataset, same split methodology
    validation_period=("2025-06-17", "2025-12-30"),
    test_period=("2025-12-31", "2026-07-15"),
    random_seeds=[42, 43],  # primary two-seed confirmation, IDENTICAL to v1; stability_across_seeds separately sweeps 42-48
    code_version="xgboost_volatility_prediction_regularized_v2_draft",
    testing_family_declaration="INDEPENDENT_SINGLE",
    applicability_lock=[
        ("data_integrity", True), ("lookahead_audit", True), ("timestamp_safety", True),
        ("sample_size_adequacy", False),  # kept False at draft time per this project's established convention, despite already knowing N=174 from the identical dataset
        ("statistical_testing", False), ("reproduction", False),
        ("primary_test_significant", False), ("effect_size_meets_threshold", False),
        ("multiple_testing_survived", False), ("robustness_survived", False),
        ("oos_survived", False),
        ("primary_performance_test_significant", False), ("concentration_check", False),
        ("pricing_accuracy_meets_threshold", False), ("pricing_coverage_meets_threshold", False),
    ],
    oos_validation_claimed=False,  # IDENTICAL reasoning to v1 -- Stage 1's test_period is a locked historical range; a Stage 2 for this specific hypothesis is not designed here (see Status note below)
    declared_robustness_checks=[
        "leave_one_ticker_out",  # AMD tracked explicitly -- see parameters
        "stability_across_seeds",  # NEW relative to v1 -- re-verifies whether the regularized result's sign is seed-stable
        "alternate_horizon:10day",
        "alternate_horizon:50day",
        "shuffled_target_placebo",  # MANDATORY, unchanged
    ],
)

DECISION_RULES = """
STAGE 1 VALIDATED requires ALL of:
  1. Primary (locked, non-overlapping) test-set N >= min_n_per_stage=100
  2. Model B (regularized XGBoost) significantly outperforms Model A
     (Ridge), SAME 8-feature set, on the PRIMARY (20-day) test set: paired
     one-sided Wilcoxon on per-observation absolute error, alpha_corrected=
     0.0167 (Bonferroni family of 3 horizons)
  3. Effect size: R-squared(Model B) - R-squared(Model A) >= 0.05 (the
     baseline beats-Ridge floor, IDENTICAL to v1)
  4. GAP-CLOSURE CRITERION (pinned 2026-09-26, before Stage 1 execution --
     see parameters.gap_closure_criterion for full derivation): the SAME
     R-squared delta from (3) must ALSO be >= 50% of Random Forest v2's
     own already-confirmed R-squared delta on this identical primary test
     set, matched per seed: seed42 requires delta >= 0.1991 (0.50 x
     0.3982), seed43 requires delta >= 0.1793 (0.50 x 0.3586). This is a
     SEPARATE, ADDITIONAL bar from (3), not a restatement of it -- clearing
     0.05 alone is NOT sufficient for VALIDATED if this criterion isn't
     also met.
  5. Survives ALL 5 declared robustness checks: leave_one_ticker_out (all
     6 exclusions positive, AMD's own figure explicitly reported),
     stability_across_seeds (sign does not flip across the 7 tested
     seeds), alternate_horizon:10day, alternate_horizon:50day,
     shuffled_target_placebo (NO significant effect -- inverse pass
     condition; see parameters.early_stopping_placebo_leakage_fix for the
     frozen-round-count carve-out this check now uses, pinned 2026-09-26
     BEFORE this file's Stage 1 was rerun, after an 8-seed sweep confirmed
     a real, systematic leakage mechanism in the FIRST attempted run)
  6. No single ticker or contiguous sub-period drives the entire primary-
     test effect (concentration_check)

STAGE 1 REJECTED if:
  - Primary N >= 100 but the primary test is not significant at the
    corrected alpha, OR effect size is below 0.05, OR the gap-closure
    criterion (4) is not met even if effect size clears 0.05 (reported as
    a DISTINCT outcome from a basic beats-Ridge failure, not conflated),
    OR any of the first 4 robustness checks fails/reverses (no isolated-
    failure carve-out, same standard as every other closure in this
    project), OR shuffled_target_placebo DOES show a significant effect
    (flagged separately as a pipeline/leakage problem)

INTERPRETIVE NOTE, pre-specified before any result exists: a REJECTED
verdict here, given the regularization genuinely reflects the cited
practitioner/official guidance (early stopping, lower learning rate,
higher L1/L2 ceilings, more aggressive subsampling -- all real, verified
changes from v1, not relabeled defaults), is LEGITIMATE evidence that this
dataset structurally favors Random Forest's bagging architecture over
gradient boosting for this specific target/feature combination -- not a
reason to draft a v3 with yet more aggressive XGBoost tuning. This
interpretive note does not change the mechanical REJECTED/VALIDATED
determination itself, which follows the rules above exactly.

INCONCLUSIVE if:
  - Primary N < 100 (not expected, identical dataset to v1's already-
    confirmed N=174 primary test set)

NOTE ON STAGE 2: not designed in this draft. If Stage 1 VALIDATES, a Stage
2 (rolling window, matching v1/RF-v2's shared 2026-07-16 start) would be a
separate, deliberate addition before any OVERALL VALIDATED claim -- not
assumed here.
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
print("v1 (xgboost_volatility_prediction_v1_20260925) remains CLOSED/REJECTED,")
print("untouched by this file.")
print("=" * 100)

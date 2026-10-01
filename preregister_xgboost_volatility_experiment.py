from dotenv import load_dotenv
load_dotenv()

"""
DRAFT pre-registration for a XGBoost-vs-linear-baseline volatility-
prediction hypothesis -- a NEW, STANDALONE experiment, scoped 2026-09-25.

THIS IS NOT A CONTINUATION OR RETUNE OF preregister_xgboost_interaction_
experiment.py. That hypothesis (three named win/loss-predictive feature
interactions) is CLOSED, REJECTED (CLAUDE.md Section 44) -- genuine signal
failure, confirmed via a clean shuffled-target placebo showing the real
effect sat inside the noise band. This file does not reuse its dataset,
its target, its feature set, or its hash. Different hypothesis, own hash.

THIS FILE CONSTRUCTS AND PRINTS THE CONFIG FOR REVIEW ONLY. IT DOES NOT
CALL preregister_experiment() OR run_experiment() ANYWHERE.

WHY THIS TARGET, NOT ANOTHER WIN/LOSS PREDICTION: three separate modeling
attempts on a win/loss (or directional-return) target have now failed in
this project -- V1's raw entry signal (Phase 6, Section 5), ML Experiment
1's Feature Factory + Ridge (Section 5/18, REJECTED), and the XGBoost
interaction experiment (Section 44, REJECTED). The ONE target class this
project has found a real, robust, pre-registered-and-surviving signal in
is FORWARD REALIZED VOLATILITY -- iv_term_structure_slope_v1_20260921
(Section 33): Stage 1 correlation -0.282 to -0.310 across 4 of 5
robustness-check variants, p=0.001-0.002, all significant at the
Bonferroni-corrected threshold. This experiment targets that same
demonstrated-tractable target class, with a richer feature set and a
nonlinear model, rather than another attempt at the demonstrated-hard
directional/win-loss class.

EXPLICIT NON-INTERFERENCE CONSTRAINT, stated here because it matters:
this experiment does NOT touch, read from, or write to
iv_term_structure_slope_v1_20260921's own Stage 2 rolling-accumulation
pipeline (CLAUDE.md Section 33 -- the data-existence-only stop rule, the
N>=100 threshold check, or prospective_gex_validation.db). This is a
fully separate hypothesis, separate dataset build (a new script, not yet
written), separate SQLite database, and separate hash. The only thing
reused from that experiment is its ALREADY-VALIDATED term-structure-slope
feature DEFINITION (bucket DTEs, expiration-selection convention,
matched-strike tiebreak, realized-volatility formula) -- reused for
apples-to-apples comparability of the target/methodology, not a shared
pipeline or shared accumulating dataset.

===========================================================================
FEATURE-DEPTH VERIFICATION, PERFORMED 2026-09-25 BEFORE LOCKING THE
DESIGN -- NOT ASSUMED FROM ANY PRIOR SESSION'S PARTIAL CHECK:
===========================================================================

1. GEX metrics (gex_data_cache.db:gex_metrics) -- queried fresh, all 7
   tickers (6 project tickers + SPY): uniformly 2026-06-10 to 2026-09-23,
   ~72-73 distinct dates, ~3.5 months. Confirms CLAUDE.md Section 40's
   already-documented TRAIN_START constant -- this has NOT grown to cover
   the ~3-year window the other candidate features support.

2. Term-structure slope (near[7-16 DTE]/far[30-45 DTE] IV buckets, id-
   date-safe, real EODHD `volatility` field) -- spot-checked at
   2023-10-02 (the already-confirmed EODHD depth cliff, Section 44),
   2024-06-03, and 2025-06-02, all 6 tickers, single-page queries (NOT
   the full paginated fetch -- a real caveat, noted below). Broadly
   feasible at every date/ticker sampled EXCEPT NVDA and MSTR both showed
   near=0 at 2024-06-03 specifically (0 real expirations in the 7-16 DTE
   window that day for those two tickers on a single-page query). This
   experiment's actual Stage-1 data-generation pass MUST use the full,
   already-validated paginated fetch method (same as
   gex_data_loader.py:_fetch_raw_chain_paginated or the query construction
   IV term structure's own Stage 1 run used, which achieved 536-540 raw
   observations over a much shorter ~5-month window) -- not assumed
   resolved by this spot check alone; some ticker-days will legitimately
   have no valid near-bucket expiration and must be EXCLUDED, never
   substituted, consistent with this project's established rule.

3. OI skew (nonzero open_interest, both call and put, near-money) --
   same 3 spot-check dates, all 6 tickers: robustly populated throughout,
   hundreds of contracts per side per ticker-date at every point sampled,
   extending Section 37's existing 2026-06/2026-09 confirmation back to
   2023-10-02. No coverage gap found.

DECISION, EXPLICITLY DOCUMENTED PER INSTRUCTION -- GEX FEATURES ARE
DROPPED FROM THIS EXPERIMENT'S DESIGN. Including them would shrink the
usable window from ~3 years to ~3.5 months (an ~89% reduction), for a
class of feature whose OWN standalone predictive value for this exact
target (forward realized volatility) has ALREADY been formally tested and
found insufficient -- net_gamma_regime (Section 42, REJECTED: correct
direction throughout, but effect ratio 1.167x < the 1.20x threshold and
not significant at the corrected alpha, only 18 distinct negative-regime
days available). Paying an ~89% N reduction for a feature class that has
not demonstrated its own value on this target is a bad trade, especially
for a regression problem where more N directly improves power. Term
structure, OI skew, and real-IV Greeks all confirmed feasible back to
2023-10-02 -- that is the window this experiment uses.
"""

from experiment_config import ExperimentConfig

NOTES = (
    "PRE-REGISTRATION DRAFT, not yet submitted. Standalone, NOT a retune of "
    "the closed/REJECTED xgboost_feature_interactions_v1_20260924 (Section 44). "
    "Targets forward realized volatility -- the one target class this project "
    "has found real signal in (iv_term_structure_slope_v1_20260921, Section 33) "
    "-- rather than win/loss, which has now failed 3 separate modeling attempts "
    "(V1 raw signal / Phase 6, ML Experiment 1 Feature Factory+Ridge, XGBoost "
    "interactions). GEX features explicitly EXCLUDED from this design -- see "
    "the feature-depth verification above: gex_metrics only covers ~3.5 months "
    "(2026-06-10 to present) vs. term-structure/OI-skew/Greeks' confirmed "
    "~3-year depth (2023-10-02 to present), and net_gamma_regime (the one "
    "formal test of GEX's own standalone value for THIS target) was already "
    "REJECTED -- not worth an 89% N reduction for an unproven feature class. "
    "Model A (baseline) = Ridge regression, NOT plain OLS -- chosen because "
    "the feature set includes multiple genuinely correlated inputs (e.g. "
    "gamma/vega naturally co-move with moneyness/DTE-driven quantities, and "
    "trailing realized vol correlates with several Greeks), and plain OLS is "
    "unstable under multicollinearity in a way that would make Model A an "
    "unfairly weak baseline; Ridge keeps the comparison LINEAR (the actual "
    "variable under test is nonlinearity, isolated by holding the feature set "
    "and problem type constant between A and B) while giving the baseline a "
    "fair, real chance. Model B = XGBoost regression, same feature set, same "
    "regularization discipline as the interaction experiment "
    "(max_depth<=3, min_child_weight>=5, nonzero L1/L2, subsample/"
    "colsample_bytree<=0.8, tuned via nested CV on train+val only). "
    "Primary test statistic: paired one-sided Wilcoxon signed-rank on "
    "per-observation ABSOLUTE error (not squared) -- chosen because squared "
    "error would let a small number of extreme volatility-spike days "
    "(plausible over a 3-year window) dominate the test; absolute error is "
    "more robust to those outliers and directly interpretable in the same "
    "units as realized volatility itself. Effect-size floor: R-squared(B) - "
    "R-squared(A) >= 0.05 on the primary (20-day) horizon's primary test set "
    "-- the regression analog of the interaction experiment's own AUC-delta "
    "convention (also 0.05), reused for consistency across this project's "
    "ML-track effect-size thresholds, not a newly-invented number. "
    "Primary test-set construction: LOCKED, non-overlapping, same mechanism "
    "as ml_experiment1_final_executor.py / the XGBoost interaction "
    "experiment (first observation per (ticker, ISO calendar week) within "
    "the chronological test split) -- NOT IV term structure's own day-"
    "clustered Monte Carlo permutation design; this experiment explicitly "
    "uses the locked-primary-test-set pattern instead, per its own design "
    "requirement. "
    "declared_robustness_checks mandatory going forward per CLAUDE.md "
    "Section 1's new rule (added 2026-09-25, prompted by this exact "
    "session's finding): shuffled_target_placebo is REQUIRED for any ML-"
    "track experiment comparing a richer/nonlinear model to a simpler "
    "baseline. Also includes leave_one_ticker_out, alternate_model:"
    "random_forest, and both secondary horizons (10-day, 50-day) as "
    "robustness checks, matching this project's established 5-check "
    "family-size convention. "
    "Term-structure-slope feature DEFINITION reused verbatim from "
    "iv_term_structure_slope_v1_20260921 for comparability (near[7-16 DTE]/"
    "far[30-45 DTE] buckets, soonest-near/latest-far expiration selection, "
    "median-of-common-strikes tiebreak, standard annualized-stdev-of-daily-"
    "log-returns realized-vol formula, same [10,20,50]-bar horizon set, "
    "same Bonferroni family size 3 / alpha_corrected=0.0167) -- this is "
    "feature-definition reuse only, NOT shared data/pipeline/accumulation "
    "with that experiment's own Stage 2 (see the non-interference "
    "constraint above)."
)

config = ExperimentConfig(
    experiment_id="xgboost_volatility_prediction_v1_20260925",
    experiment_type="signal_research",
    hypothesis=(
        "Among a richer feature set (IV term-structure slope, OI skew, real-IV-based "
        "Greeks, and trailing realized volatility) computed daily per ticker, XGBoost -- "
        "an interaction-aware, nonlinear model -- predicts forward realized volatility "
        "with lower error than a Ridge linear regression using the SAME feature set. "
        "This isolates NONLINEARITY as the tested variable (both models see identical "
        "inputs) -- it does not test 'more features helps' or 'XGBoost beats a single-"
        "feature baseline,' either of which would conflate feature richness with model "
        "class and reintroduce the exact ambiguity the interaction experiment's design "
        "was built to avoid."
    ),
    research_question=(
        "Does a nonlinear, tree-based model (XGBoost) meaningfully outperform a linear "
        "model (Ridge) with an IDENTICAL feature set at predicting forward realized "
        "volatility for this project's 6-ticker universe -- and does that advantage, if "
        "any, hold under a second independent model class (Random Forest), survive a "
        "shuffled-target leakage check, and generalize across tickers and horizons?"
    ),
    dataset_version="xgboost_volatility_v1_20231002_present_6ticker_new_generation_pass",
    date_range=("2023-10-02", "2026-09-25"),  # confirmed EODHD options-data floor (term structure/OI/Greeks all verified feasible back to this date, this pass); re-verify the end date against EODHD/Alpaca's actual current extent immediately before the new data-generation pass runs, same discipline as every other growing-window experiment in this project
    universe=["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"],  # GEX metrics (which would include SPY-relevant infra) explicitly excluded from this design -- see the depth-tradeoff decision above; SPY itself is not part of this experiment's universe
    option_type="call",  # matches this project's established calls-only convention for matched-strike term-structure/Greeks work
    features_used=[
        ("term_structure_slope_pct", "1.0"),
        ("oi_skew", "1.0"),
        ("trailing_realized_vol_20d", "1.0"),
        ("delta", "1.0"), ("gamma", "1.0"), ("theta", "1.0"), ("charm", "1.0"), ("vega_per_1pct_iv", "1.0"),
    ],
    parameters={
        "target_metric": "realized_volatility_forward_20d",
        "target_definition": "standard annualized stdev of daily log returns over the FORWARD window -- reused verbatim from iv_term_structure_slope_v1_20260921's realized_volatility_formula, not redefined",
        "target_horizons_bars": [10, 20, 50],
        "primary_horizon_bars": 20,
        "secondary_horizons_bars": [10, 50],
        "population": "one observation per (ticker, trading day) -- day-level, UNCONDITIONAL on V1's entry gate, matching iv_term_structure_slope_v1_20260921's own established scope-note reasoning: this is a market-structure/volatility-prediction question, not a directional-entry-conditional one",
        "term_structure_feature_definition": "REUSED VERBATIM from iv_term_structure_slope_v1_20260921: near_bucket_dte=[7,16], far_bucket_dte=[30,45], slope=far_IV-near_IV at the matched strike (median of common-strike intersection, sorted(common)[len//2] tiebreak), NEAR=soonest expiration in bucket, FAR=latest expiration in bucket (widest-spread convention), id-date-safe throughout, exclude (never substitute) when no common strike or no valid near/far expiration exists that day",
        "oi_skew_feature_definition": "REUSED from the strike-positioning pre-registration's already-scoped definition (Section 37/39): log(total_put_OI / total_call_OI), strikes within +/-10% of spot, summed across all expirations in a 7-45 DTE window, id-date-safe, nonzero-OI required both sides",
        "trailing_realized_vol_20d_definition": "same annualized-stdev-of-daily-log-returns formula as the target, computed on the PRECEDING 20 trading days (backward-looking, contemporaneous with the observation date) -- included because excluding a well-known, trivially-available, legitimate lagged-volatility predictor ('vol clusters') would make Model A/B both artificially weak and would understate what a real baseline forecaster would use; NOT the target itself, no lookahead",
        "greeks_definition": "delta/gamma/theta/charm/vega_per_1pct_iv computed via options_pricing.py's already-validated Black-Scholes formulas, using REAL historical EODHD IV (v2_iv_pricing_model.py's methodology, id-date-safe, T-1-safe) at the SAME near-bucket matched-strike call contract already being fetched for the term-structure feature -- a natural, already-determined choice, not a new/separate contract-selection rule",
        "gex_features_excluded": "EXPLICIT DECISION, see the feature-depth verification above -- gex_metrics only covers ~3.5 months (2026-06-10 to present) vs. this experiment's confirmed ~3-year window for every other feature; including GEX would cost an ~89% reduction in N for a feature class whose own standalone predictive value for this exact target was already formally tested and REJECTED (net_gamma_regime, Section 42)",
        "data_generation_source": "NEW script required (not written here, construction/hashing only) -- computes all 8 features + the target per (ticker, trading day) over the confirmed 2023-10-02-to-present window, reusing v2_iv_pricing_model.py/options_pricing.py/the term-structure and OI-skew query patterns already validated elsewhere in this project, unmodified. Saves to a NEW, separate SQLite database -- does not touch ml_xgboost_interaction_data.db, ml_training_data.db, or any IV-term-structure/GEX database.",
        "model_a_primary": "Ridge regression on the full 8-feature set (see NOTES for why Ridge, not plain OLS, was chosen as the linear baseline)",
        "model_b_primary": "XGBoost regression on the SAME full 8-feature set -- identical inputs to Model A, isolating nonlinearity as the only varied factor",
        "xgboost_regularization": "NOT default hyperparameters -- max_depth capped at 3, min_child_weight>=5, L1 (reg_alpha) and L2 (reg_lambda) both nonzero and tuned via nested CV, subsample and colsample_bytree both <=0.8 -- same regularization family as the interaction experiment, same rationale (modest dataset, fight overfitting by design)",
        "cross_validation": "NESTED cross-validation on the TRAIN+VALIDATION portion only (chronological, purged, TimeSeriesSplit-based inner loop for hyperparameter search) -- test period never touches hyperparameter selection at any point, same discipline as the interaction experiment",
        "primary_test": "paired_wilcoxon_on_per_observation_absolute_error",  # see NOTES for why absolute, not squared, error
        "primary_significance_alpha_uncorrected": 0.05,
        "bonferroni_family_size": 3,  # 3 horizons (10/20/50-day), reused from iv_term_structure_slope_v1_20260921's convention
        "primary_significance_alpha_corrected": 0.0167,  # 0.05 / 3
        "effect_size_threshold_r2_delta": 0.05,  # R-squared(B) - R-squared(A) on the primary test set -- the regression analog of the interaction experiment's AUC-delta=0.05 convention
        "min_n_per_stage": 100,  # matching this project's family-wide floor
        "primary_test_set_construction": "LOCKED, non-overlapping primary test set, same discipline as ml_experiment1_final_executor.py / the XGBoost interaction experiment -- NOT IV term structure's own day-clustered Monte Carlo design. Mechanism: chronological train(60%)/validation(20%)/test(20%) split by trading date (purged, by REAL day-count once known, not a calendar placeholder), then within the test-period pool the PRIMARY test uses the first qualifying observation per (ticker, ISO calendar week). Full untinned test set reported descriptively only.",
        "robustness_model_choice": "Random Forest -- same rationale as the interaction experiment (no CatBoost precedent anywhere in this codebase, scikit-learn already a light, standard dependency)",
        "shuffled_target_placebo_note": "MANDATORY per CLAUDE.md Section 1's rule (added 2026-09-25) -- target (forward realized vol) randomly permuted in train+val before fitting both models; PASS condition is the INVERSE of the other checks: no significant Model-B-beats-Model-A effect should appear on shuffled labels. If it does, that flags a pipeline/leakage problem, not a real finding, per this project's established asymmetric-check-interpretation discipline (CLAUDE.md Section 33's 50-day-horizon precedent).",
    },
    model_version=None,
    pricing_methodology="n/a_realized_volatility_prediction_only",  # predicts realized volatility of the underlying, not option P&L -- same isolation choice as iv_term_structure_slope_v1_20260921 and the GEX net-gamma-regime experiment
    execution_assumptions="none -- this experiment does not touch option pricing, spread, sizing, or execution; a validated volatility-prediction edge would need a separate follow-on experiment to translate into an actual trading rule",
    train_period=("2023-10-02", "2025-06-30"),  # ~60% of the confirmed window, PLACEHOLDER split point pending the actual joined observation count from the new data-generation pass -- re-verify and adjust proportionally once real N is known, same disclosed-placeholder discipline as the interaction experiment (do not silently keep this literal if it no longer reflects a genuine 60/20/20 split)
    validation_period=("2025-07-01", "2026-02-28"),  # ~20%, same placeholder caveat
    test_period=("2026-03-01", "2026-09-25"),  # ~20%, same placeholder caveat -- a LOCKED historical range (not rolling/prospective), matching the interaction experiment's own test_period design, not IV term structure's rolling Stage 2 pattern; oos_validation_claimed is False below since chronological holdout on already-existing historical data is not genuine prospective replication
    random_seeds=[42, 43],  # matches this project's established seed pair throughout
    code_version="xgboost_volatility_prediction_v1_draft",
    testing_family_declaration="INDEPENDENT_SINGLE",
    applicability_lock=[
        ("data_integrity", True), ("lookahead_audit", True), ("timestamp_safety", True),
        ("sample_size_adequacy", False),  # UNKNOWN until the new data-generation pass actually runs
        ("statistical_testing", False), ("reproduction", False),
        ("primary_test_significant", False), ("effect_size_meets_threshold", False),
        ("multiple_testing_survived", False), ("robustness_survived", False),
        ("oos_survived", False),
        ("primary_performance_test_significant", False), ("concentration_check", False),
        ("pricing_accuracy_meets_threshold", False), ("pricing_coverage_meets_threshold", False),
    ],
    oos_validation_claimed=False,  # chronological holdout on already-existing historical data, not genuine prospective replication -- matching this project's precise use of the term elsewhere
    declared_robustness_checks=[
        "shuffled_target_placebo",  # MANDATORY, see parameters note and CLAUDE.md Section 1's new rule
        "leave_one_ticker_out",
        "alternate_model:random_forest",
        "alternate_horizon:10day",
        "alternate_horizon:50day",
    ],
)

DECISION_RULES = """
VALIDATED requires ALL of:
  1. Primary (locked, non-overlapping) test-set N >= min_n_per_stage=100
     -- confirmed empirically once the new data-generation pass runs
  2. Model B (XGBoost) significantly outperforms Model A (Ridge), SAME
     8-feature set, on the PRIMARY (20-day) test set: paired one-sided
     Wilcoxon on per-observation absolute error, alpha_corrected=0.0167
     (Bonferroni family of 3 horizons)
  3. Effect size: R-squared(Model B) - R-squared(Model A) >= 0.05 on the
     primary test set
  4. Survives ALL 5 declared robustness checks in the same direction:
     shuffled_target_placebo shows NO significant effect (inverse pass
     condition, stated explicitly to avoid interpretation ambiguity),
     leave_one_ticker_out, alternate_model:random_forest,
     alternate_horizon:10day, alternate_horizon:50day
  5. No single ticker or contiguous sub-period drives the entire primary-
     test effect (concentration_check, same discipline as the interaction
     experiment / Phase 7)

REJECTED if:
  - Primary N >= 100 but the primary test is not significant at the
    corrected alpha, OR effect size (R-squared delta) is below 0.05, OR
    the direction reverses under any of the first four robustness checks,
    OR the shuffled_target_placebo DOES show a significant effect
    (flagged separately as a pipeline/leakage problem, not a clean
    rejection of the hypothesis itself, per this project's established
    convention)

INCONCLUSIVE if:
  - Primary N < 100 after the new data-generation pass
  - Model A and Model B disagree in direction across robustness checks
    without a clear majority, or the concentration_check finds the
    result is driven by a single ticker/sub-period in a way that isn't
    itself a clean robustness-check failure but undercuts confidence in
    generalizability
"""

print("=" * 100)
print("DRAFT CONFIG -- FOR REVIEW, NOT YET PREREGISTERED")
print("=" * 100)
print("experiment_id: " + config.experiment_id)
print("experiment_type: " + config.experiment_type)
print("hypothesis: " + config.hypothesis)
print("research_question: " + config.research_question)
print("universe: " + str(config.universe))
print("date_range: " + str(config.date_range))
print("train_period: " + str(config.train_period))
print("validation_period: " + str(config.validation_period))
print("test_period: " + str(config.test_period))
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
print("running the new data-generation pass + Stage 1, are separate, deliberate")
print("future steps. NO DATA TOUCHED beyond the empirical data-depth queries above.")
print("=" * 100)

from dotenv import load_dotenv
load_dotenv()

"""
DRAFT pre-registration for a genuinely NEW, standalone ML forward-realized-
volatility hypothesis, scoped 2026-09-29. NOT a reopening, retune, or
extension of RF v1/v2, XGBoost v1, or regularized XGBoost v2 -- all four
stay exactly as closed (CLAUDE.md Section 58). This is the first experiment
in this project's ML-volatility track to use: (a) the full 59-ticker
broader universe (existing 6 + all 53 candidates that passed feasibility,
broader_universe_feasibility_report.md), (b) Target C -- relative-to-own-
history, structurally removing the ticker-mean-memorization confound
Section 58 found rather than merely controlling for it after the fact, and
(c) a genuine K=4 expanding-window walk-forward design inside Stage 1,
rather than a single static train/val/test split.

THIS FILE CONSTRUCTS AND PRINTS THE CONFIG FOR REVIEW ONLY. IT DOES NOT
CALL preregister_experiment() OR run_experiment() ANYWHERE. NO DATA HAS
BEEN TOUCHED BY THIS FILE.

===========================================================================
DESIGN LINEAGE (Steps 1-4, all already reviewed and approved before this
file was written):
===========================================================================
Step 1 (broader_universe_feasibility_report.md): 59-ticker universe
  confirmed feasible; a real 3-day Alpaca IEX-feed gap (44/53 candidates)
  and a DIS single-stray-bar anomaly were both investigated and resolved
  as NOT affecting the 2023-10-02+ research window.
Step 2 (target_design_comparison_v1.md): Target C (relative-to-own-
  history) approved over cross-sectional rank/z-score, specifically because
  it structurally removes Section 58's ticker-memorization confound, is
  outlier-safer than a cross-sectional z-score given this project's history
  of split-contamination incidents, and maps directly onto existing single-
  ticker execution infrastructure (unlike a cross-sectional/dispersion
  target, which this project cannot currently trade). Cross-sectional rank
  (Target A) is explicitly preserved as a separate, legitimate future
  hypothesis, not chased here.
Steps 3-4 (target_c_baseline_and_walkforward_design_v1.md): ticker-identity
  baseline design and walk-forward validation design, both approved subject
  to three conditions, all resolved before this file was written (see
  preregistration_prep_resolution_v1.md):
    1. The 7 IPO-limited tickers (ARM/RIVN/LCID/SOFI/COIN/PLTR/AFRM) were
       checked directly against live EODHD data and confirmed to have NO
       later depth cliff than the shared 2023-10-02 date (substantial
       populated records at the cliff itself for all 7, plus 100%
       population across a 28-date density sample in the critical first
       126-trading-day window) -- no special eligibility rule needed.
    2. Real fold boundary dates were computed against the live SPY trading
       calendar (get_real_trading_days), not placeholders -- see
       parameters.fold_structure below for the exact, verified dates.
    3. Stage 2 automation was built ALONGSIDE Stage 1, not after --
       generate_broader_universe_volatility_dataset.py and the
       BroaderUniverse_Volatility_Nightly_Update scheduled task (20:30 ET
       daily) are both already registered and running as of 2026-09-29,
       specifically to avoid the multi-month Stage-2 stall RF v2 suffered
       (CLAUDE.md Section 52).
"""

from experiment_config import ExperimentConfig

FULL_59_TICKER_UNIVERSE = [
    "AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR",
    "MSFT", "GOOGL", "AMZN", "META", "AVGO", "INTC", "MU", "QCOM", "TXN", "LRCX", "AMAT", "ASML", "ARM",
    "F", "GM", "RIVN", "LCID", "NIO",
    "WMT", "COST", "TGT", "NKE", "SBUX", "MCD", "HD", "DIS",
    "JPM", "BAC", "GS", "MS", "V", "MA", "PYPL", "SOFI",
    "UNH", "JNJ", "PFE", "LLY", "MRNA",
    "XOM", "CVX", "OXY",
    "BA", "CAT", "GE",
    "COIN", "RIOT", "MARA", "PLTR", "SNAP", "ROKU", "DKNG", "AFRM",
]
assert len(FULL_59_TICKER_UNIVERSE) == 59

NOTES = (
    "MODEL CANDIDATES: Model A (baseline) = Ridge regression, the same linear "
    "baseline used throughout this project's entire ML-volatility track. Model B "
    "(candidate) = Random Forest, NOT XGBoost. This is a deliberate, disclosed "
    "choice, not an oversight: the diagnostic investigation that closed out the "
    "prior volatility-prediction line (CLAUDE.md Section 47) found XGBoost "
    "specifically prone to a harmful, noise-fitting reliance on vega/theta on "
    "this exact feature family, consistently across 7 seeds and 6 hyperparameter "
    "variants -- a documented, dataset-specific failure mode, not a generic "
    "'XGBoost is worse' claim. Random Forest's bagging architecture already "
    "showed better resistance to exactly this failure mode in every prior "
    "experiment that tested it. Repeating the XGBoost comparison here, on a "
    "target explicitly designed to remove a DIFFERENT confound (ticker-mean "
    "memorization), would not test anything new about XGBoost's already-"
    "documented problem -- so alternate_model:xgboost is DELIBERATELY NOT "
    "declared as a robustness check here, for the same reason RF v2 dropped it "
    "(CLAUDE.md Section 48): requiring agreement with a model independently "
    "shown to overfit this feature family tests THAT model's stability, not "
    "Random Forest's validity. "
    "HORIZON: 10/20/50-day forward realized volatility, primary=20-day, "
    "Bonferroni family of 3, alpha_corrected=0.0167 -- reused verbatim from the "
    "established convention across every prior experiment in this track "
    "(Sections 45/46/48/51), for direct comparability. "
    "EFFECT-SIZE FLOOR: R-squared(B) - R-squared(A) >= 0.05, reused verbatim. "
    "R-squared is scale-invariant, so this floor transfers cleanly even though "
    "Target C's absolute scale (a per-ticker-demeaned, roughly-standardized "
    "quantity) differs in character from the raw-volatility target the floor "
    "was originally set against -- no rescaling or renormalization of the "
    "threshold itself is needed. "
    "TWO MANDATORY GATES, EQUAL PRIORITY TO THE PRIMARY TEST, PER EXPLICIT "
    "INSTRUCTION -- failing either alone is sufficient for REJECTED, "
    "independent of how the primary model comparison performs: "
    "(1) ticker_identity_baseline_gate (target_c_baseline_and_walkforward_"
    "design_v1.md Section 1) -- Model B fit with the 8 real features PLUS "
    "explicit ticker one-hot dummies must show BOTH positive incremental "
    "R-squared over a per-ticker training-mean-of-target baseline AND a "
    "significant paired Wilcoxon win over that baseline, on the same locked "
    "primary test set. Kept as a mandatory gate even though Target C already "
    "structurally reduces the risk it guards against, per explicit instruction "
    "not to drop it just because the target helps structurally. "
    "(2) fold_stability_gate (target_c_baseline_and_walkforward_design_v1.md "
    "Section 2) -- Model B must beat Model A in the SAME direction in ALL 4 "
    "individual walk-forward folds, not just in the pooled result -- the "
    "walk-forward analog of leave-one-ticker-out, applied to leave-one-time-"
    "block-out instead. "
    "TARGET-C ELIGIBILITY RULE: 126-trading-day trailing lookback, >=90% "
    "(113/126) populated within that window, hard-excluded (never imputed) "
    "otherwise -- locked BEFORE this file was written, verified to interact "
    "identically with the 7 IPO-limited tickers as with the rest of the "
    "universe (see design lineage above). alternate_lookback:252day is a "
    "declared robustness check testing this specific choice. "
    "LEAVE_ONE_TICKER_OUT COST DISCLOSURE: across the full 59-ticker universe "
    "this means 59 separate refits, not 6 -- a real, larger computational cost "
    "than any prior experiment in this track, disclosed here rather than "
    "quietly reduced in scope."
)

config = ExperimentConfig(
    # HASH HISTORY: bf9fef62c5478683e552a0e4b9737c3d793bec9ce273b439a40d9c70bb8de4f6 (drafted 2026-09-29)
    #   -> 10f10a1364cd6034bc578c6807b9582a5fbe5f5912648cc71d2525f624e699cc (2026-10-01: fold_structure.purge_rule
    #   added -- train/test label-leakage purge of max(h, 20) trading days; design fix, made before registration
    #   and before any result. Not yet registered in research_database.db.)
    experiment_id="broader_universe_volatility_target_c_v1_20260929",
    experiment_type="signal_research",
    hypothesis=(
        "Random Forest predicts forward realized volatility, expressed relative to each "
        "ticker's own trailing 126-day history (Target C), with lower error than a Ridge "
        "linear regression using the IDENTICAL 8-feature set, across the full 59-ticker "
        "broader universe -- and this advantage is not merely a rediscovery of persistent "
        "per-ticker average volatility differences (the confound that invalidated every "
        "prior experiment in this track once discovered, CLAUDE.md Section 58), since the "
        "target itself is already demeaned relative to each ticker's own history and a "
        "dedicated ticker-identity gate is run as a mandatory, equal-priority check "
        "alongside the primary test."
    ),
    research_question=(
        "Does Random Forest meaningfully outperform Ridge regression, identical 8-feature "
        "set, at predicting a ticker's forward realized volatility RELATIVE TO ITS OWN "
        "recent (126-trading-day) history, across a genuinely broad (59-ticker) universe -- "
        "and does that advantage (a) survive a mandatory ticker-identity-baseline gate "
        "proving it is not ticker-mean recovery in disguise, (b) hold consistently across "
        "all 4 individual walk-forward folds, not just pooled, (c) survive a shuffled-"
        "target leakage check, (d) generalize across all 59 tickers with no single "
        "exclusion reversing the effect, (e) hold at alternate horizons and an alternate "
        "trailing-lookback specification, and (f) replicate on a genuinely separate, "
        "later, out-of-sample rolling window?"
    ),
    dataset_version="broader_universe_volatility_v1_20231002_present_59ticker_generation_in_progress_20260929",  # PROVISIONAL -- the Stage-1 historical backfill (generate_broader_universe_volatility_dataset.py) was started 2026-09-29 and is still running as of this draft (a real, disclosed, multi-hour-plus job at ~10x the original 6-ticker build's scale). A final, content-hash-qualified dataset_version (matching the "..._sha256_<prefix>" convention established in Section 56) will be appended as a documented amendment once the backfill is confirmed complete against broader_universe_volatility_dataset.db -- NOT before. This is a first-time provenance-labeling situation (an actively-generating dataset), not a data-correctness fix, so it does not fall under the Section 1 rule that fixes-without-config-edits keep their hash; establishing the INITIAL dataset_version here is itself a normal, expected part of drafting this preregistration.
    date_range=("2024-04-02", "2026-07-10"),  # Stage 1 window: real Stage1_start (126th real SPY trading day on/after the 2023-10-02 EODHD depth cliff) through real Stage1_end (today minus the largest candidate horizon [50d] minus a 5-day safety buffer, real trading days) -- both computed against the live SPY trading calendar 2026-09-29, not placeholders.
    universe=FULL_59_TICKER_UNIVERSE,
    option_type="call",
    features_used=[
        ("term_structure_slope_pct", "1.0"), ("oi_skew", "1.0"), ("trailing_realized_vol_20d", "1.0"),
        ("delta", "1.0"), ("gamma", "1.0"), ("theta", "1.0"), ("charm", "1.0"), ("vega_per_1pct_iv", "1.0"),
    ],  # IDENTICAL feature vocabulary to every prior experiment in this track, deliberately, for comparability -- this experiment's novelty is the target transform, universe size, and validation design, not a new feature set.
    parameters={
        "target_metric": "realized_volatility_forward_20d_relative_to_own_126day_trailing_history",
        "target_construction": (
            "Target C (relative-to-own-history), per target_design_comparison_v1.md Section 1: "
            "z_i,t = (raw_realized_vol_i,t - trailing_mean_i) / trailing_std_i, where trailing_mean/"
            "std are computed from ticker i's own real target_realized_vol readings over a FIXED "
            "126-trading-day calendar window strictly before t. NOT computed here yet -- this "
            "script only locks the definition; the transform is applied downstream from the raw "
            "features/targets generate_broader_universe_volatility_dataset.py already saves."
        ),
        "target_eligibility_rule": (
            "A ticker-date is eligible only if >=113 of the 126 trading days in its trailing window "
            "(>=90%) have a valid, computable raw target_realized_vol_20d reading. Below that, "
            "EXCLUDED, never imputed or substituted -- locked 2026-09-29, before any result exists, "
            "per target_c_baseline_and_walkforward_design_v1.md Section 0. Verified 2026-09-29 to "
            "interact identically with the 7 IPO-limited tickers (ARM/RIVN/LCID/SOFI/COIN/PLTR/AFRM) "
            "as with the rest of the universe -- no special rule needed for any of them."
        ),
        "target_horizons_bars": [10, 20, 50],
        "primary_horizon_bars": 20,
        "secondary_horizons_bars": [10, 50],
        "model_a_primary": "Ridge regression, full 8-feature set (standardized), tuned via nested CV on train+val only",
        "model_b_primary": "Random Forest regression, SAME 8-feature set (standardized), tuned via nested CV on train+val only, NOT default hyperparameters",
        "dropped_check_disclosure": "alternate_model:xgboost is DELIBERATELY NOT declared -- see module NOTES. Reuses RF v2's own established reasoning (CLAUDE.md Section 48): XGBoost was independently shown (Section 47) to overfit this exact feature family, so requiring agreement with it tests XGBoost's stability, not Random Forest's validity.",
        "fold_structure": {
            "stage1_start": "2024-04-02", "stage1_end": "2026-07-10",
            "n_stage1_real_trading_days": 569, "K": 4,
            "note": "5 equal blocks (~113-116 real trading days each); block 1 is Fold 1's initial training-only period, blocks 2-5 are the 4 expanding-window test blocks. All dates verified against the live SPY trading calendar 2026-09-29 (get_real_trading_days), not placeholders.",
            "folds": [
                {"fold": 1, "train": ["2024-04-02", "2024-09-11"], "test": ["2024-09-12", "2025-02-25"]},
                {"fold": 2, "train": ["2024-04-02", "2025-02-25"], "test": ["2025-02-26", "2025-08-08"]},
                {"fold": 3, "train": ["2024-04-02", "2025-08-08"], "test": ["2025-08-11", "2026-01-21"]},
                {"fold": 4, "train": ["2024-04-02", "2026-01-21"], "test": ["2026-01-22", "2026-07-10"]},
            ],
            # ADDED 2026-10-01, before this pre-registration was finalized or any result existed: the
            # original fold design had NO purge -- each test block starts the trading day after its
            # train block ends (e.g. fold 1 train ends 2024-09-11, test starts 2024-09-12). The targets
            # are FORWARD realized vols (10/20/50 trading days), so the last h training rows' labels
            # were computed from prices inside the test block -- train/test label leakage even with
            # zero shared dates. Feature lookbacks (longest: trailing_realized_vol_20d, 20 days) look
            # backward and are not themselves a leak, but the purge is sized to cover them too.
            "purge_rule": {
                "purge_trading_days": "max(h, 20), where h = forward horizon of the target being modeled (primary h=20 -> 20; alternate_horizon:10day -> 20; alternate_horizon:50day -> 50) and 20 = the longest feature lookback (trailing_realized_vol_20d, TRAILING_WINDOW=20 in generate_broader_universe_volatility_dataset.py)",
                "mechanic": "Within each fold, DROP from the training set every observation dated in the last purge_trading_days NYSE trading days before that fold's test start (equivalently: keep only training rows whose full forward-label window ends strictly before the test block begins). Test blocks and their start dates are UNCHANGED; only training sets shrink.",
                "applies_to": "the outer walk-forward folds AND the nested CV inside each fold's training data (same purge between every inner train/validation split), and the ticker_identity_baseline_gate's per-ticker training means.",
                "no_post_test_embargo_needed": "Expanding-window folds never train on data dated after their own test block, so the post-test embargo used in shuffled k-fold CV does not apply here; the pre-test purge above is the complete fix.",
            },
            "hyperparameter_tuning": "retuned independently within EACH fold's own (purged) training data via nested CV -- never informed by that fold's own test period or any later fold's data.",
            "primary_test_set_construction": "all 4 folds' test-period observations pooled FIRST, then the established per-(ticker, ISO calendar week) thinning rule applied ONCE to the pooled set -- not per-fold-then-combined, to avoid leaving near-adjacent weeks standing across a fold boundary.",
        },
        "ticker_identity_baseline_gate": {
            "status": "MANDATORY, EQUAL PRIORITY TO THE PRIMARY TEST -- not a lesser robustness check.",
            "baseline_model": "per-ticker constant = mean(Target C value) over that ticker's own training-period observations only",
            "real_model": "Model B (Random Forest) fit with the 8 real features PLUS explicit one-hot ticker dummy columns as additional inputs -- same mechanism as CLAUDE.md Section 58's analyze_ticker_fixed_effects.py",
            "pass_condition": "BOTH incremental_r2 > 0 AND a significant paired one-sided Wilcoxon win (model+dummies' absolute error < baseline's) at the same corrected alpha as the primary test, on the SAME pooled/thinned primary test set.",
            "why_not_the_0.05_floor": "That floor was calibrated for 'does a richer model meaningfully beat a simpler one' -- a different question from 'does the model add anything at all beyond ticker identity.' Section 58 showed the realistic failure mode is outright negative incremental R2, not a small positive margin, so 'provably beats it' is the correct bar here, not an additional arbitrary margin.",
        },
        "fold_stability_gate": {
            "status": "MANDATORY, EQUAL PRIORITY TO THE PRIMARY TEST.",
            "pass_condition": "Model B beats Model A (positive R2 delta) in the SAME direction in ALL 4 individual folds, evaluated on each fold's own test block, not just the pooled result.",
        },
        "primary_test": "paired_wilcoxon_on_per_observation_absolute_error",
        "primary_significance_alpha_uncorrected": 0.05,
        "bonferroni_family_size": 3,
        "primary_significance_alpha_corrected": 0.0167,
        "effect_size_threshold_r2_delta": 0.05,
        "min_n_per_stage": 100,
        "min_n_estimate_disclosure": "Not yet an exact count -- estimated order of magnitude only (pooled ~452 real test-period trading days x up to 59 tickers, thinned to one observation per ticker per ISO week, before burn-in/eligibility exclusions). Very likely comfortably above 100 but to be reconfirmed against real saved data at Stage 1 execution time, not assumed here.",
        "primary_test_set_construction": "Locked, non-overlapping: first observation per (ticker, ISO calendar week) within the POOLED (all 4 folds') test-period set.",
        "rf_regularization": "Real hyperparameter grid (max_depth, min_samples_leaf, max_features), tuned via nested CV on train+val only, matching the already-established RF grid used throughout this project's ML-volatility track.",
        "cross_validation": "Nested cross-validation on TRAIN+VALIDATION only, within each fold's own training data -- no global, cross-fold tuning. Every inner split is purged per fold_structure.purge_rule (added 2026-10-01).",
        "stage2_window_definition": (
            "Rolling, fixed start 2026-07-13 (the real next trading day after Stage1_end, 2026-07-10, "
            "verified against the live SPY calendar), open end via a data-existence check only, N>=100 "
            "lock-and-test-once. Automation ALREADY BUILT AND RUNNING as of 2026-09-29 -- "
            "generate_broader_universe_volatility_dataset.py serves as both the Stage 1 backfill and "
            "the Stage 2 accumulation mechanism at once (no separate script), and the "
            "BroaderUniverse_Volatility_Nightly_Update scheduled task (daily 20:30 ET) is registered "
            "and confirmed State=Ready -- built ALONGSIDE Stage 1, not after, per explicit instruction "
            "citing RF v2's multi-month Stage 2 stall (CLAUDE.md Section 52) as the failure mode to avoid."
        ),
        "stage2_readiness_as_of_20260929": "55 real trading days already available for Stage 2 as of today (2026-09-29) -- accumulating automatically going forward, independent of when the Stage 1 historical backfill itself completes.",
        "eodhd_ipo_ticker_depth_disclosure": "Verified 2026-09-29: all 7 IPO-limited tickers (ARM/RIVN/LCID/SOFI/COIN/PLTR/AFRM) have substantial, real, populated EODHD options data AT the shared 2023-10-02 depth cliff (200-700+ raw records each), and 100% population across a 28-date density sample spanning the critical first 126-trading-day window. No later per-ticker cliff exists in this universe; a single shared START_DATE=2023-10-02 is correct for all 59 tickers.",
    },
    model_version=None,
    pricing_methodology="n/a_realized_volatility_prediction_only",
    execution_assumptions="none -- identical scope-isolation choice to every prior experiment in this track",
    train_period=("2024-04-02", "2026-07-10"),  # overall Stage-1 span across which SOME fold's training occurs -- see parameters.fold_structure for the real, per-fold breakdown; the schema's flat 3-tuple fields cannot natively express a 4-fold walk-forward design, disclosed here rather than silently flattened without comment
    validation_period=None,  # no separate held-out validation block distinct from the folds themselves -- nested CV WITHIN each fold's own training data serves this role, per parameters.fold_structure
    test_period=("2024-09-12", "2026-07-10"),  # overall pooled span of all 4 folds' test blocks (fold 1's test start through fold 4's test end) -- the ACTUAL primary test set is the pooled, per-ticker-per-week-thinned subset of this span, not every day within it; see parameters.fold_structure
    random_seeds=[42, 43],
    code_version="broader_universe_volatility_target_c_v1_draft",
    testing_family_declaration="INDEPENDENT_SINGLE",
    applicability_lock=[
        ("data_integrity", True), ("lookahead_audit", True), ("timestamp_safety", True),
        ("sample_size_adequacy", False), ("statistical_testing", False), ("reproduction", False),
        ("primary_test_significant", False), ("effect_size_meets_threshold", False),
        ("multiple_testing_survived", False), ("robustness_survived", False),
        ("oos_survived", False),
        ("primary_performance_test_significant", False), ("concentration_check", False),
        ("pricing_accuracy_meets_threshold", False), ("pricing_coverage_meets_threshold", False),
    ],
    oos_validation_claimed=False,  # Stage 1's test_period is a locked historical (pooled walk-forward) range; genuine prospective replication is Stage 2's separate job, matching every prior experiment's convention
    declared_robustness_checks=[
        "ticker_identity_baseline_gate",  # MANDATORY, equal priority to the primary test -- see parameters
        "fold_stability_gate",  # MANDATORY, equal priority to the primary test -- see parameters
        "leave_one_ticker_out",  # across the FULL 59-ticker universe -- 59 refits, disclosed cost
        "alternate_lookback:252day",  # tests the 126-day trailing-history window choice itself
        "alternate_horizon:10day",
        "alternate_horizon:50day",
        "shuffled_target_placebo",  # MANDATORY per CLAUDE.md Section 1's rule
    ],
)

DECISION_RULES = """
STAGE 1 VALIDATED requires ALL of:
  1. Primary (pooled, locked, non-overlapping) test-set N >= min_n_per_stage=100
  2. Model B (Random Forest) significantly outperforms Model A (Ridge), SAME
     8-feature set, on the PRIMARY (20-day) pooled test set: paired one-sided
     Wilcoxon on per-observation absolute error, alpha_corrected=0.0167
     (Bonferroni family of 3 horizons)
  3. Effect size: R-squared(Model B) - R-squared(Model A) >= 0.05
  4. ticker_identity_baseline_gate PASSES (both incremental_r2 > 0 AND a
     significant paired Wilcoxon win vs. the ticker-only baseline) -- MANDATORY,
     equal priority to criteria 2-3; failing this ALONE is sufficient for
     REJECTED regardless of how criteria 2-3 perform
  5. fold_stability_gate PASSES (Model B beats Model A in the same direction in
     ALL 4 individual folds) -- MANDATORY, equal priority to criteria 2-3
  6. Survives the remaining declared robustness checks in the same direction:
     leave_one_ticker_out (all 59 exclusions positive), alternate_lookback:
     252day, alternate_horizon:10day, alternate_horizon:50day
  7. shuffled_target_placebo shows NO significant effect (inverse pass
     condition, mandatory per CLAUDE.md Section 1's rule)
  8. No single ticker or fold drives the entire primary-test effect
     (concentration_check)

STAGE 1 REJECTED if:
  - Primary N >= 100 but the primary test is not significant at the corrected
    alpha, OR effect size is below 0.05, OR ticker_identity_baseline_gate
    fails, OR fold_stability_gate fails, OR direction reverses under
    leave_one_ticker_out / alternate_lookback:252day / alternate_horizon:10day
    / alternate_horizon:50day, OR shuffled_target_placebo DOES show a
    significant effect
  - No isolated-failure carve-out -- same no-exception standard as every
    other closure in this project (RF v1, RF v2, XGBoost v1, regularized
    XGBoost v2)

OVERALL VALIDATED additionally requires:
  9. Stage 2 (rolling, fixed start 2026-07-13, open end, N>=100
     stop-and-lock via data-existence check only) replicates the same
     direction and clears the same significance/effect-size bars
     independently, including its own ticker_identity_baseline_gate and
     shuffled_target_placebo re-check

OVERALL INCONCLUSIVE if:
  - Stage 1 passes but Stage 2 has not yet reached N>=100 (CURRENT STATE as
    of 2026-09-29: 55 real trading days accumulated, growing automatically)
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
print("universe (n=" + str(len(config.universe)) + "): " + str(config.universe))
print("date_range (Stage 1): " + str(config.date_range))
print("train_period: " + str(config.train_period))
print("validation_period: " + str(config.validation_period))
print("test_period (Stage 1, pooled): " + str(config.test_period))
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
print("RF v1/v2, XGBoost v1, and regularized XGBoost v2 remain CLOSED, untouched")
print("by this file (CLAUDE.md Section 58).")
print("=" * 100)

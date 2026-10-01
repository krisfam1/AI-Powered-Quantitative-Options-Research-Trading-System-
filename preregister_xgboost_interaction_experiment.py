from dotenv import load_dotenv
load_dotenv()

"""
DRAFT pre-registration for an XGBoost feature-interaction hypothesis --
the sixth-ish formal experiment in this project (fifth GEX/IV/strike-
family experiment plus this, the second ML-track experiment after the
rejected ml_experiment1_feature_factory_vs_baseline). Scoped 2026-09-24.

THIS FILE CONSTRUCTS AND PRINTS THE CONFIG FOR REVIEW ONLY. IT DOES NOT
CALL preregister_experiment() OR run_experiment() ANYWHERE. Per explicit
instruction: construction and hashing only. Stage 1 (the actual data-
generation pass and model fit) is NOT run here -- that is a separate,
later, deliberate step, and it needs a NEW data-generation pass first
(see the data-depth section below), not reuse of the existing 573-row
ml_training_data.db (which is capped at the last 90 days only).

REAL DATA-DEPTH TEST, PERFORMED EMPIRICALLY BEFORE DESIGNING ANYTHING --
NOT ASSUMED FROM EODHD'S OWN "ROBUST TWO-YEAR HISTORY" MARKETING CLAIM:
  - EODHD options data (all 6 project tickers + SPY, id-date-safe queries
    at real trading days, checked via bisection, not a single spot-check):
    a genuine, consistent, hard cliff exists at 2023-10-02 -- confirmed
    2023-09-29 (a real Friday trading day) returns ZERO id-date-matched
    records for ALL 7 tickers tested, while 2023-10-02 (the next trading
    day) returns FULL, populated records (volatility field present) for
    all 7. This boundary is EARLIER (better) than the marketed "two
    years" -- 2023-10-02 to today (2026-09-24) is just under THREE years,
    not two. Two intermediate false alarms were caught and corrected
    during this check, not glossed over: an initial naive calendar
    bisection hit 2024-01-15 (a market holiday, MLK Day) and 2024-01-20
    (a Saturday) and misread those as depth-limit signals; both were
    recognized as ordinary non-trading-day artifacts once cross-checked
    against real weekday trading dates, not a genuine cliff.
  - Alpaca daily bars (all 6 project tickers, via the same construction
    backtest_engine.get_daily_regime() uses internally): a uniform
    2020-07-27 start across all 6 tickers, extending to 2026-09-23 (SPY
    specifically goes back further, to 2018-11-01, but SPY is not itself
    a training-data ticker here). NOT the binding constraint -- EODHD's
    options depth is, since every feature in this experiment's set
    requires options Greeks/OI, not just underlying price.
  - CONCLUSION: the real, empirically-confirmed usable window for this
    experiment is 2023-10-02 through today, ~2.97 years, across all 6
    tickers -- not the 90-day window generate_training_data.py currently
    defaults to (a self-imposed convenience default in that script, not
    a real data constraint, confirmed here). A NEW data-generation pass
    over this full window is required before Stage 1 can run; the
    existing 573-row ml_training_data.db is NOT reused.

WHY THIS IS GENUINELY DISTINCT FROM ml_experiment1_feature_factory_vs_baseline
(REJECTED), NOT A RERUN WITH A DIFFERENT MODEL CLASS BOLTED ON:
  - ML Experiment 1's LOCKED_FEATURES (confirmed by direct code read of
    ml_experiment1_executor.py, not memory): past_return_n,
    breakout_strength, atr_normalized, dte_at_index, delta_at_index,
    iv_vs_realized_vol, iv_percentile, spy_trend_state,
    relative_strength_vs_spy, vwap_distance -- predicting 20-BAR FORWARD
    RETURNS via Ridge, baseline = past_return_n alone.
  - THIS experiment's feature set (feature_extraction.py's 13 features,
    confirmed by direct code read, a COMPLETELY DIFFERENT, non-overlapping
    set from ML Experiment 1's): delta, gamma, theta, charm,
    vega_per_1pct_iv, realized_volatility, realized_vol_percentile,
    relative_volume, breakout_magnitude_score, trend_strength_score,
    momentum_score, moneyness, dte -- predicting TRADE OUTCOME (win/loss
    on the already-validated V1-style entry/exit chain), not forward
    return of the underlying.
  - Different features, different target variable, different population
    (real executed/simulated trades, not raw signal-eligible bars),
    different model class, and -- the actual hypothesis under test --
    specific NAMED pairwise interactions among this feature set, not
    "trees are generally better than linear models."
  - ML Experiment 1's REJECTED verdict is about a specific linear model
    on a specific different feature set predicting a specific different
    target. It does not, and structurally cannot, speak to whether
    THESE particular interaction terms, on THIS particular feature set
    and target, would help a tree-based model. Not reusing that
    rejection as evidence here, per this project's own Section 19
    discipline (a rejection's finding does not transfer to a different,
    non-identical hypothesis).

THREE NAMED INTERACTIONS, EACH WITH A STATED THEORETICAL REASON --
falsifiable, not "trees find interactions automatically so let's just
throw the raw features at XGBoost and see":
  1. realized_volatility x relative_volume ("high-conviction move"
     theory): realized volatility alone can be driven by a single thin,
     illiquid print: relative volume alone doesn't indicate directional
     conviction. Their JOINT elevation -- high realized movement WITH
     broad participation -- is a qualitatively different, more credible
     signal of genuine informed/institutional flow than either factor
     alone. entry_scorer.py already scores both factors, but ADDITIVELY
     (separate point contributions) -- this hypothesis is specifically
     that their PRODUCT, not their sum, carries information a linear
     combination cannot represent.
  2. gamma x moneyness ("convexity regime-dependence" theory): gamma is
     mechanically highest near the money and decays toward zero deep
     ITM/OTM. The PRACTICAL risk/reward impact of a given gamma value on
     a trade's P&L sensitivity depends on WHERE in moneyness-space the
     position sits -- the same gamma reading means something different
     for a near-the-money position (delta, and therefore P&L, can flip
     quickly) than for a position gamma already implies is far from the
     money. A linear model forces gamma's coefficient to be constant
     across all moneyness levels; this is explicitly a conditional,
     not additive, relationship.
  3. breakout_magnitude_score x trend_strength_score ("confirmation vs.
     exhaustion" theory): a strong breakout WITHOUT an underlying trend
     context is a classic false/exhaustion-breakout pattern (prone to
     mean-reversion); a strong breakout WITH a strong pre-existing trend
     is a continuation signal (classical technical-analysis
     "confirmation" logic). The same breakout_magnitude_score value
     should predict differently depending on trend_strength_score's
     value -- again conditional, not additive, by the theory's own
     construction.

CORRECTED 2026-09-24, before finalizing, caught by explicit user review:
the original draft used V1's realized-vol proxy for the Greeks (as
feature_extraction.py:extract_features() does by default) and disclosed
that as a known limitation rather than fixing it. That was the wrong
call once checked properly -- real historical EODHD IV is CONFIRMED to
cover the full 2023-10-02-to-present window (the same empirical check
in the data-depth section above already confirmed the `volatility` field
populated at every date tested from 2023-10-02 onward, for all 6
tickers -- not a separate, unverified assumption). FIXED: the Greeks
(delta/gamma/theta/charm/vega_per_1pct_iv) will be computed using REAL
historical EODHD IV via v2_iv_pricing_model.py:get_v2_entry_iv() --
the SAME already-validated methodology the V1/V2 pricing-correction
chain uses (T-1-safe, authoritative record-ID snapshot-date rule, never
fabricates/substitutes a fallback value, validated at 8.8% median error
per that module's own docstring) -- not reimplemented, reused exactly
as-is. realized_volatility and realized_vol_percentile are NOT swapped
-- those are legitimately about REALIZED (historical price-based)
volatility, a genuinely different, still-valid feature from IV, and
remain computed via calculate_historical_volatility() as before; only
the volatility INPUT FED INTO THE GREEKS FORMULAS changes.

REAL, DISCLOSED COST OF THIS SWAP, not left unstated: get_v2_entry_iv()
is called ONCE per trade ENTRY (matching extract_features()'s own
existing once-per-entry call pattern, not once per bar) -- one
additional EODHD API call per qualifying trade. Scaling V1's own
90-day/6-ticker/251-trade baseline to the ~2.97-year confirmed window
suggests roughly 2,500-3,500 total entries across 6 tickers, i.e.
roughly 2,500-3,500 EODHD calls for this step alone. This is LARGER than
most single passes already completed this session, but the SAME ORDER
OF MAGNITUDE as several already-completed ones (the SPY historical
backfill and the strike-positioning Stage 1 run were both 600+-call
background passes) -- feasible via the same background-execution
pattern already used repeatedly this session, not a blocking constraint.
Not yet actually run, so this is a disclosed ESTIMATE, not a confirmed
final count. A SECOND, genuine consequence, also disclosed: unlike the
realized-vol proxy (which is always computable from price bars alone),
get_v2_entry_iv() can genuinely return None for a trade whose exact
strike/DTE has no matching real quoted contract on its entry date --
per this project's established "exclude, never substitute" rule (used
everywhere else, e.g. gex_lookup.py, prospective_gex_pipeline.py), any
such trade is EXCLUDED from this experiment's dataset, not backfilled
with the proxy. This means the final joined N will likely be somewhat
LOWER than a proxy-based approach would have produced -- not yet known
precisely, to be confirmed once the new data-generation pass actually
runs, consistent with this project's own established real-IV coverage
rates elsewhere (94.4%-98.8% matched, per the V1/V2 correction chain,
CLAUDE.md Section 3) rather than assumed to be 100%.
"""

from experiment_config import ExperimentConfig

config = ExperimentConfig(
    experiment_id="xgboost_feature_interactions_v1_20260924",
    experiment_type="signal_research",  # matches this project's established convention -- confirmed ML Experiment 1 itself (preregister_experiment1.py) also used "signal_research", not a distinct ML-specific type; ExperimentConfig has no separate ml_model_research value
    hypothesis=(
        "Among the already-validated V1-style trade population (real breakout/regime/score-"
        "gated entries, reversal-guard exits, real spread cost applied), three SPECIFIC named "
        "pairwise feature interactions -- realized_volatility x relative_volume, gamma x "
        "moneyness, and breakout_magnitude_score x trend_strength_score -- carry predictive "
        "information about trade outcome (win/loss) that a linear model CANNOT structurally "
        "represent (each interaction is explicitly a conditional/multiplicative relationship, "
        "not additive), but a tree-based, interaction-aware model (XGBoost) CAN. This is "
        "testing the specific interaction terms, not 'XGBoost is generally better than Ridge' "
        "-- the comparison holds model class constant (XGBoost vs. XGBoost) and varies only "
        "whether the three named interaction features are included, to isolate their own "
        "contribution from any general tree-vs-linear advantage."
    ),
    research_question=(
        "Does adding three specific, theoretically-motivated pairwise interaction features to "
        "the already-validated 13-feature set improve an XGBoost model's out-of-sample "
        "prediction of real trade outcome, beyond what the 13 base features alone achieve -- "
        "and does this hold for a second, independent tree-based model class (Random Forest), "
        "not just XGBoost specifically?"
    ),
    dataset_version="ml_interaction_v1_20231002_present_6ticker_new_generation_pass",
    date_range=("2023-10-02", "2026-09-24"),  # empirically confirmed EODHD options-data floor, not the 90-day generate_training_data.py default -- see data-depth disclosure above. Re-verify this end date against EODHD/Alpaca's actual current extent immediately before the new data-generation pass is run, same discipline as every other experiment in this project with a growing window.
    universe=["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"],
    option_type="call",  # matches the existing V1-style entry chain's fixed_direction="call" convention this data-generation pass reuses (options_backtest_engine.py / generate_training_data.py's existing invocation pattern)
    features_used=[
        ("delta", "1.0"), ("gamma", "1.0"), ("theta", "1.0"), ("charm", "1.0"),
        ("vega_per_1pct_iv", "1.0"), ("realized_volatility", "1.0"), ("realized_vol_percentile", "1.0"),
        ("relative_volume", "1.0"), ("breakout_magnitude_score", "1.0"), ("trend_strength_score", "1.0"),
        ("momentum_score", "1.0"), ("moneyness", "1.0"), ("dte", "1.0"),
        ("realized_volatility_x_relative_volume", "1.0"),  # interaction 1, Model B only
        ("gamma_x_moneyness", "1.0"),  # interaction 2, Model B only
        ("breakout_magnitude_score_x_trend_strength_score", "1.0"),  # interaction 3, Model B only
    ],
    parameters={
        "data_generation_source": "options_backtest_engine.py:run_options_backtest(..., collect_features=True) via feature_extraction.py:extract_features() -- SAME mechanism generate_training_data.py already uses, but over the full empirically-confirmed 2023-10-02-to-present window instead of that script's 90-day default, and MODIFIED to substitute real historical EODHD IV for the Greeks' volatility input (see greeks_volatility_input below) -- everything else about the extraction pipeline (realized_volatility/realized_vol_percentile computation, relative_volume, breakout/trend/momentum scores, moneyness/dte) reused unmodified. A NEW data-generation script is required (not written here, construction/hashing only).",
        "target_metric": "trade_outcome_binary",
        "target_definition": "won = 1 if pnl_dollars > 0 else 0, EXACTLY matching generate_training_data.py's own existing training_examples.won column definition -- reused, not redefined.",
        "greeks_volatility_input": "CORRECTED 2026-09-24 (see module docstring's correction note): delta/gamma/theta/charm/vega_per_1pct_iv use REAL historical EODHD IV via v2_iv_pricing_model.py:get_v2_entry_iv(ticker, entry_timestamp, strike, option_type, target_dte=14) -- the same already-validated methodology (T-1-safe, id-date-safe, 8.8% median error, never fabricates) the V1/V2 pricing-correction chain uses, reused unmodified, one call per trade ENTRY (not per bar). realized_volatility/realized_vol_percentile remain calculate_historical_volatility()-based, unchanged -- those are a genuinely different, still-valid feature (realized, not implied, volatility), not swapped. Trades whose exact strike/DTE has no matching real quoted contract on entry date are EXCLUDED (never substituted with the proxy), per this project's established exclude-never-substitute rule -- final joined N will likely be somewhat lower than a proxy-based count as a direct consequence, not yet known precisely.",
        "greeks_swap_cost_disclosure": "Estimated 2,500-3,500 additional EODHD API calls (one per qualifying trade entry across 6 tickers over the ~2.97-year window, scaled from V1's own 90-day/251-trade baseline) -- larger than most single passes this session, but the same order of magnitude as several already-completed ones (SPY historical backfill, strike-positioning Stage 1, both 600+ calls) -- feasible via the same background-execution pattern already used repeatedly, not a blocking constraint. A disclosed ESTIMATE, not yet confirmed by an actual run.",
        "model_a_primary": "XGBoost on the 13 BASE features only (no interaction terms) -- the 'without interactions' comparison arm",
        "model_b_primary": "XGBoost on the 13 base features PLUS the 3 named interaction features -- the 'with interactions' arm. Comparison of Model A vs Model B, SAME model class held constant, isolates the interactions' own contribution.",
        "xgboost_regularization": "NOT default hyperparameters -- max_depth capped at 3 (shallow trees, deliberately limiting interaction order captured per tree to reduce overfitting risk on a still-modest dataset), min_child_weight>=5, L1 (reg_alpha) and L2 (reg_lambda) both nonzero and tuned via the nested CV below, subsample and colsample_bytree both <=0.8 (row/column subsampling as an additional overfitting guard). Exact grid to be finalized at Stage 1 execution time from this stated family, not left as 'default'.",
        "cross_validation": "NESTED cross-validation on the TRAIN+VALIDATION portion only (chronological, purged -- no test-period data touches hyperparameter selection at any point): outer loop for honest generalization estimate, inner loop for hyperparameter search within the stated regularization family above. Standard nested-CV discipline specifically because the dataset, even at ~3 years, remains modest -- the model must be fighting overfitting by design (regularization + nested CV), not merely getting lucky on one holdout split.",
        "primary_test": "paired_wilcoxon_on_per_observation_log_loss",  # matches ml_experiment1_final_executor.py's own paired-error Wilcoxon design exactly, substituting binary log-loss for MSE (appropriate for probabilistic classification, both XGBoost and Random Forest natively produce predict_proba)
        "primary_significance_alpha": 0.05,  # SINGLE primary comparison (Model A vs Model B, same model class) -- no Bonferroni family needed, matching ML Experiment 1's own single-primary-test structure (not the GEX/IV-family's multi-horizon design, which does need correction)
        "effect_size_threshold_auc_delta": 0.05,  # Model B's AUC-ROC must exceed Model A's by >= 0.05 on the primary test set -- a real, chosen convention (not a literature mandate, stated as such) for "meaningful," not merely statistically-detectable, improvement
        "min_n_per_stage": 100,  # matching this project's family-wide floor; given the ~2.97-year window (vs. the original V1's ~90-day/251-trade window), this is very likely comfortably achievable, but NOT assumed -- to be confirmed by the actual joined count once the new data-generation pass runs
        "primary_test_set_construction": "LOCKED, NON-OVERLAPPING primary test set, same discipline as ml_experiment1_final_executor.py's 24-observation primary set -- NOT a fixed count (that count was itself a consequence of ML Experiment 1's own specific data volume, not a portable constant). Mechanism, pinned now: chronological train (60%) / validation (20%) / test (20%) split by ENTRY DATE (purged -- no trade whose entry falls in a later split can have any exit or feature data leak into an earlier split). Within the full (potentially trade-clustered) test-period pool, the PRIMARY significance test uses a deterministically-thinned non-overlapping subset: the FIRST qualifying trade per (ticker, calendar week) within the test period only -- reduces temporal/market-condition clustering across nearby trades without requiring a result-dependent fixed count. The full (untinned) test set is reported descriptively only (mirroring ML Experiment 1's full-test-set MSE being descriptive, not the primary claim).",
        "robustness_model_choice": "Random Forest, chosen over CatBoost -- CatBoost has no existing dependency or precedent anywhere in this codebase (confirmed by grep, CLAUDE.md Section 38 already established zero tensorflow/keras/torch/sklearn-adjacent ML infrastructure exists beyond what ML Experiment 1 itself used), while scikit-learn (which ships RandomForestClassifier) is a lighter, more standard addition with no new heavy dependency -- the more practical choice given the actual data-depth/infrastructure state confirmed in this pass, not a coin flip.",
    },
    model_version=None,
    pricing_methodology="n/a_trade_outcome_classification_only",  # predicts win/loss of the already-priced, already-executed (simulated) trade -- does not itself touch pricing/spread/execution logic, which the underlying V1-style backtest already applies before this experiment's features/target are computed
    execution_assumptions="reuses the already-validated V1-style entry/exit chain (weighted entry, 0.30 delta, reversal_guard exit, real spread cost applied) exactly as generate_training_data.py already does -- this experiment does not modify or re-derive that chain, only extends its date range and adds ML feature engineering on top",
    train_period=("2023-10-02", "2026-01-31"),  # ~60% of the confirmed window, PLACEHOLDER split point pending the actual joined trade count from the new data-generation pass -- re-verify and adjust proportionally once real N is known, do not silently keep this literal if it no longer reflects a genuine 60/20/20 split
    validation_period=("2026-02-01", "2026-05-31"),  # ~20%, same placeholder caveat as train_period
    test_period=("2026-06-01", "2026-09-24"),  # ~20%, same placeholder caveat -- UNLIKE the GEX/IV-family's rolling test_period=None pattern, this IS locked to a specific historical range (not genuinely prospective/rolling), since the full 2023-10-02-to-present window is itself already historical data -- oos_validation_claimed is still False below, since chronological-holdout is not the same rigor tier as genuine prospective replication
    random_seeds=[42, 43],  # matches this project's established seed pair, used for the nested-CV fold assignment and any stochastic model-fitting steps (XGBoost/Random Forest both have their own internal randomness controlled by this seed)
    code_version="xgboost_feature_interactions_v1_draft",
    testing_family_declaration="INDEPENDENT_SINGLE",
    applicability_lock=[
        ("data_integrity", True), ("lookahead_audit", True), ("timestamp_safety", True),
        ("sample_size_adequacy", False),  # UNKNOWN until the new data-generation pass actually runs and the real joined N is counted
        ("statistical_testing", False), ("reproduction", False),
        ("primary_test_significant", False), ("effect_size_meets_threshold", False),
        ("multiple_testing_survived", False),  # N/A in substance (single primary test, no Bonferroni family) but left False/unrun per the framework's own convention until Stage 1 actually confirms no hidden multiplicity
        ("robustness_survived", False),
        ("oos_survived", False),
        ("primary_performance_test_significant", False), ("concentration_check", False),  # relevant here in a way it wasn't for the GEX-family experiments -- worth checking whether any single ticker or short sub-period dominates the primary test set's result, mirroring Phase 7's concentration-attribution discipline
        ("pricing_accuracy_meets_threshold", False), ("pricing_coverage_meets_threshold", False),
    ],
    oos_validation_claimed=False,  # chronological holdout on already-existing historical data is NOT the same claim as genuine prospective/forward replication -- explicitly not claimed here, matching this project's precise use of the term elsewhere
    declared_robustness_checks=[
        "alternate_model:random_forest",  # MANDATORY per explicit instruction -- same feature set, same target, same train/val/test split, same with/without-interactions comparison, different model class. If XGBoost shows the effect and Random Forest does not, treat this as XGBoost finding noise, not signal -- same severity as this project's other alternate-model/alternate-signal robustness checks, e.g. net-gamma-regime's alternate_signal checks (CLAUDE.md Section 43)
        "leave_one_interaction_out",  # each of the 3 named interactions individually removed from Model B (3 sub-checks) -- confirms the effect isn't driven entirely by just one of the three, which would undercut the "three named interactions" framing of the hypothesis itself
        "leave_one_ticker_out",  # standard check from this project's other experiments, adapted -- 6 tickers here (not 1, unlike the SPY-only experiment), so this remains genuinely runnable
        "alternate_horizon:exit_reason_stratified",  # rerun the primary comparison separately on reversal_guard-exited vs. stop_loss-exited trades (CLAUDE.md Section 13's own finding that these two exit reasons behave near-oppositely) -- confirms the interaction effect isn't an artifact of one dominant exit-reason subgroup
        "shuffled_target_placebo",  # Model B refit with the target (won) randomly permuted before training -- should show NO effect (AUC delta collapsing toward 0, no significant Wilcoxon result); if this placebo ALSO shows a significant effect, that indicates overfitting/leakage in the pipeline itself, not a real interaction signal -- a check with a genuinely different failure mode from the other four, deliberately included to catch a pipeline bug that a same-population/same-target check could never catch
    ],
)

DECISION_RULES = """
VALIDATED requires ALL of:
  1. Primary (thinned, non-overlapping) test-set N >= min_n_per_stage=100
     -- confirmed empirically once the new data-generation pass runs, not
     assumed from the ~2.97-year window's raw scale
  2. Model B (13 base features + 3 named interactions) significantly
     outperforms Model A (13 base features only) on the PRIMARY,
     non-overlapping test set: paired one-sided Wilcoxon on per-
     observation log-loss, alpha=0.05 (single primary test, no
     Bonferroni family -- one comparison, not multiple horizons)
  3. Effect size: AUC-ROC(Model B) - AUC-ROC(Model A) >= 0.05 on the
     primary test set
  4. Survives ALL 5 declared robustness checks in the same direction:
     alternate_model:random_forest, leave_one_interaction_out (all 3
     sub-checks), leave_one_ticker_out, alternate_horizon:
     exit_reason_stratified, AND the shuffled_target_placebo shows NO
     significant effect (this one check's PASS condition is the inverse
     of the others -- explicitly noted here to avoid the interpretation
     ambiguity this project has hit before with asymmetric-condition
     robustness checks, CLAUDE.md Section 33's 50-day-horizon case)
  5. No single ticker or contiguous sub-period drives the entire primary-
     test effect (concentration_check) -- mirrors Phase 7's concentration
     discipline (CLAUDE.md Section 13), applied here for the first time
     to an ML-track experiment

REJECTED if:
  - Primary N >= 100 but the primary test is not significant at alpha=
    0.05, OR effect size (AUC delta) is below 0.05, OR the direction
    reverses under any of the first four robustness checks, OR the
    shuffled_target_placebo DOES show a significant effect (indicating
    a pipeline/leakage problem rather than the interactions themselves
    being non-predictive -- flagged separately from a clean REJECTED if
    this specific check fails, since it implies the whole pipeline needs
    fixing before ANY verdict here can be trusted, not just this
    hypothesis)

INCONCLUSIVE if:
  - Primary N < 100 after the new data-generation pass (would be a
    genuine surprise given the ~2.97-year window's scale relative to
    V1's own 251-trade/90-day baseline, but not assumed in advance)
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

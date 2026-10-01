from dotenv import load_dotenv
load_dotenv()

"""
DRAFT pre-registration for the NET GAMMA REGIME hypothesis -- a third,
distinct GEX-based experiment, scoped 2026-09-22 after the call-wall-
distance experiment (preregister_gex_callwall_experiment.py) CLOSED as
REJECTED at Stage 1 (CLAUDE.md Section 32).

THIS FILE CONSTRUCTS AND PRINTS THE CONFIG FOR REVIEW ONLY. IT DOES NOT
CALL preregister_experiment() ANYWHERE, and no data has been touched
beyond a raw feasibility count directly against gex_metrics (see below --
a plain COUNT/GROUP BY, not a join against any signal population, and
nothing about the hypothesis's actual predictive relationship was
inspected).

WHY THIS IS A GENUINELY DIFFERENT HYPOTHESIS FROM CALL-WALL-DISTANCE, NOT
A RELABELING OF THE SAME REJECTED IDEA:
  - Call-wall-distance is a SPATIAL/POSITIONAL, FIRST-MOMENT test: does
    proximity to one specific strike (the call wall) predict SUPPRESSED
    forward RETURN LEVEL, via a localized price-pinning mechanism? This
    used call_wall_strike (from find_gamma_walls(), which does NOT branch
    on sign_convention -- confirmed by direct code read, CLAUDE.md Section 32).
  - Net gamma regime is an AGGREGATE, SECOND-MOMENT test: does the SIGN of
    total dealer gamma exposure (no strike information at all) predict
    forward REALIZED VOLATILITY MAGNITUDE (sign-agnostic price-swing
    size), via a portfolio-wide hedging-flow-direction mechanism? This
    uses gex_regime / net_gex (from calculate_net_gex(), which DOES branch
    on sign_convention -- confirmed by direct code read below).
  These are computed by different functions, feed different outcome
  variables (return level vs. volatility), and test different theories
  (localized pinning vs. portfolio-wide hedging-flow amplification). A
  signal could score anywhere on call_wall_distance_pct independent of
  its gex_regime -- the two are not assumed correlated, and that
  correlation (if any) has not been computed here.
"""

from experiment_config import ExperimentConfig

# ---------------------------------------------------------------------------
# FEASIBILITY CHECK -- 2026-09-22, direct query against the CURRENT (post-
# backfill, Section 40) gex_metrics table. Raw distribution only -- NOT
# joined against V1-qualifying signals, and no relationship between regime
# and any forward outcome was computed or inspected.
#
#   model_a convention:  384 positive / 41 negative  (425 total (ticker,
#     snapshot_date) rows, 6 tickers, 2026-06-10 to 2026-09-21) -- 9.6%
#     negative. Per-ticker negative counts: AAPL=2, TSLA=11, NVDA=6, AMD=13,
#     SMCI=1, MSTR=8 -- SMCI and AAPL in particular have very few negative-
#     regime snapshot-days in the ENTIRE available history.
#   flipped convention:  41 positive / 384 negative -- confirmed a near-
#     total MIRROR IMAGE of model_a (this is a genuine, meaningful
#     robustness axis for THIS hypothesis, unlike call-wall-distance, where
#     sign_convention was confirmed to not affect call_wall_strike at all).
#
# HONEST, UNRESOLVED FEASIBILITY RISK, flagged rather than smoothed over:
# this class imbalance (9.6% negative) is a RAW upper-bound proxy on the
# full snapshot table, not the actual joined N against V1-qualifying
# signals -- that join has NOT been run. Two reasons the true joined
# negative-regime N could be smaller still, not just proportionally scaled:
#   (a) V1's gate requires a BULLISH SPY regime, while negative dealer-
#       gamma exposure is theorized in the literature to correlate with
#       market stress/decline -- if that correlation is real in this data,
#       restricting to V1-qualifying (bullish-only) signals could
#       systematically under-sample exactly the negative-regime days this
#       hypothesis needs, worse than a naive proportional estimate.
#   (b) The severe per-ticker imbalance (SMCI=1, AAPL=2 negative days in
#       the ENTIRE table) means leave-one-ticker-out robustness (a
#       declared check below) could be materially destabilized by
#       excluding AMD, MSTR, or TSLA specifically, which carry most of the
#       negative-regime observations.
# This is disclosed now, before Stage 1 runs, exactly like call-wall-
# distance's own pre-run joined-N uncertainty was disclosed rather than
# assumed favorable.
# ---------------------------------------------------------------------------

NOTES = (
    "PRE-REGISTRATION DRAFT, not yet submitted. Third GEX-based hypothesis, "
    "scoped 2026-09-22 after call-wall-distance CLOSED REJECTED (CLAUDE.md "
    "Section 32) and GEX_Historical_Incremental_Update (Section 40) was "
    "confirmed to be general-purpose infrastructure, not tied to the closed "
    "hypothesis. This is the SAME construction SpyGammaLoop already uses "
    "LIVE for entry gating (CLAUDE.md Section 34-36: negative net-gamma "
    "regime as part of its signal chain) -- but SpyGammaLoop's own use of "
    "this signal has NEVER been formally tested for predictiveness, only "
    "used operationally, on live paper capital. This experiment is the "
    "first formal predictiveness test of that construction. "
    "NO forward-collection wait needed for Stage 1/2, unlike the now-closed "
    "call-wall-distance design -- GEX has no data before 2026-06-10 "
    "(gex_data_loader.py's own frozen TRAIN_START), so a pre-V1-window split "
    "(the IV-term-structure/strike-positioning pattern) is not available "
    "here either. Instead, this reuses gex_data_loader.py's own ALREADY-"
    "EXISTING, non-arbitrary TRAIN_END=2026-08-11 boundary to split the "
    "single available window into Stage 1 / Stage 2, and Stage 2 grows via "
    "the already-running, general-purpose GEX_Historical_Incremental_Update "
    "job (Section 40) -- no new prospective pipeline required.\n\n"
    "CORRECTED 2026-09-22, same day, caught by explicit user review BEFORE "
    "Stage 1 was touched -- a real population-design flaw, not a nitpick. "
    "The original draft inherited call-wall-distance's V1-qualifying "
    "signal population (bullish SPY regime + 20-bar breakout + entry_score>=20, "
    "calls only). This is wrong for THIS hypothesis specifically: net gamma "
    "regime is a market-structure/volatility-amplification mechanism with no "
    "connection to V1's directional bullish setup, and V1's bullish-only gate "
    "was very plausibly suppressing exactly the negative-regime days this "
    "hypothesis needs (negative dealer gamma is theorized to correlate with "
    "market stress/decline -- the opposite of V1's bullish requirement). "
    "Worse structurally: gex_regime is itself a once-per-ticker-per-day "
    "quantity, so multiple intraday V1 signals on the same day all share the "
    "IDENTICAL regime value -- day-clustered statistical power depends on "
    "DISTINCT DAYS represented, not signal count, and the day-level ceiling "
    "for negative-regime days (41 in the full table) can never be exceeded "
    "by adding more intraday signals on top of it. FIXED: population is now "
    "DAY-LEVEL and UNCONDITIONAL on V1's gate -- one observation per (ticker, "
    "trading day), anchored at that day's market-open bar, no bullish-regime/"
    "breakout/entry-score requirement at all. This matches an ALREADY-"
    "ESTABLISHED precedent in this exact project: iv_term_structure_slope_v1_"
    "20260921's own SCOPE NOTE explicitly chose the same 'NOT conditioned on "
    "V1's entry signal... population is all valid trading days... independent "
    "of whether V1 would have fired an entry that day' design, for the "
    "identical underlying reason (a market-structure mechanism, not a "
    "directional-entry-conditional one). VERIFIED BEFORE LOCKING, not assumed: "
    "direct query against the current gex_metrics table confirms this "
    "materially improves feasibility -- Stage 1 window (2026-06-10 to "
    "2026-08-11) under the new day-level population has 260 total "
    "(ticker,day) rows, 33 negative-regime (12.7%), comfortably clearing both "
    "min_n_per_stage=100 AND min_n_negative_regime_per_stage=20. Stage 2 (so "
    "far, still growing) has 165 total, 8 negative -- clears the total floor "
    "already, not yet the negative-regime floor, consistent with the general "
    "rolling-Stage-2-still-accumulating pattern already established for the "
    "other experiments in this family."
)

config = ExperimentConfig(
    experiment_id="gex_netgammaregime_v1_20260922",
    experiment_type="signal_research",
    hypothesis=(
        "Among all valid (ticker, trading day) observations in the 6-ticker universe -- NOT "
        "conditioned on V1's directional entry gate, see the population-design correction in "
        "NOTES above -- T-1 net gamma regime (gex_regime: positive vs. negative aggregate "
        "signed dealer gamma exposure, from gex_lookup.py's T-1 validated GEX snapshot, "
        "sign_convention=model_a) predicts forward REALIZED VOLATILITY MAGNITUDE, independent "
        "of return direction or level: days with a NEGATIVE net gamma regime show "
        "systematically HIGHER forward realized volatility (measured from that day's market "
        "open) than days with a POSITIVE net gamma regime, consistent with the standard "
        "theory that a net-short-gamma dealer book must hedge by trading in the SAME "
        "direction as the underlying's move (selling into declines, buying into rallies), "
        "amplifying realized price swings; a net-long-gamma (positive regime) book hedges "
        "AGAINST the move, dampening realized swings. This is a distinct mechanism and a "
        "distinct outcome variable from the closed call-wall-distance hypothesis (localized "
        "price-pinning -> suppressed RETURN LEVEL near one specific strike, itself "
        "V1-conditioned), not a re-test of the same idea."
    ),
    research_question=(
        "Does the SIGN of aggregate T-1 dealer gamma exposure carry predictive information "
        "about forward realized volatility for this project's 6-ticker universe, on any "
        "trading day -- the same construction SpyGammaLoop already uses live for entry "
        "gating (CLAUDE.md Section 34-36), but never formally tested for predictiveness "
        "until now?"
    ),
    dataset_version="gex_metrics_v1_20260610_20260921_two_window_split_daylevel_unconditional",
    date_range=("2026-06-10", "2026-09-21"),  # known span as of preregistration time; grows via GEX_Historical_Incremental_Update (Section 40) -- Stage 2's actual end date will grow past this, see test_period/parameters.stage2_window_definition
    universe=["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"],
    option_type="n/a_underlying_only",  # CORRECTED -- population is no longer V1's calls-only convention; this tests the underlying's realized volatility directly, not tied to any option direction
    features_used=[
        ("net_gamma_regime_negative_indicator", "1.0"),
    ],
    parameters={
        "gex_source": "gex_lookup.py:get_gex_for_signal, sign_convention=model_a, field=gex_regime",
        "signal_qualification": (
            "CORRECTED 2026-09-22 (see NOTES) -- population is DAY-LEVEL and UNCONDITIONAL "
            "on V1's entry gate: one observation per (ticker, real trading day) where a T-1 "
            "GEX snapshot is available (gex_lookup.py:get_gex_for_signal, sign_convention="
            "model_a), across the full 6-ticker universe. NO bullish-SPY-regime requirement, "
            "NO 20-bar-breakout requirement, NO entry_score>=20 requirement, NO calls-only "
            "restriction -- V1's gate does not apply to this hypothesis at all, matching the "
            "already-established, differently-worded precedent in "
            "iv_term_structure_slope_v1_20260921's own SCOPE NOTE ('NOT conditioned on V1's "
            "entry signal... population is all valid trading days')."
        ),
        "anchor_timestamp": "Each (ticker, trading day) observation is anchored at that day's FIRST 5-minute bar (market open) -- a non-arbitrary, once-per-day reference point matching gex_regime's own once-per-ticker-per-day granularity (unlike an intraday V1 signal timestamp, which would reintroduce a selection question about WHICH bar of the day to pick). Real trading days determined via get_real_trading_days() (gex_data_loader.py), the same trading-calendar helper used throughout this project.",
        "group_definition": "Natural categorical split on gex_regime (positive/negative) at T-1 -- NOT a median split (unlike call-wall-distance's continuous |call_wall_distance_pct|), since gex_regime is already binary in the stored data. No re-derivation of the regime boundary -- uses gex_calculator.py's own already-computed, already-stored classification as-is.",
        "target_metric": "realized_volatility_forward",
        "realized_volatility_formula": "Population standard deviation of consecutive 5-minute-bar log returns over the forward horizon, measured from each ticker-day's market-open anchor bar (log(bars[i+1].close/bars[i].close) for i in [anchor_index, anchor_index+horizon-1]), NOT annualized -- comparisons are relative (negative-regime vs. positive-regime, same bar frequency throughout), so a constant annualization scalar would not change any conclusion. Deliberately uses 5-minute-bar granularity, not IV term-structure's daily-bar formula (CLAUDE.md Section 33) -- matches this project's intraday data granularity. Pinned here, upfront, before Stage 1 runs -- unlike IV term structure, which had to pin its own formula mid-stream after an ambiguity was caught.",
        "target_horizons_bars": [5, 10, 20, 50],  # matches call-wall-distance's set -- same GEX-family, direct comparability
        "primary_horizon_bars": 20,  # matches Phase 6/call-wall-distance's primary horizon
        "secondary_horizons_bars": [5, 10, 50],
        "primary_test": "monte_carlo_day_clustered_one_sided",  # reuses Phase 6/call-wall-distance's already-validated methodology, not re-derived: T_obs = day-clustered-mean(realized_vol | negative) - day-clustered-mean(realized_vol | positive); null built by permuting regime labels across the pooled ticker-day observations, preserving group sizes; one-sided p-value. Day-clustering now clusters ACROSS TICKERS sharing the same calendar date (since there is exactly one observation per ticker-day), a cleaner application than the signal-based experiments' blend of within-ticker multi-signal and cross-ticker clustering.
        "monte_carlo_replicates": 1000,
        "min_n_per_stage": 100,  # total, matching the other three experiments' floor
        "min_n_negative_regime_per_stage": 20,  # specific to this hypothesis -- a total-N floor alone is insufficient given the known class imbalance; without a floor on the minority class, a technically-adequate total N could still leave the negative-regime group too small for a meaningful comparison. Not present in the other three experiments because their splits were roughly balanced (continuous median-splits or naturally frequent categories); this is a deliberate, disclosed addition, not a silent inconsistency.
        "bonferroni_family_size": 4,  # 4 horizons tested (5/10/20/50-bar), matching call-wall-distance
        "alpha_uncorrected": 0.05,
        "effect_size_threshold_vol_ratio": 1.20,  # negative-regime forward realized vol must be >= 1.20x (20% relatively higher) than positive-regime forward realized vol to count as economically meaningful. Deliberately a RATIO threshold, not an additive percentage-point threshold like the other three experiments -- volatility comparisons are naturally multiplicative (standard convention: 'vol was X% higher'), not additive, and using a pp-based threshold here would not be a meaningful adaptation of the other experiments' convention, it would be a category error.
        "class_imbalance_disclosure": "Day-level, unconditional (current design): Stage 1 window (2026-06-10 to 2026-08-11) has 260 total (ticker,day) rows, 33 negative-regime (12.7%) -- clears both min_n_per_stage=100 and min_n_negative_regime_per_stage=20. Stage 2 window so far (2026-08-12 to 2026-09-21) has 165 total, 8 negative -- clears the total floor, not yet the negative-regime floor; will keep growing via GEX_Historical_Incremental_Update. Confirmed by direct query 2026-09-22, BEFORE locking this design change -- not assumed favorable. (For reference, the raw full-table figure across both stages combined, unconditional on stage: 384 positive/41 negative of 425 rows, 9.6% negative -- this is the number the earlier, now-superseded V1-gated design was working from.)",
        "stage1_stage2_split_rationale": "Unlike IV term structure and strike positioning, GEX has NO data before 2026-06-10 (gex_data_loader.py's own frozen TRAIN_START) -- a pre-V1-window historical split is not available for any GEX-based hypothesis. Instead, this experiment splits the single available window at gex_data_loader.py's own ALREADY-EXISTING TRAIN_END=2026-08-11 constant (CLAUDE.md Section 15/40) -- a non-arbitrary boundary that already existed in the codebase for a different original purpose, not a date chosen or tuned for this experiment.",
        "stage2_window_definition": "ROLLING, not a fixed literal -- FIXED START 2026-08-12 (the day after the Stage 1/Stage 2 split), OPEN END determined at whatever moment Stage 2 is actually executed, via a data-EXISTENCE check only (record count > 0 in gex_metrics for the most recent date -- never by computing or inspecting any regime/volatility relationship). Continues accumulating via the already-running GEX_Historical_Incremental_Update job (Section 40, general-purpose infrastructure, not tied to the closed call-wall-distance hypothesis) until the joined N (and, separately, the negative-regime joined N) reach their respective thresholds. Once reached, LOCK the exact realized end-date and run the primary test ONCE against that locked set. No new prospective/forward-collection pipeline is needed for this design, unlike the now-closed call-wall-distance experiment.",
    },
    model_version=None,
    pricing_methodology="n/a_realized_volatility_prediction_only",  # predicts realized volatility of the UNDERLYING, not option P&L -- same isolation choice as IV term structure
    execution_assumptions="none -- this experiment does not touch option pricing, spread, sizing, or execution; a separate follow-on experiment would be needed to translate any validated regime edge into an actual trading/sizing rule",
    train_period=("2026-06-10", "2026-08-11"),  # Stage 1 -- bounded by gex_data_loader.py's own pre-existing TRAIN_END constant, not a new/arbitrary choice
    validation_period=None,
    test_period=None,  # deliberately None, matching the now-corrected pattern from IV term structure/strike positioning -- Stage 2's actual realized set isn't knowable at preregistration time; oos_validation_claimed is False until Stage 2 actually runs
    random_seeds=[42, 43],  # matches Phase 6/GEX-family's exact seed pair
    code_version="gex_netgammaregime_v1_draft",
    testing_family_declaration="INDEPENDENT_SINGLE",
    applicability_lock=[
        ("data_integrity", True), ("lookahead_audit", True), ("timestamp_safety", True),
        ("sample_size_adequacy", False),  # UNKNOWN until the actual join is run -- especially uncertain here given the disclosed class-imbalance risk
        ("statistical_testing", False), ("reproduction", False),
        ("primary_test_significant", False), ("effect_size_meets_threshold", False),
        ("multiple_testing_survived", False), ("robustness_survived", False),
        ("oos_survived", False),
        ("primary_performance_test_significant", False), ("concentration_check", False),
        ("pricing_accuracy_meets_threshold", False), ("pricing_coverage_meets_threshold", False),
    ],
    oos_validation_claimed=False,  # Stage 2 has not run
    declared_robustness_checks=[
        "leave_one_ticker_out",  # HIGHER RISK than the other experiments' version of this check, given the severe per-ticker negative-regime imbalance disclosed above (SMCI=1, AAPL=2) -- flagged, not hidden
        "alternate_horizon:5bar", "alternate_horizon:10bar", "alternate_horizon:50bar",
        "sign_convention:flipped",  # UNLIKE call-wall-distance (where this was confirmed a structural no-op, Section 32), this IS a meaningful check here: calculate_net_gex() DOES branch on sign_convention, and gex_regime is confirmed a near-total mirror image between conventions (384/41 vs 41/384) -- this tests whether the amplification pattern also holds under the alternative dealer-positioning assumption, a genuinely different economic claim, not a reproduction of the same computation.
    ],
)

DECISION_RULES = """
VALIDATED requires ALL of:
  1. Stage 1 joined N >= 100 (min_n_per_stage) AND joined negative-regime
     N >= 20 (min_n_negative_regime_per_stage) -- both floors required,
     given the disclosed class imbalance; a technically-adequate total N
     with too few negative-regime observations does not count
  2. Primary test (20-bar horizon) significant at Bonferroni-corrected
     alpha = 0.05 / 4 = 0.0125 (bonferroni_family_size=4), one-sided in
     the hypothesized direction (negative regime -> higher forward
     realized volatility)
  3. Effect size: negative-regime forward realized vol >= 1.20x
     positive-regime forward realized vol (effect_size_threshold_vol_ratio)
  4. Survives ALL declared robustness checks (leave-one-ticker-out, the
     three secondary horizons, sign_convention:flipped) in the same
     direction
  5. Stage 2 (rolling, fixed start 2026-08-12, open end -- see
     parameters.stage2_window_definition; N>=100 AND negative-regime
     N>=20 required, stop-and-lock via data-existence check only)
     replicates the same direction

REJECTED if:
  - Stage 1 N >= 100 (and negative-regime N >= 20) but the primary test is
    not significant at the corrected alpha, OR effect size is below the
    1.20x threshold, OR the direction reverses under any declared
    robustness check

INCONCLUSIVE if:
  - Stage 1 N < 100, OR negative-regime N < 20 (do not interpret whatever
    number comes out anyway if the minority-class floor isn't met, even if
    the total floor is)
  - Stage 1 passes but Stage 2 cannot yet reach its own N/negative-N
    thresholds -- experiment stays OPEN, not closed, pending further
    accumulation via GEX_Historical_Incremental_Update
  - Stage 1 and Stage 2 disagree in direction without a pre-specified
    tiebreaker (none specified here -- a genuine conflict would require a
    NEW, separately pre-registered follow-up, not an ad hoc resolution)
"""

print("=" * 100)
print("DRAFT CONFIG -- FOR REVIEW, NOT YET PREREGISTERED")
print("=" * 100)
print("experiment_id: " + config.experiment_id)
print("experiment_type: " + config.experiment_type)
print("hypothesis: " + config.hypothesis)
print("research_question: " + config.research_question)
print("universe: " + str(config.universe))
print("train_period (Stage 1): " + str(config.train_period))
print("test_period (Stage 2): " + str(config.test_period))
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

from dotenv import load_dotenv
load_dotenv()

"""
DRAFT pre-registration for the strike-structure/positioning (OI skew)
hypothesis -- a third parallel formal experiment, alongside GEX
call-wall-distance (preregister_gex_callwall_experiment.py) and IV
term-structure slope (preregister_iv_termstructure_experiment.py).
GEX and IV term structure stay in their own separate tracks, untouched
by this. Candidate signal first defined in CLAUDE.md Section 37
(2026-09-22), feasibility-confirmed there (18/18 ticker-date pairs);
this is the formal pre-registration for it.

Modeled directly on preregister_experiment1.py's ExperimentConfig
structure and the two prior pre-registrations' discipline.

THIS FILE CONSTRUCTS AND PRINTS THE CONFIG FOR REVIEW ONLY.
IT DOES NOT CALL preregister_experiment() OR run_experiment() ANYWHERE.
Per explicit instruction: construction and hashing only. No data has
been touched, no test has run.

WHY A HISTORICAL TWO-SIDED SPLIT (like IV term structure), NOT A
GEX-STYLE PROSPECTIVE-ONLY DESIGN: GEX's call-wall-distance depends on
a pre-computed, narrower-window table (gex_data_cache.db:gex_metrics,
confirmed 2026-06-10 to 2026-09-08 only, Section 37) that itself came
from a specific calculation pipeline (gex_calculator.py) -- Stage 2
there genuinely requires new data to be collected forward. This OI-skew
signal reads `open_interest` DIRECTLY from the same raw EODHD chain
already confirmed present from at least 2026-01-15 through at least
2026-09-18 (the IV term-structure feasibility work, Section 33) -- no
intermediate calculated/stored pipeline is required. A genuinely
out-of-sample historical holdout is therefore available the same way
it was for IV term structure, and is used here for consistency and to
avoid an unnecessary prospective wait this signal doesn't actually need.
"""

from experiment_config import ExperimentConfig

# ---------------------------------------------------------------------------
# SIGNAL DEFINITION -- as scoped in CLAUDE.md Section 37, feasibility-
# confirmed there (18/18 ticker-date pairs, full universe, id-date-safe,
# not a single-ticker spot check).
#
#   oi_skew = log(total_put_OI_near_money / total_call_OI_near_money)
#
# "Near money" = strikes within +/-10% of the underlying's own real closing
# price on the observation date (Alpaca daily close, same source already
# validated for IV term structure's realized-return computation -- using
# that SAME day's own close is not lookahead, it's the standard way to
# define moneyness for a same-day snapshot).
#
# DTE window = 7-45 days, aggregated ACROSS ALL expirations in that window
# (not a single near/far expiration pair like the IV term-structure slope --
# this is a chain-wide positioning sum, structurally closer to GEX's
# aggregation shape than to the term-structure slope's shape). Uses RAW
# open interest only -- no gamma weighting (unlike GEX), no IV (unlike
# term structure) -- a pure positioning/sentiment proxy.
#
# Division-by-zero handling: if total_call_OI or total_put_OI is exactly
# zero for a (ticker, date), the observation is EXCLUDED (log ratio
# undefined) -- never fabricated, never substituted.
# ---------------------------------------------------------------------------

NOTES = (
    "PRE-REGISTRATION DRAFT, not yet submitted. Third parallel experiment "
    "alongside gex_callwall_distance_v1_20260921 and "
    "iv_term_structure_slope_v1_20260921 (both untouched by this). "
    "Candidate signal and feasibility check (18/18 ticker-date pairs, full "
    "universe, id-date-safe) both done in CLAUDE.md Section 37, 2026-09-22, "
    "prior to this pre-registration. "
    "THEORETICAL MECHANISM, stated explicitly so the hypothesis is "
    "falsifiable rather than 'skew matters somehow': this is a CROWD-"
    "SENTIMENT / contrarian-positioning hypothesis, not a dealer-hedging-"
    "flow hypothesis -- deliberately kept distinct from GEX's mechanism, "
    "which already occupies the dealer-positioning explanation. Classical "
    "put/call-ratio technical analysis treats elevated put positioning as "
    "a sentiment extreme (crowd hedging/fear) that tends to mean-revert, "
    "not as informed negative information -- hence the predicted direction "
    "is POSITIVE (contrarian), not negative. "
    "SPLIT DESIGN: historical two-sided split (Stage 1 pre-V1-window, "
    "Stage 2 rolling post-V1-window), matching IV term structure's design, "
    "NOT a GEX-style prospective-only design -- justified because this "
    "signal reads open_interest directly from the raw EODHD chain "
    "(confirmed present 2026-01-15 through 2026-09-18+), with no "
    "intermediate calculated/stored pipeline required, unlike GEX's "
    "dependency on the narrower, separately-computed gex_metrics table. "
    "TARGET: forward RETURN of the underlying (not realized volatility, "
    "unlike the IV term-structure experiment) -- this signal makes a "
    "directional prediction, not a volatility-regime prediction."
)

config = ExperimentConfig(
    experiment_id="strike_positioning_oi_skew_v1_20260922",
    experiment_type="signal_research",
    hypothesis=(
        "Elevated put/call open-interest skew near spot (oi_skew = log(put_OI/call_OI), "
        "strikes within +/-10% of spot, 7-45 DTE, summed across all expirations in that "
        "window) reflects crowd hedging/bearish positioning that is, on average, "
        "CONTRARIAN -- predicting HIGHER subsequent returns over the following 20 trading "
        "days. Conversely, low put/call skew (more call positioning, bullish crowd "
        "speculation) predicts relatively LOWER subsequent returns. This is a sentiment/"
        "positioning mechanism, deliberately distinct from GEX's dealer-hedging-flow "
        "mechanism (raw OI, not gamma-weighted) and from IV term structure's vol-pricing "
        "mechanism (open interest, not implied volatility)."
    ),
    research_question=(
        "Does put/call open-interest skew near spot carry predictive information about "
        "subsequent underlying returns for this project's 6-ticker universe, measured on "
        "data entirely outside V1's own analyzed window, in the contrarian direction "
        "classical put/call-ratio theory predicts?"
    ),
    dataset_version="eodhd_oi_skew_v1_two_window_split",
    date_range=("2026-01-15", "2026-09-22"),  # known data span as of preregistration time; Stage 2's actual end date rolls forward, see parameters.stage2_window_definition
    universe=["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"],
    option_type="call",  # field required by ExperimentConfig; NOTE this experiment's signal itself uses BOTH calls and puts (it is a put/call ratio) -- this field describes the schema convention only, not a restriction on which option type's OI is read
    features_used=[
        ("oi_skew", "1.0"),
    ],
    parameters={
        "moneyness_band_pct": 0.10,  # +/- 10% of spot, matching the feasibility check
        "dte_window": [7, 45],  # aggregated across ALL expirations in this window, not a single near/far pair
        "spot_source": "Alpaca daily close on the observation date (same source validated for IV term structure)",
        "skew_definition": "log(total_put_OI / total_call_OI), summed across all contracts within moneyness_band_pct and dte_window, id-date-safe (never tradetime). If either total is exactly zero, the observation is EXCLUDED (undefined ratio), never fabricated.",
        "target_metric": "forward_return_20d",
        "target_horizons_days": [10, 20, 50],
        "primary_horizon_days": 20,  # matches Phase 6/GEX/IV-term-structure's primary horizon for comparability
        "secondary_horizons_days": [10, 50],
        "primary_test": "monte_carlo_day_clustered_one_sided",  # reuses Phase 6's already-validated methodology; hypothesized direction is POSITIVE correlation (contrarian), opposite sign convention from the IV term-structure experiment
        "monte_carlo_replicates": 1000,
        "min_n_per_stage": 100,
        "bonferroni_family_size": 3,  # 3 horizons tested (10/20/50-day)
        "alpha_uncorrected": 0.05,
        "effect_size_threshold_correlation": 0.15,  # same threshold as the IV term-structure experiment, for cross-hypothesis comparability
        "coverage_confirmed_via_sample": "18/18 (ticker, date) pairs across 6 tickers x 3 dates spanning V1's window had real, nonzero OI on both call and put sides -- CLAUDE.md Section 37, 2026-09-22",
        "stage2_window_definition": (
            "ROLLING, not a fixed literal -- learned directly from the IV term-structure "
            "experiment's caught-and-fixed bug (a hardcoded literal end date cannot grow). "
            "FIXED START 2026-09-10 (the day immediately after V1's frozen window ends), "
            "OPEN END determined at whatever moment Stage 2 is actually executed: query the "
            "real trading calendar for the most recent day with available EODHD data (a "
            "data-EXISTENCE check only, never by computing or inspecting the actual skew/"
            "return relationship). Continue accumulating trading days forward from "
            "2026-09-10 until the joined N reaches min_n_per_stage=100, then LOCK the exact "
            "realized end-date and run the primary test ONCE against that locked set."
        ),
    },
    model_version=None,
    pricing_methodology="n/a_underlying_return_prediction_only",  # this experiment predicts underlying returns, not option P&L -- same deliberate isolation as the other two signal experiments
    execution_assumptions="none -- this experiment does not touch option pricing, spread, sizing, or execution; a separate follow-on experiment would be needed to translate any validated edge into an actual trading rule",
    train_period=("2026-01-15", "2026-06-10"),  # Stage 1, entirely pre-V1-window, same dates as IV term structure for cross-hypothesis comparability
    validation_period=None,
    test_period=None,  # Stage 2 is rolling/open-ended -- see parameters.stage2_window_definition; None here for the same reason as both prior experiments
    random_seeds=[42, 43],  # matches Phase 6/GEX/IV-term-structure's exact seed pair
    code_version="strike_positioning_oi_skew_v1_draft",
    testing_family_declaration="INDEPENDENT_SINGLE",
    applicability_lock=[
        ("data_integrity", True), ("lookahead_audit", True), ("timestamp_safety", True),
        ("sample_size_adequacy", False),  # UNKNOWN until the actual join is run
        ("statistical_testing", False), ("reproduction", False),
        ("primary_test_significant", False), ("effect_size_meets_threshold", False),
        ("multiple_testing_survived", False), ("robustness_survived", False),
        ("oos_survived", False),
        ("primary_performance_test_significant", False), ("concentration_check", False),
        ("pricing_accuracy_meets_threshold", False), ("pricing_coverage_meets_threshold", False),
    ],
    oos_validation_claimed=False,  # test_period=None -- matches both prior experiments' correct pattern (the OOS design intent is real, but can't be claimed as a locked, datable test_period while Stage 2 is still open-ended)
    declared_robustness_checks=[
        "leave_one_ticker_out",
        "alternate_horizon:10d", "alternate_horizon:50d",
        "alternate_moneyness_band:15pct",  # sensitivity to the +/-10% choice -- widen to +/-15%
        "alternate_dte_window:7-30dte",    # sensitivity to the 7-45 DTE choice -- narrow to 7-30
    ],
)

DECISION_RULES = """
VALIDATED requires ALL of:
  1. Stage 1 joined N >= 100 (min_n_per_stage) -- population is ALL valid
     trading days with a computable oi_skew, not gated by V1's signal
  2. Stage 1 primary test (20-day horizon) significant at Bonferroni-corrected
     alpha = 0.05 / 3 = 0.0167, one-sided in the hypothesized direction
     (POSITIVE correlation -- higher put skew -> higher forward return,
     contrarian; NOTE this is the OPPOSITE sign convention from the IV
     term-structure experiment)
  3. Effect size (|correlation|) >= 0.15
  4. Survives ALL 5 declared robustness checks in the same direction
  5. Stage 2 (rolling window starting 2026-09-10, open end -- see
     parameters.stage2_window_definition; N >= 100 required, stop-and-lock
     the moment that's reached, checked via data-existence only, never via
     peeking at the result) replicates the same direction

REJECTED if:
  - Stage 1 N >= 100 but primary test not significant, or effect size below
    threshold, or direction reverses under any robustness check

INCONCLUSIVE if:
  - Stage 1 N < 100
  - Stage 1 passes but Stage 2 has not yet reached N >= 100
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
print("run_experiment() -- registering this config into the real framework, and")
print("running Stage 1, are separate, deliberate future steps. NO DATA TOUCHED.")
print("=" * 100)

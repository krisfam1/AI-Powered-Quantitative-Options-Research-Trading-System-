from dotenv import load_dotenv
load_dotenv()

"""
V2 (2026-10-01): iv_term_structure_slope_v2_20261001 supersedes iv_term_structure_slope_v1_20260921
(file preregister_iv_termstructure_experiment.py, kept byte-identical). Sole substantive change: the
locked Stage 2 test now requires N >= 139 distinct days (new parameter min_n_stage2) instead of 100,
for power (89% at Stage 1's r=0.28 vs 76%). Stage 1 is NOT re-run or re-judged: it stays governed by
min_n_per_stage = 100 (passed with 101 days), SUGGESTIVE. Text below is v1's, updated where noted.

DRAFT pre-registration for the IV term-structure-slope hypothesis --
a second, parallel formal experiment alongside the GEX call-wall-distance
one (preregister_gex_callwall_experiment.py), chosen 2026-09-21. GEX stays
in its own wait-and-monitor phase, untouched -- this is additive, not a
replacement.

Modeled directly on preregister_experiment1.py / preregister_gex_callwall_
experiment.py's structure and ExperimentConfig's actual validated fields.

THIS FILE CONSTRUCTS AND PRINTS THE CONFIG FOR REVIEW ONLY.
IT DOES NOT CALL preregister_experiment() ANYWHERE. Per explicit
instruction, the actual test must not run yet -- this script cannot
register or execute anything even if run end to end.

KEY METHODOLOGICAL DIFFERENCE FROM THE GEX EXPERIMENT: GEX's Stage 2 needs
genuinely-not-yet-existing future data from an ongoing forward collection
pipeline. This hypothesis uses only already-existing historical EODHD data
-- confirmed 2026-09-21 to extend from at least 2026-01-15 through at
least 2026-09-18 (both ends spot-checked directly, id-date-safe). That
means BOTH the primary and the confirmatory holdout period can be fully
specified and locked right now, with no waiting required for new data to
accumulate -- unlike GEX, this experiment could actually run soon once
approved, not months from now.
"""

from experiment_config import ExperimentConfig

# ---------------------------------------------------------------------------
# DATA AVAILABILITY CHECK -- performed 2026-09-21, BEFORE writing this config,
# id-date-safe throughout (unlike the pre-existing eodhd_audit_term_structure.py,
# which used tradetime -- a real methodology gap in that older, single-date,
# single-ticker audit, corrected here).
#
# Universe coverage (3 sample dates spanning V1's window: 2026-06-11,
# 2026-07-22, 2026-09-08; all 6 tickers): 18/18 (ticker, date) pairs had a
# real, matched-strike, id-date-safe term-structure slope computable --
# at least one real expiration in the near bucket (7-16 DTE) and at least
# one in a wider far-proxy bucket (31-60 DTE, see note on bucket width
# below), with common strikes between them (no interpolation needed for
# these samples, though interpolation would be a legitimate fallback per
# the original audit's own finding).
#
# Date-range extent (AAPL only, spot-checked): real id-date-clean records
# exist at 2026-01-15, 2026-03-01, 2026-04-01, 2026-05-01, 2026-05-15
# (all BEFORE V1's window) and 2026-09-15, 2026-09-18 (AFTER V1's window,
# through the most recent available trading days as of this check).
#
# CAVEAT, stated honestly: the 18/18 coverage check used a FAR bucket of
# 31-60 DTE as a feasibility proxy, slightly wider than this config's
# actual 30-45-day definition below. A 30-45-day window is a subset of
# what was checked and options are not always listed at fine enough
# increments to guarantee a hit in every 15-day sub-window on every single
# day -- coverage for the EXACT 30-45 bucket has not been exhaustively
# confirmed and should be reconfirmed as part of Stage 1's actual run, not
# assumed. This is flagged, not glossed over.
# ---------------------------------------------------------------------------

NOTES = (
    "PRE-REGISTRATION DRAFT, not yet submitted. Second parallel experiment "
    "alongside gex_callwall_distance_v1_20260921 (GEX stays in its own "
    "wait-and-monitor phase, untouched by this). "
    "Unlike GEX, both stages use already-existing historical EODHD data -- "
    "no forward-collection wait required. Stage 1 (train/primary): "
    "2026-01-15 to 2026-06-10, entirely BEFORE V1's frozen window, chosen "
    "specifically so this hypothesis's evidence is independent of anything "
    "already examined via V1/V2/Phase 6/Phase 7. Stage 2 (test/holdout): "
    "ROLLING window starting 2026-09-10 (fixed, = V1 window end+1), entirely "
    "AFTER V1's window -- genuinely a second, separate out-of-sample window, "
    "not a split within the same period. "
    "CORRECTED 2026-09-21 (caught by explicit user review before Stage 1 was "
    "touched): this Stage 2 window was originally specified as a HARDCODED "
    "LITERAL end date (2026-09-18), which is a real design flaw -- a frozen, "
    "hashed config can never grow a literal past date no matter how long you "
    "wait, silently breaking the entire 'wait for more data' plan. Fixed to a "
    "genuinely rolling definition (parameters.stage2_window_definition): fixed "
    "start, open end determined at execution time via a data-EXISTENCE check "
    "only (never by peeking at the slope-vs-return result), stopping once "
    "N>=100 is reached and then locking that exact realized set for one test. "
    "As of 2026-09-21, directly reverified: only 7 real trading days exist in "
    "this window (2026-09-10 through 2026-09-18) -- zero new trading days have "
    "appeared since the original check (weekend, plus 2026-09-21's own EODHD "
    "data not yet published as of this check -- likely a next-business-day "
    "publishing lag). Max ~42 raw candidates, still far below the N>=100 "
    "threshold -- the wait is real and has not progressed yet, exactly as "
    "expected only 3 calendar days after the original design. "
    "COVERAGE CAVEAT: the 30-45 DTE far-bucket's exact coverage has only "
    "been proxy-checked via a wider 31-60 DTE window (18/18 sample pairs "
    "positive) -- true 30-45-day coverage should be reconfirmed when Stage "
    "1 actually runs, not assumed from this proxy. "
    "SECOND CORRECTION, 2026-09-21, before Stage 1 execution: the original "
    "slope_definition left 'the chosen near and far expirations' undefined "
    "when multiple fall in a bucket (the common case, not rare). Also left "
    "the realized-volatility formula unspecified. Both pinned now as explicit "
    "parameters (expiration_selection_convention, matched_strike_tiebreak, "
    "realized_volatility_formula) BEFORE running Stage 1, using the EXACT "
    "convention already validated by the coverage-feasibility check -- not a "
    "newly-invented choice made after seeing this ambiguity. "
    "SCOPE NOTE: this hypothesis is NOT conditioned on V1's entry signal "
    "(unlike the GEX call-wall-distance experiment) -- the population is "
    "all valid trading days for the 6-ticker universe with a computable "
    "term-structure slope, independent of whether V1 would have fired an "
    "entry that day."
)

# HASH HISTORY: ... -> 09bc383803cbbabe4141752c3ba66d023e91923e6a4f6975b7805a946ee653e4
# (nearest-strike fallback pinned, 2026-09-22) -> bfa05fe93667de8d199cb2d9034a3bab51d307c4f546be7dac62f860ebf43bcc
# (2026-10-01: min_n_definition clarified to distinct pooled days, alpha_per_test_one_sided made
# explicit, stage2_locked_test_and_exploratory_rule added). Stage 1 results were known at that time;
# no Stage 2 data existed (0 rows). The hypothesis, test, thresholds and robustness checks are unchanged.
# v2 (2026-10-01, NEW experiment_id iv_term_structure_slope_v2_20261001, superseding v1's bfa05fe9...):
# Stage-2 N raised 100 -> 139 via a new min_n_stage2 field; Stage 1's min_n_per_stage=100 unchanged.
# Still 0 Stage 2 rows. v2 hash: 1426199993aea7e934c8c15be8e0d8eb4cea7437fe8b6ea170c2afb784509647
# (registered 2026-10-01T21:15:38Z; also in CLAUDE.md Section 33 and the registry).
config = ExperimentConfig(
    experiment_id="iv_term_structure_slope_v2_20261001",
    experiment_type="signal_research",
    hypothesis=(
        "A steeper (more positive, i.e. more upward-sloping / contango) IV term-structure "
        "slope -- far-dated IV minus near-dated IV at a matched strike -- predicts LOWER "
        "subsequent realized volatility over the following 20 trading days; conversely, an "
        "inverted (negative, backwardated) slope predicts HIGHER subsequent realized "
        "volatility. This follows standard vol-term-structure theory (contango associated "
        "with calm/low-uncertainty regimes, inversion associated with anticipated near-term "
        "event risk) applied here as a specific, falsifiable prediction, independent of V1's "
        "entry signal and independent of the separate GEX call-wall-distance mechanism."
    ),
    research_question=(
        "Does the IV term-structure slope at a given date carry predictive information "
        "about subsequent realized volatility for this project's 6-ticker universe, "
        "measured on data entirely outside V1's own analyzed window?"
    ),
    dataset_version="eodhd_term_structure_v1_two_window_split",
    date_range=("2026-01-15", "2026-09-21"),  # known data span AS OF preregistration time (2026-09-21); Stage 2's actual end date will grow past this as real trading days accumulate -- see test_period and parameters.stage2_window_definition below for how that's handled without re-hardcoding a stale literal
    universe=["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"],
    option_type="call",  # matched-strike calls only, for consistency with this project's existing calls-focused conventions; puts not examined here
    features_used=[
        ("term_structure_slope_pct", "1.0"),
    ],
    parameters={
        "near_bucket_dte": [7, 16],
        "far_bucket_dte": [30, 45],  # the user's exact specification; NOTE the feasibility check above used a wider 31-60 proxy, see NOTES
        "slope_definition": "far_IV - near_IV at the matched strike closest to the median of the common-strike intersection between the chosen near and far expirations; id-date-safe (never tradetime), never interpolated across strikes unless no common strike exists, in which case the observation is excluded, never fabricated",
        "expiration_selection_convention": (
            "PINNED 2026-09-21, before Stage 1 execution, to close a real ambiguity the "
            "original config left unresolved (which expiration to use when multiple exist "
            "in a bucket -- common, not an edge case: e.g. AAPL 2026-07-22 had 5 near-bucket "
            "and 2 far-bucket expirations). Uses the EXACT convention already validated in "
            "the coverage-feasibility check (18/18 pairs), not a new/different choice: NEAR "
            "= the SOONEST expiration within [7,16] DTE (sorted ascending by exp_date, take "
            "index 0 -- closest to 7 DTE). FAR = the LATEST expiration within [30,45] DTE "
            "(sorted ascending, take index -1 -- closest to 45 DTE). This is the WIDEST-SPREAD "
            "convention, not nearest-to-boundary -- confirmed by re-reading the coverage "
            "check's actual code, not assumed from memory."
        ),
        "matched_strike_tiebreak": "sorted(common_strikes)[len(common_strikes)//2] -- lower-middle for an even-sized intersection, exact median for odd -- same convention already used in the coverage-feasibility check",
        "nearest_strike_fallback_mechanic": (
            "PINNED 2026-09-22, before running this specific robustness-check variant, "
            "confirmed explicitly by user (closed a real ambiguity -- the config's own "
            "name for this check, 'nearest_strike_fallback_vs_exact_match_only', did not "
            "specify the mechanics on its own). Applies ONLY to the "
            "nearest_strike_fallback_vs_exact_match_only robustness check -- the PRIMARY "
            "Stage 1 rule (slope_definition above: exclude when no common strike exists) "
            "is UNCHANGED for the main run. For this variant only: when the near and far "
            "expirations (selected via the same expiration_selection_convention as the "
            "primary run) share NO common strike, select whichever near-strike/far-strike "
            "PAIR minimizes the absolute gap |near_strike - far_strike| across all "
            "available near-strike x far-strike combinations, and use their raw quoted "
            "IVs directly for the slope. No interpolation, no independent nearest-to-spot "
            "selection per expiration -- the minimal relaxation from the primary rule: "
            "same pairing philosophy, just 'closest match, even if not exact' instead of "
            "'exact match or exclude'. If multiple pairs tie for the minimum gap, the "
            "lower-strike-pair wins (deterministic, matches the lower-middle convention "
            "already used for matched_strike_tiebreak)."
        ),
        "realized_volatility_formula": "PINNED 2026-09-21: annualized standard deviation of daily log returns over the forward window (standard textbook definition) -- deliberately NOT this project's existing 'hybrid' EWMA-smoothed calculate_historical_volatility(), which was built for live pricing smoothing, a different purpose than a fresh statistical test",
        "target_metric": "realized_volatility_forward_20d",
        "target_horizons_bars": [10, 20, 50],
        "primary_horizon_bars": 20,  # matches Phase 6/GEX's primary horizon for comparability
        "secondary_horizons_bars": [10, 50],
        "primary_test": "monte_carlo_day_clustered_one_sided",  # reuses Phase 6's already-validated methodology, not re-derived
        "monte_carlo_replicates": 1000,
        "min_n_per_stage": 100,  # v2: now governs STAGE 1 ONLY (already executed: 101 days, passed). Stage 2 uses min_n_stage2.
        # v2 (2026-10-01): power-driven increase for the PENDING Stage 2 test only (user decision).
        "min_n_stage2": 139,
        "min_n_stage_split": (
            "v2, 2026-10-01: the N requirement is SPLIT BY STAGE. Stage 1 (historical, already executed, "
            "101 distinct days, PASSED, SUGGESTIVE) stays governed by min_n_per_stage = 100, unchanged. "
            "The locked Stage 2 test is governed by min_n_stage2 = 139 (was 100 in v1), raised before any "
            "Stage 2 data existed because N=100 gave only 76% power at Stage 1's own r=0.28 (65% at r=0.25); "
            "N=139 gives 89% at r=0.28 and 80% at r=0.25. This is NOT 'N raised to 139 across the board'. "
            "The definition of N (min_n_definition: distinct pooled days) is unchanged."
        ),
        # CLARIFIED 2026-10-01 (clarifies, does not change, the original intent): the original
        # text called N "joined N (valid, slope-computable ticker-day observations)", which could
        # be read as total rows summed across tickers. Resolved to the day-clustered N that the
        # primary test (monte_carlo_day_clustered_one_sided) actually treats as its unit, that
        # Stage 1 used ("536 raw / 101 day-clustered", CLAUDE.md Section 33), and that
        # generate_iv_termstructure_stage2_dataset.py already logs (COUNT(DISTINCT obs_date)).
        "min_n_definition": (
            "N = number of DISTINCT trading days with at least one valid, slope-computable "
            "observation (any of the 6 tickers), pooled across tickers -- NOT total rows summed "
            "across tickers, and NOT a per-ticker minimum. Applies to both stages: Stage 1 must reach "
            "min_n_per_stage (100; Stage 1 had 101 distinct days, passes) and Stage 2 must reach "
            "min_n_stage2 (139, v2). Clarified 2026-10-01; threshold split by stage in v2."
        ),
        "supersedes": "iv_term_structure_slope_v1_20260921 (registered hash bfa05fe93667de8d199cb2d9034a3bab51d307c4f546be7dac62f860ebf43bcc). Stage 1 (executed 2026-09-21, SUGGESTIVE) carries over unchanged; v1's Stage 2 was never run (0 rows). Superseded 2026-10-01 by a power-driven Stage-2 N increase (100 -> 139).",
        "bonferroni_family_size": 3,  # 3 horizons tested (10/20/50-day)
        "alpha_uncorrected": 0.05,
        "alpha_per_test_one_sided": 0.05 / 3,  # = 0.0167; made explicit 2026-10-01 (already stated in DECISION_RULES)
        "stage2_locked_test_and_exploratory_rule": (
            "ADDED 2026-10-01; v2 target 139. The confirmatory primary test runs ONCE, on the night the 139th "
            "distinct Stage-2 observation day becomes available (earliest: night of 2027-06-10, "
            "session #189 from the fixed 2026-09-10 start, i.e. observation day #139 = 2027-03-31; "
            "later if any whole day has no valid observation or a nightly run fails). Any look at "
            "Stage-2 data before that is EXPLORATORY ONLY: it must not run the formal primary "
            "significance test, must not be used to accept/reject the hypothesis, must not be "
            "reported as a result, and must not influence the design, robustness checks, or "
            "decision rules. Anything from such a look must be labeled 'EXPLORATORY -- NOT THE "
            "PRE-REGISTERED TEST' wherever it appears (logs, output files, CLAUDE.md)."
        ),
        "effect_size_threshold_correlation": 0.15,  # minimum |correlation| between slope and forward realized vol to count as economically meaningful, not just statistically detectable
        "coverage_confirmed_via_sample": "18/18 (ticker, date) pairs across 6 tickers x 3 dates spanning V1's window, using a 31-60 DTE far-bucket proxy -- see NOTES for the 30-45 exact-bucket caveat",
        "data_extent_confirmed": "AAPL spot-checked at 2026-01-15, 2026-03-01, 2026-04-01, 2026-05-01, 2026-05-15 (before Stage 1 start) and 2026-09-15, 2026-09-18 (within Stage 2) -- all returned real id-date-clean records",
        "stage2_window_definition": (
            "ROLLING, not a fixed literal -- FIXED START 2026-09-10 (the day immediately "
            "after V1's frozen window ends), OPEN END determined at whatever moment Stage 2 "
            "is actually executed: query the real trading calendar for the most recent day "
            "with available EODHD data (via a data-EXISTENCE check only -- record count > 0 "
            "for that date -- never by computing or inspecting any slope/return value, so the "
            "stopping decision cannot be influenced by having peeked at the result). Continue "
            "accumulating trading days forward from 2026-09-10 until N -- the number of DISTINCT "
            "trading days with at least one valid, slope-computable observation (see "
            "min_n_definition; clarified 2026-10-01) -- reaches min_n_stage2=139 (v2; was 100). Once N>=139 "
            "is reached, LOCK the exact realized end-date and run the primary test ONCE against "
            "that locked set -- this is what keeps the design honest despite the boundary moving: "
            "the STOP is triggered by data volume alone, not by a favorable-looking result, and "
            "once triggered the set is frozen for the one test that follows."
        ),
        "stage2_confirmed_trading_days_as_of_20260921": 7,  # 2026-09-10, 11, 14, 15, 16, 17, 18 -- verified directly 2026-09-21; zero NEW trading days have appeared since 09-18 (weekend + today's 09-21 EODHD data not yet published as of this check, likely next-business-day publishing lag)
        "stage2_estimated_current_n_upper_bound": 42,  # 7 confirmed trading days x 6 tickers, BEFORE slope-computability filtering -- still far below min_n_per_stage=100
    },
    model_version=None,
    pricing_methodology="n/a_realized_volatility_prediction_only",  # this experiment predicts realized volatility of the UNDERLYING, not option P&L -- deliberately isolates the term-structure signal's own predictive content, same design choice as the GEX experiment
    execution_assumptions="none -- this experiment does not touch option pricing, spread, sizing, or execution; a separate follow-on experiment would be needed to translate any validated term-structure edge into an actual trading rule",
    train_period=("2026-01-15", "2026-06-10"),  # Stage 1, entirely pre-V1-window -- fixed, this boundary is a real design choice, not a data-availability constraint, so it stays literal
    validation_period=None,
    test_period=None,  # CORRECTED 2026-09-21 -- was hardcoded ("2026-09-10","2026-09-18"), a real bug: a frozen config with a literal past end-date can NEVER grow no matter how long you wait, silently breaking the "wait for more data" plan. Genuinely open-ended per parameters.stage2_window_definition above; None here for the same reason GEX's test_period is None -- the exact realized set isn't knowable at preregistration time.
    random_seeds=[42, 43],  # matches Phase 6/GEX's exact seed pair
    code_version="iv_termstructure_v2_draft",
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
    oos_validation_claimed=False,  # CORRECTED 2026-09-21 to match test_period=None -- ExperimentConfig itself refuses True with a None test_period (InvalidExperimentConfigError), which is the right refusal: the OOS design intent is real (see parameters.stage2_window_definition) but cannot be claimed as a locked, datable test_period the way GEX's original False/None pairing already correctly modeled
    declared_robustness_checks=[
        "leave_one_ticker_out", "alternate_horizon:10d", "alternate_horizon:50d",
        "alternate_far_bucket:31-60dte",  # cross-check against the exact bucket actually feasibility-tested, since 30-45 coverage is a caveat
        "nearest_strike_fallback_vs_exact_match_only",
    ],
)

# POWER ANALYSIS (added 2026-10-01). Deliberately OUTSIDE the ExperimentConfig, so it does not change
# the registered config hash. Standard field for all pre-registrations; see power_analysis.py.
# v2 (2026-10-01): recomputed at the Stage-2 lock N = 139. v1's N=100 figures were 26%/45%/65%/76%
# at r=0.15/0.20/0.25/0.28, MDE80 ~0.29 -- the reason for this version.
from power_analysis import power_table
POWER_ANALYSIS = power_table(
    n=139, alpha=0.05 / 3, rs=(0.15, 0.20, 0.25, 0.28), computed="2026-10-01 (v2)",
    note=("Stage 2 N = 139 distinct days (min_n_stage2; N definition unchanged, min_n_definition). "
          "Effective N is the day count, not the ticker-day count: Stage 1's r=-0.28 over 101 days gave "
          "p=0.001-0.002, matching the Fisher-z p for N=100, so the 6 tickers are highly correlated "
          "within a day. At N=139: 80% power at |r|=0.25, 89% at Stage 1's own 0.28. A REJECTED/"
          "INCONCLUSIVE still means 'no effect >= ~0.25 detected', not 'no effect >= 0.15'."),
)

DECISION_RULES = """
VALIDATED requires ALL of:
  1. Stage 1 N >= 100 (min_n_per_stage; N = DISTINCT trading days with at least
     one valid slope-computable observation, pooled across tickers -- see
     parameters.min_n_definition, clarified 2026-10-01) -- population is ALL
     valid trading days with a computable slope, not gated by V1's signal
  2. Stage 1 primary test (20-day horizon) significant at Bonferroni-corrected
     alpha = 0.05 / 3 = 0.0167, one-sided in the hypothesized direction
     (steeper slope -> lower forward realized vol)
  3. Effect size (|correlation|) >= 0.15
  4. Survives ALL declared robustness checks in the same direction
  5. Stage 2 (ROLLING window starting 2026-09-10, open end -- see
     parameters.stage2_window_definition; N >= 139 distinct days required
     (min_n_stage2, v2; was 100 in v1), stop-and-lock the moment that's
     reached, checked via data-existence only, never via peeking at the
     result) replicates the same direction. The primary test runs ONCE on the
     locked set (earliest night of 2027-06-10);
     any earlier look is EXPLORATORY ONLY per
     parameters.stage2_locked_test_and_exploratory_rule

REJECTED if:
  - Stage 1 N >= 100 but primary test not significant, or effect size below
    threshold, or direction reverses under any robustness check

INCONCLUSIVE if:
  - Stage 1 N < 100
  - Stage 1 passes but Stage 2 has not yet reached N >= 139 (v2; CURRENT STATE
    as of 2026-10-01: Stage 2 N = 0, lock earliest 2027-06-10. Original v1 note:
    as of 2026-09-21: only 7 confirmed trading days / ~42 raw candidates --
    re-check periodically as real trading days accumulate; the window is
    now genuinely rolling, so simply waiting and re-running the same
    existence check will correctly show growth once it happens, unlike the
    original hardcoded-literal version of this design)
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
print("run_experiment() -- registering this config into the real framework is a")
print("separate, deliberate future step, only after this draft is reviewed.")
print("=" * 100)

from dotenv import load_dotenv
load_dotenv()

"""
DRAFT pre-registration for a SPY-specific GEX/volatility hypothesis --
the fifth formal experiment in this project, and the first SPY-only one.
Scoped 2026-09-24, after the SPY historical GEX backfill (gex_metrics
covered SPY 2026-06-10 to 2026-09-21, 142 rows / 71 trading days,
verified independently against the DB, no truncation, no gaps, AS OF
THAT MOMENT).

CORRECTED 2026-09-24, same day, caught by explicit user review BEFORE
Stage 1 was touched -- a real window-staleness flaw, not a nitpick, and
already CONCRETELY MANIFESTED, not just theoretical: within the same
working session, gex_metrics grew to 146 rows / 73 trading days / through
2026-09-23 (SPY was added to GEX_Historical_Incremental_Update's ongoing
TICKERS list the same day). The original date_range/train_period below
were hardcoded literals reflecting the 71-day state at draft time -- the
EXACT bug class already caught and fixed once this session for IV term
structure's original test_period, and already fixed once for GEX call-
wall-distance's own Stage 1 dataset definition (CLAUDE.md Section 32: "no
result was ever computed against the original 748-row set... Stage 1's
dataset is hereby defined as the full historical gex_metrics table, not a
fixed snapshot... whatever it currently contains"). Same fix applied here,
same reasoning: no Stage 1 result has ever been computed against the
original 71-day snapshot, so redefining the window now is a pre-execution
construction correction, not a post-hoc reshuffle after a peek -- nothing
about this violates the no-retroactive-changes rule. date_range/
train_period below are updated to the table's actual extent AS OF THIS
CORRECTION (2026-06-10 to 2026-09-23, 146 rows / 73 distinct dates,
confirmed by direct query). Because SPY is now on the SAME nightly
incremental-update cadence as the 6 stocks (Section 43), this value WILL
continue to drift forward daily -- unlike the fixed-window 6-stock GEX
experiments (which hit a real data-availability ceiling at TRAIN_START),
there is no such ceiling here on the SPY side. This file's own
date_range/train_period must therefore be RE-VERIFIED against gex_metrics'
actual current SPY max immediately before Stage 1 is ever executed --
treat the value below as "current as of last update," never as
permanently locked from today, exactly the discipline call-wall-distance's
Stage 1 already established.

SECOND CORRECTION, 2026-09-24, same day, from an explicit independent
audit pass (not Stage 1 execution) -- two real, distinct bugs found and
fixed, plus one genuine market fact confirmed and disclosed (not a bug):

(a) COMPUTABLE-N OFF-BY-ONE, root-caused and fixed. The previously-stated
    figures (54/64/24 computable at the 20/10/50-day horizons) were each
    ONE TOO HIGH. Root cause: the Alpaca daily-bar calendar used to check
    forward-return computability included TODAY's bar even while the
    market was still open (confirmed via anomalously low volume on that
    bar vs. genuinely closed days, and the check's own UTC timestamp
    falling within regular market hours) -- a partial, still-forming
    session was being counted as a real, elapsed trading day, shifting
    every horizon's eligibility boundary by exactly +1. CORRECTED
    figures, reverified with today's incomplete bar properly excluded:
    53/73 computable at 20-day (primary), 63/73 at 10-day, 23/73 at
    50-day (all as of 2026-09-24 -- these will keep changing as both
    calendar time passes and the window itself grows, same caveat as
    the date-range correction above).

(b) near_opex_vs_far_opex WAS A STRUCTURAL NO-OP, root-caused and fixed,
    a DIFFERENT bug from the (a) figures above. The original mechanic
    (querying EODHD's live options chain for each observation date's
    real listed expirations, filtering expiration_type=='monthly') can
    only see expirations AT OR AFTER the observation date -- an already-
    expired contract has no queryable forward quotes -- so it could only
    ever detect UPCOMING OPEX proximity, never JUST-PASSED OPEX
    proximity, despite the parameter's own stated definition of "before
    or after." Confirmed empirically before assuming a fix was even
    needed: querying 2026-07-17 itself (a real monthly OPEX date) as the
    observation date incorrectly returned "nearest monthly OPEX =
    2026-08-21, 35 days away" instead of 0 -- and across all 73 real
    Stage-1 days, this asymmetry produced 0 NEAR / 72 FAR, a genuine
    structural no-op, not sampling noise (re-verified against the full
    population, not a sparse sample, before concluding this). FIXED by
    replacing the live-chain-query method entirely with a pure calendar
    computation (3rd Friday of the observation month, plus the months
    immediately before/after, minimum absolute distance) -- removes the
    forward-only bias structurally rather than patching around it, and
    needs no EODHD call at all for this specific check. Sanity-checked
    against EODHD's own confirmed "monthly" labels (2026-07-17,
    2026-08-21, 2026-09-18, 2026-10-16) before trusting it -- exact
    match. RE-VERIFIED against all 73 real days after the fix, not just
    trusted structurally: NEAR=31, FAR=42 (both buckets genuinely
    populate now), and the 2026-07-17 spot-check now correctly returns
    0 days away.

(c) put_wall_distance_pct's partial same-strike caveat -- CONFIRMED a
    real market fact, NOT a bug, left as-is and disclosed rather than
    "fixed" (there is nothing to fix): on ~9 of the 73 days,
    call_wall_strike and put_wall_strike happen to be the exact same
    strike (SPY's very liquid chain often clusters large OI at the same
    round-number strike on both sides) -- find_gamma_walls() computes
    each side's maximum completely independently (confirmed by direct
    code re-read), so this isn't a wiring bug, just a genuine empirical
    coincidence. On those specific days ONLY, put_wall_distance_pct is
    the exact negation of call_wall_distance_pct by construction
    (opposite subtraction order applied to the same strike) -- not
    independent evidence on those days specifically, though the
    robustness check as a whole remains meaningfully non-degenerate
    across the full 73-day sample (empirical cross-correlation -0.38,
    not -1.0). Recorded here explicitly so it isn't rediscovered as a
    surprise, or mistaken for a bug, later.

NEITHER (a) NOR (b) NOR (c) CHANGES WHETHER STAGE 1 CAN BE RUN YET --
both were about making this file's own stated numbers and mechanics
correct, not about clearing the min_n_per_stage=100 bar, which remains
unmet regardless (53 < 100 at the primary horizon, before and after
these fixes).

THIS FILE CONSTRUCTS AND PRINTS THE CONFIG FOR REVIEW ONLY. IT DOES NOT
CALL preregister_experiment() OR run_experiment() ANYWHERE. Per explicit
instruction: construction and hashing only. Stage 1 is NOT run here --
that is a separate, later, deliberate step.

WHY THIS IS GENUINELY DISTINCT FROM THE TWO REJECTED 6-STOCK GEX
EXPERIMENTS, NOT A RERUN OF EITHER:
  - Call-wall-distance (Section 32, REJECTED): tested |call_wall_distance_pct|
    (median-split, sign discarded) against forward RETURN LEVEL, pooled
    across 6 stocks, V1-gated. That specific signal-outcome pairing was
    rejected -- wrong direction, not significant.
  - Net gamma regime (Section 42, REJECTED): tested categorical gex_regime
    (sign preserved, but binary) against forward REALIZED VOLATILITY,
    pooled across 6 stocks, day-level unconditional population. Correct
    direction, insufficient strength.
  - THIS experiment: tests the SIGNED, CONTINUOUS call_wall_distance_pct
    (sign preserved, not collapsed to |distance|) against forward REALIZED
    VOLATILITY (not return level), on SPY only, with an explicit new
    theoretical mechanism (below) that is DIFFERENT from either prior
    hypothesis's mechanism -- not the same claim retested with the sign
    fixed, and not the same claim retested on a different ticker.

THEORETICAL MECHANISM, stated explicitly so this is falsifiable, not "a
GEX feature vs volatility, see what sticks" -- NEW REASONING, flagged as
such (not a direct literature citation, matching this project's Section
14 discipline for inferred-not-documented reasoning, same as Section 36's
precedent): a call wall sitting ABOVE spot (call_wall_distance_pct > 0)
represents a not-yet-reached concentration of dealer call-gamma -- price
has room to approach it, and the standard pinning mechanism (dealers long
gamma at that strike buying dips/selling rallies AROUND it) provides a
stabilizing, volatility-DAMPENING force as price nears it. A call wall
sitting BELOW spot (call_wall_distance_pct < 0) means price has already
moved PAST the region of peak call-gamma concentration -- the localized
stabilizing structure is now behind price rather than ahead of it, so
there is comparatively LESS resistance constraining further movement,
consistent with a "through the wall" / reduced-pinning configuration that
plausibly corresponds to HIGHER subsequent realized volatility. This
predicts a NEGATIVE correlation between call_wall_distance_pct and
forward realized volatility -- distinct from, and not derivable from,
either rejected hypothesis's own claim.

OPEX-PROXIMITY CONDITIONING -- DECIDED UP FRONT, STATED EXPLICITLY:
implemented as a STRATIFIED ROBUSTNESS CHECK (near-OPEX vs. far-OPEX
subsets, both rerun through the same primary test), NOT a required
pre-filter on the whole sample. Reasoning: SPY is a single ticker, so
Stage 1 N is structurally far smaller than the 6-stock experiments' pooled
N (there is no cross-ticker pooling to inflate it) -- a hard OPEX filter
would shrink an already-small sample further and risk INCONCLUSIVE by
construction rather than by genuine evidence. The stratified-check design
preserves the full Stage-1 N for the primary test while still directly
testing whether OPEX proximity matters, as requested.

HONEST FEASIBILITY DISCLOSURE, computed BEFORE any correlation is run,
same discipline as every prior pre-registration in this family: Stage 1
(current backfilled window, 73 trading days as of the 2026-09-24
correction above, growing nightly) is a single-ticker design, so its
day-clustered N is capped at the window's own day count -- there is no
multi-ticker pooling available to reach the min_n_per_stage=100 standard
used throughout the rest of this project's GEX/IV/strike-positioning
family. 73 < 100 (and raw day count is itself an OVER-estimate of what's
actually runnable today regardless -- forward returns need real elapsed
trading days: as of 2026-09-24, only 53/73 observations have a computable
20-day forward return, 63/73 for 10-day, 23/73 for 50-day (corrected from
an earlier off-by-one -- see the SECOND CORRECTION note above); the remainder
will resolve as calendar time passes, independent of whether new GEX
dates are also collected). If Stage 1 is run against the CURRENT dataset,
it is expected to return INCONCLUSIVE under decision rule item 1, not
because the design is flawed, but because a single-ticker window cannot
structurally reach the pooled-multi-ticker N this project has used
elsewhere, and because real time has not yet elapsed for many of the
window's own observations. min_n_per_stage is deliberately being KEPT at
100 here for family-wide comparability, rather than quietly lowered to
make Stage 1 easier to pass -- that would violate this project's own
no-manipulated-thresholds discipline. Whether to accept a lower,
explicitly-justified SPY-specific floor is a decision left for explicit
user review, not made unilaterally in this draft. Given the window now
grows nightly (Section 43), N>=100 is reachable through ordinary
accumulation over several more weeks, without needing that threshold
decision at all -- re-check gex_metrics' actual SPY count periodically
rather than assuming either outcome.

SEPARATE, DISCLOSED INFRASTRUCTURE GAP: Stage 2 (rolling, prospective)
requires ONGOING SPY data collection. SPY was deliberately NOT added to
GEX_Historical_Incremental_Update's TICKERS list (Section 40/the SPY
backfill work) -- that script's scan-start logic wouldn't have triggered
a genuine historical build for a brand-new ticker anyway, which is why a
dedicated one-time backfill script was built instead (gex_spy_historical_
backfill.py). That one-time script is NOT scheduled to run again. This
means: as of this draft, gex_metrics will NOT keep accumulating new SPY
rows going forward, and Stage 2 cannot begin accumulating until a SPY-
specific ongoing collection mechanism is built (a new, small addition --
not designed or built here, per explicit instruction to stop at the
pre-registration). Flagged now so it isn't discovered as a surprise when
Stage 2 is eventually attempted.
"""

from experiment_config import ExperimentConfig

config = ExperimentConfig(
    experiment_id="spy_gex_callwall_volatility_v1_20260924",
    experiment_type="signal_research",
    hypothesis=(
        "For SPY specifically, the SIGNED T-1 call-wall distance (call_wall_distance_pct = "
        "(call_wall_strike - spot_price) / spot_price * 100, sign preserved -- positive means "
        "the wall sits above spot, negative means price has already moved past the wall) is "
        "NEGATIVELY correlated with forward realized volatility: a wall above spot (positive "
        "distance, not yet reached) predicts LOWER subsequent realized volatility via localized "
        "dealer-hedging pinning; a wall below spot (negative distance, already passed through) "
        "predicts HIGHER subsequent realized volatility via reduced localized resistance. This "
        "is a directional, sign-dependent claim -- deliberately not the magnitude-only |distance| "
        "framing used by the rejected 6-stock call-wall-distance experiment (Section 32), and a "
        "different outcome variable (volatility, not return level) and different signal shape "
        "(continuous signed distance to a specific strike, not a binary aggregate regime) from "
        "the rejected 6-stock net-gamma-regime experiment (Section 42)."
    ),
    research_question=(
        "For SPY -- the underlying with by far the deepest, most liquid options chain and the "
        "signal construction SpyGammaLoop already trades on live -- does the SIGNED distance to "
        "the nearest call-gamma wall carry predictive information about forward realized "
        "volatility, and does this relationship depend on proximity to the nearest monthly "
        "options-expiration (OPEX) cycle?"
    ),
    # BUG FIX 2026-10-01 (CLAUDE.md Section 43): date_range / train_period / dataset_version were
    # hard-coded to end 2026-09-23, capping Stage 1 at 73 distinct days, so N>=100 could NEVER be
    # reached -- contradicting this file's own stated design ("N>=100 is reachable through ordinary
    # accumulation over several more weeks", "this WILL drift forward again"). Same bug class as IV
    # term structure's original hardcoded test_period (Section 33). Fixed by making the Stage-1 end
    # open and re-derived at execution time (parameters.stage1_window_definition), like IV's
    # rolling-window fix. This corrects the code to match its own documented intent; it is not a new
    # design decision. Hash: 1e84831a1e3daf2d77e7f7ce0d5889e1a02be9b7f502aaaaea50953cd3a38e99
#   -> c2629dc1e8aff9f3037a16894622e96c8681899b28ad4fd7d037ae3e004256c2 (2026-10-01; CLAUDE.md Section 43).
    dataset_version="spy_gex_metrics_v1_20260610_open_end_single_ticker",
    date_range=("2026-06-10", "OPEN_END_AT_EXECUTION"),  # fixed start; end is re-derived at execution per parameters.stage1_window_definition (was the stale literal "2026-09-23")
    universe=["SPY"],
    option_type="call",  # call_wall is a call-side construction; put_wall_distance_pct is tested only as a declared robustness check (below), not the primary feature
    features_used=[
        ("call_wall_distance_pct", "1.0"),
    ],
    parameters={
        "gex_source": "gex_lookup.py:get_gex_for_signal, sign_convention=model_a, field=call_wall_distance_pct (SIGNED, not absolute value)",
        "signal_qualification": "Day-level, unconditional -- one observation per SPY trading day, anchored at that day's market-open bar, no V1 gate, matching the already-established precedent from IV term structure (Section 33) and the corrected net-gamma-regime design (Section 42). Requires T-1 GEX available via gex_lookup.py (excluded, never substituted, if missing).",
        "single_ticker_note": "SPY only -- day-clustering as used elsewhere in this project (aggregate across tickers sharing a calendar day) does not apply here since there is only one ticker; each Stage-1 observation IS one calendar day. leave_one_ticker_out is consequently NOT a possible robustness check for this experiment -- see declared_robustness_checks below for the substitute set.",
        "target_metric": "realized_volatility_forward",
        "realized_volatility_formula": "REUSED VERBATIM from the IV term-structure experiment (CLAUDE.md Section 33), not reinvented: annualized standard deviation of DAILY log returns over the forward window, using SPY's own daily closes (Alpaca daily bars, same construction as backtest_engine.get_daily_regime() uses internally). Deliberately the DAILY-bar formula, not the 5-minute-bar formula used by the net-gamma-regime experiment (Section 42) -- explicit choice, per instruction to reuse IV term structure's construction directly.",
        "target_horizons_days": [10, 20, 50],
        "primary_horizon_days": 20,  # matches the rest of this project's GEX/IV-family primary horizon, for comparability
        "secondary_horizons_days": [10, 50],
        "primary_test": "day_clustered_pearson_correlation_plus_monte_carlo_permutation",  # REUSED VERBATIM from the IV term-structure Stage 1 construction (CLAUDE.md Section 33): day-clustered Pearson correlation (trivial day-clustering here, single ticker -- see single_ticker_note), null built by permuting the day-level pairing, one-sided in the hypothesized direction (NEGATIVE correlation)
        "monte_carlo_replicates": 1000,
        "min_n_per_stage": 100,  # KEPT at the family-wide standard deliberately, NOT lowered for this single-ticker design. Reachable only because the Stage-1 window now grows (stage1_window_definition, fixed 2026-10-01).
        "stage1_window_definition": (
            "ADDED 2026-10-01 (bug fix, replaces the stale literal train_period 2026-06-10..2026-09-23). "
            "ROLLING: FIXED START 2026-06-10, OPEN END re-derived at execution time from data existence "
            "only (SPY rows present in gex_metrics, and the latest fully closed NYSE trading day for "
            "forward-volatility computability) -- never from inspecting any distance-vs-volatility value. "
            "N = distinct SPY trading days with a computable call_wall_distance_pct AND a computable "
            "20-trading-day forward realized volatility (single ticker, so distinct days = observations). "
            "Stop and LOCK on the first night N>=100 is reached; run the primary test ONCE on that "
            "locked set. Any later Stage 2 must use only dates strictly after the locked Stage-1 end."
        ),
        "bonferroni_family_size": 3,  # 3 horizons tested (10/20/50-day), matching IV term structure and strike positioning
        "alpha_uncorrected": 0.05,
        "alpha_per_test_one_sided": 0.05 / 3,  # = 0.0167, made explicit 2026-10-01 (already the threshold in DECISION_RULES item 2)
        "framework_alpha_mismatch_note": (
            "ADDED 2026-10-01: the binding threshold is alpha_per_test_one_sided = 0.0167. The research "
            "framework's multiple_testing.compute_per_test_alpha() will return 0.05 for this experiment "
            "(testing_family_declaration=INDEPENDENT_SINGLE -> none_single_test), because it can only apply "
            "Bonferroni across separately registered experiments, not across one experiment's 3 horizons. "
            "Do NOT take the framework's multiple_testing_survived result at face value; evaluate it against 0.0167."
        ),
        "effect_size_threshold_correlation": 0.15,  # same threshold as IV term structure and strike positioning, for cross-hypothesis comparability
        "opex_proximity_definition": "CORRECTED 2026-09-24 (see SECOND CORRECTION in the module docstring) -- the original mechanic (live EODHD chain query, filtering expiration_type=='monthly') was forward-only-biased and produced a structural no-op (0 NEAR / 72 FAR across all 73 real Stage-1 days, confirmed empirically, not assumed). FIXED: near-OPEX = observation date is within 5 CALENDAR days (before OR after, genuinely bidirectional now) of the nearest monthly options-expiration date, computed via a PURE CALENDAR RULE -- the 3rd Friday of the observation date's own month, plus the 3rd Fridays of the immediately preceding and following months, minimum absolute distance -- no EODHD query needed for this specific check. Sanity-checked against EODHD's own confirmed expiration_type=='monthly' labels before trusting it (2026-07-17, 2026-08-21, 2026-09-18, 2026-10-16 -- exact match). far-OPEX = more than 5 calendar days away. RE-VERIFIED against all 73 real Stage-1 days after the fix: NEAR=31, FAR=42, both buckets genuinely populate; the 2026-07-17 spot-check (itself a real monthly OPEX date) now correctly returns 0 days away, not 35.",
        "opex_conditioning_method": "STRATIFIED ROBUSTNESS CHECK (near_opex_vs_far_opex, declared below), not a required pre-filter on the whole Stage 1 sample -- decided explicitly up front (see NOTES/docstring above) to avoid shrinking an already single-ticker-constrained sample.",
    },
    model_version=None,
    pricing_methodology="n/a_realized_volatility_prediction_only",  # predicts realized volatility of the underlying, not option P&L -- same isolation choice as IV term structure and net gamma regime
    execution_assumptions="none -- this experiment does not touch option pricing, spread, sizing, or execution; a separate follow-on experiment would be needed to translate any validated edge into an actual trading/sizing rule",
    train_period=None,  # BUG FIX 2026-10-01: was the stale literal ("2026-06-10", "2026-09-23") -- now rolling per parameters.stage1_window_definition (fixed start, open end at execution), same pattern as IV term structure's test_period=None. Original note: Stage 1 IS the full currently-backfilled SPY window -- no further split within it (unlike the 6-stock GEX-family split at TRAIN_END=2026-08-11), since splitting further would only worsen this design's already-disclosed single-ticker N constraint for no offsetting benefit (Stage 2 needs genuinely NEW data regardless of where Stage 1 ends)
    validation_period=None,
    test_period=None,  # Stage 2 is prospective/rolling and requires NEW SPY data collection that does not yet exist (see the disclosed infrastructure gap above) -- test_period cannot be dated in advance, matching the established correct pattern from every other experiment in this family
    random_seeds=[42, 43],  # matches this project's established seed pair
    code_version="spy_gex_callwall_volatility_v1_draft",
    testing_family_declaration="INDEPENDENT_SINGLE",
    applicability_lock=[
        ("data_integrity", True), ("lookahead_audit", True), ("timestamp_safety", True),
        ("sample_size_adequacy", False),  # KNOWN, DISCLOSED to likely fail at current N (73 raw / 53 computable at 20-day, as of 2026-09-24 -- corrected off-by-one, see SECOND CORRECTION) vs required 100 -- see feasibility note above
        ("statistical_testing", False), ("reproduction", False),
        ("primary_test_significant", False), ("effect_size_meets_threshold", False),
        ("multiple_testing_survived", False), ("robustness_survived", False),
        ("oos_survived", False),
        ("primary_performance_test_significant", False), ("concentration_check", False),
        ("pricing_accuracy_meets_threshold", False), ("pricing_coverage_meets_threshold", False),
    ],
    oos_validation_claimed=False,  # Stage 2 has not run, and cannot run yet -- see the disclosed infrastructure gap
    declared_robustness_checks=[
        "near_opex_vs_far_opex",       # stratified, genuinely functioning -- a real subsetting of the data, not a structural no-op (unlike sign_convention:flipped's proven no-op for wall-strike features, CLAUDE.md Section 32 -- deliberately NOT reused here for that reason)
        "alternate_horizon:10day", "alternate_horizon:50day",
        "alternate_signal:net_gex_normalized",   # genuinely distinct computation -- calculate_net_gex() DOES branch on sign_convention (unlike find_gamma_walls()), confirmed by direct code read (CLAUDE.md Section 42's finding) -- tests whether a differently-constructed, portfolio-wide signed GEX measure shows a consistent pattern, not a relabeling of the primary feature
        "alternate_signal:put_wall_distance_pct", # genuinely distinct computation overall (empirical cross-correlation with call_wall_distance_pct: -0.38 across all 73 real days, not -1.0/0) -- separate strike selection (put-side gamma concentration, not call-side), own sign convention (positive = put wall below spot, the "normal" configuration -- NOTE the opposite subtraction order from call_wall_distance_pct, confirmed by direct code read of gex_lookup.py). DISCLOSED PARTIAL CAVEAT (real market fact, not a bug -- confirmed 2026-09-24 audit): on ~9 of the 73 days, call_wall_strike==put_wall_strike exactly (SPY's liquid chain often clusters peak OI at the same round-number strike on both sides), and on those specific days put_wall_distance_pct is the EXACT NEGATION of call_wall_distance_pct by construction -- not independent evidence on those days specifically, though the check remains meaningfully non-degenerate across the full sample.
    ],
)

DECISION_RULES = """
VALIDATED requires ALL of:
  1. Stage 1 day-clustered N >= 100 (min_n_per_stage) -- population is ALL
     valid SPY trading days with a computable call_wall_distance_pct and
     forward realized volatility, day-level, unconditional on V1's gate.
     Window is ROLLING from 2026-06-10 (parameters.stage1_window_definition,
     bug fix 2026-10-01); stop-and-lock on the first night N >= 100.
  2. Primary test (20-day horizon) significant at Bonferroni-corrected
     alpha = 0.05 / 3 = 0.0167, one-sided in the hypothesized direction
     (NEGATIVE correlation -- wall below spot predicts higher forward
     realized volatility)
  3. Effect size |correlation| >= 0.15
  4. Survives ALL 5 declared robustness checks (near_opex_vs_far_opex,
     both alternate horizons, alternate_signal:net_gex_normalized,
     alternate_signal:put_wall_distance_pct) in the same direction
  5. Stage 2 (prospective, requires new SPY data collection that does not
     yet exist -- see the disclosed infrastructure gap) replicates the
     same direction once N >= 100 is reached there too

REJECTED if:
  - Stage 1 N >= 100 but the primary test is not significant at the
    corrected alpha, OR effect size is below the 0.15 threshold, OR the
    direction reverses under any declared robustness check

INCONCLUSIVE if:
  - Stage 1 N < 100 (do not interpret whatever number comes out anyway.
    Do not run before N >= 100: as of 2026-10-01, N = 58 at the 20-day
    horizon; with the rolling window it is expected to reach 100 on the
    night of 2026-11-30 -- see CLAUDE.md Section 43)
  - Stage 1 passes but Stage 2 cannot yet be run (current state: Stage 2
    has no data-collection mechanism at all yet, not merely an
    insufficient N -- a strictly earlier-stage gap than any other
    experiment in this family has faced)
  - Stage 1 and Stage 2 (once both exist) disagree in direction without
    a pre-specified tiebreaker (none specified here -- a genuine conflict
    would require a NEW, separately pre-registered follow-up)
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
print("running Stage 1, are separate, deliberate future steps. NO DATA TOUCHED")
print("beyond the already-completed, independently-verified SPY backfill.")
print("=" * 100)

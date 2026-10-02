"""
Pre-registration, trial #13 in the program tally (CLAUDE.md Section 1, Section 63).
Created 2026-10-02. Takes the slot freed when the cross-sectional straddle hypothesis
(trial #12, Section 62) was HELD -- a deliberate reallocation approved by the user for this
specific replacement, not an automatic reopening of the slot.

HYPOTHESIS IN ONE LINE: the slope of the VIX term structure, ln(VIX3M / VIX) at the close before
each monthly SPX option roll, POSITIVELY predicts the next roll-to-roll excess return of the Cboe
S&P 500 Iron Condor Index (CNDR), a capped-loss, near-delta-neutral short-volatility strategy.
Upward slope (contango) -> larger short-vol returns; inverted slope -> smaller or negative.

USER DECISIONS LOCKED BEFORE REGISTRATION (2026-10-02, after reviewing the draft whose hash was
06090007f3980de297a8c354367279a661b8bc2d14bbb3ea04f80721dfa34e71; that draft was never registered):
  1. Robustness strictness: at most ONE of the 13 sign-only robustness checks may fail direction,
     EXCEPT subsample:post_johnson_sample_2014plus, which must always pass. The vrp_control_gate
     (the volatility-control check) must always pass. A failure of either is an automatic REJECTED,
     whatever the other checks show.
  2. Stage 2 is DIRECTIONAL / INFORMATIVE ONLY, not a pass/fail gate. SUGGESTIVE is the ceiling of
     what this pre-registration can establish; the Stage 2 result is reported, never used to
     upgrade or downgrade the verdict mechanically (parameters.stage2, DECISION_RULES).
  3. Primary payoff: CNDR, not BFLY (the draft's primary). BFLY becomes a robustness payoff. The
     user's reasons: CNDR is the realistic analog of what would be traded (mini-SPX / XSP iron
     condors), needs less active management (OTM shorts can decay to expiry, vs BFLY's constant
     near-the-money risk), and the user reports a much smaller historical max drawdown (CNDR 19%
     vs BFLY 47.1%). Those drawdown figures are user-reported and were NOT verified here: verifying
     them would mean computing the target series, which this pre-registration avoids before
     locking. The choice uses unconditional properties of the payoff only, never its relation to
     the signal. Disclosed so it cannot be read as a post-hoc payoff switch.
  4. alpha = 0.05 one-sided: a single primary test at a single horizon, so the project's
     0.05/3 Bonferroni (used for 3-horizon designs) does not apply.

WHY THIS AND NOT ANOTHER REALIZED-VOL FORECAST: the IV Stage 1 economic check (Section 33) and
Target C's retirement (Section 60) showed that predicting realized vol mostly recovers the
already-priced IV level. A vol seller is paid realized MINUS implied. This experiment's target is
the return of a tradeable vol-selling strategy, so a pass is directly about the payoff.

LITERATURE BASIS (not invented ad hoc): Johnson (2017, JFQA 52(6) 2461-2490), "Risk Premia and
the VIX Term Structure": SLOPE (2nd principal component of the VIX term structure) "negatively
predicts future returns of 18 variance assets" (variance swaps, VIX futures, S&P 500 straddles;
long-volatility returns), i.e. POSITIVELY predicts short-volatility returns; next-month extreme-
quintile spreads of 8-37%; effect concentrated in the lowest SLOPE quintile, where long-variance
returns turn positive; SLOPE is incremental to VIX LEVEL and to implied-minus-expected variance;
sample 1996-2013. This experiment uses a simple geometric slope rather than a PC (Johnson reports
his results hold with "alternate geometric definitions of SLOPE"), a different payoff (Cboe CNDR,
a capped-loss short strangle with long wings), and a mostly post-publication sample (153 of 203 cycles start
2014 or later). See LITERATURE_CHECK below for the full baseline/control review.

WHAT HAS BEEN LOOKED AT BEFORE LOCKING (data-existence only, same discipline as every prior
pre-registration): series date coverage and missing-day counts; the number of cycles with both
signal and return endpoints present (scratchpad script vrp_feasibility.py, 2026-10-02). NO slope
value, NO index return, NO relationship between them has been computed or viewed. Disclosed
contamination that cannot be avoided: the market history (2008, 2018 "Volmageddon", 2020) and the
published literature are public knowledge, and the hypothesis direction was taken from Johnson.

Importing or running this file only constructs and prints the config; it never calls
preregister_experiment() or run_experiment(). Registration in research_database.db was done once,
separately, after user approval (CLAUDE.md Section 63 records the timestamp and hash).
"""
from experiment_config import ExperimentConfig

CBOE_CSV = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{SYMBOL}_History.csv"
TREASURY_CSV = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
                "daily-treasury-rates.csv/{YEAR}/all?type=daily_treasury_bill_rates")

config = ExperimentConfig(
    experiment_id="vix_termstructure_vrp_index_timing_v1_20261002",
    experiment_type="signal_research",
    hypothesis=(
        "The VIX term-structure slope, ln(VIX3M/VIX) at the close of the trading day before each "
        "monthly SPX option roll date, is POSITIVELY rank-correlated with the next roll-to-roll "
        "excess return (over 4-week T-bills) of the Cboe S&P 500 Iron Condor Index (CNDR). An "
        "upward-sloping term structure predicts larger returns to selling short-dated index "
        "volatility; an inverted one predicts smaller or negative returns. The relation is "
        "incremental to the VIX level and to the variance-risk-premium proxy VIX^2 minus trailing "
        "realized variance (Johnson 2017, JFQA)."
    ),
    research_question=(
        "Does the VIX term structure tell a seller of short-dated S&P 500 volatility WHEN the "
        "volatility risk premium is worth harvesting, beyond what the VIX level and the current "
        "implied-minus-realized gap already say, in a sample mostly after the original publication?"
    ),
    dataset_version=(
        "cboe_vix_vix3m_vix6m_spx_bfly_cndr_put_bxm_daily_csv_plus_treasury_4wk_bill_v1; frozen at "
        "execution as a local snapshot whose per-file SHA-256 is recorded with the result "
        "(closes the dataset_version gap noted in CLAUDE.md Section 1)"
    ),
    date_range=("2009-10-15", "2026-09-17"),  # first signal date (VIX3M history starts 2009-09-18) -> end of the last cycle complete before drafting
    universe=["SPX_index_options_via_cboe_strategy_indices"],
    option_type="index_strategy",
    features_used=[
        ("vix_ts_slope_ln_vix3m_over_vix_t_minus_1", "1.0"),
        ("ln_vix_level_t_minus_1", "1.0"),          # control (vrp_control_gate), not a second signal
        ("vrp_proxy_vix2_minus_rv21_t_minus_1", "1.0"),  # control (vrp_control_gate), not a second signal
    ],
    parameters={
        "data_sources": {
            "cboe_daily_history_csv": CBOE_CSV + " for VIX, VIX3M, VIX6M, SPX, BFLY, CNDR, PUT, BXM (free, no key)",
            "treasury_4wk_bill": TREASURY_CSV + ", column '4 WEEKS COUPON EQUIVALENT' (free, no key)",
            "coverage_checked_2026_10_02": (
                "VIX 1990->, VIX3M 2009-09-18->, VIX6M 2008-01-02->, SPX 1975->, BFLY/CNDR 1986-06-20->, "
                "PUT 1991->, BXM 2002->; all through 2026-10-01. BFLY/CNDR/BXM each miss 2018-12-03, "
                "2019-07-05, 2020-10-16; none of these is a cycle endpoint."
            ),
        },
        "cycle_definition": (
            "Roll date R_k = third Friday of month k, or the preceding Cboe business day if that Friday "
            "is an exchange holiday (CNDR and BFLY methodologies, identical rule; e.g. 2014-04-17, 2026-06-18). Signal date "
            "S_k = the trading day before R_k. Cycle k runs from the close of S_k to the close of "
            "S_{k+1}. Trading days = dates present in Cboe's SPX history file. A roll date in the "
            "future is never inferred (the drafting check's fake 2026-10-01 'roll' is the bug class "
            "to avoid: a cycle needs both real endpoints)."
        ),
        "signal": "slope_k = ln(VIX3M_close(S_k) / VIX_close(S_k)). Positive = upward-sloping (contango).",
        "target": (
            "excess_return_k = CNDR(S_{k+1}) / CNDR(S_k) - 1 - rf_k, where rf_k = 4-week T-bill coupon-"
            "equivalent yield on S_k (or the latest prior Treasury business day) x (calendar days from "
            "S_k to S_{k+1}) / 365. Excess return is required because CNDR (like BFLY) holds T-bills "
            "equal to 10x the options' maximum possible loss, so the T-bill rate is a large share of "
            "its raw return and rates move slowly with the volatility regime. CNDR = short ~0.20-delta "
            "SPX put and call, long ~0.05-delta put and call, monthly, AM-settled (Cboe CNDR methodology)."
        ),
        "primary_payoff_choice": (
            "CNDR (user decision 2026-10-02, replacing the draft's BFLY before registration): the "
            "realistic analog of a tradeable XSP iron condor, less active management than BFLY's "
            "at-the-money shorts, and a user-reported smaller historical max drawdown (CNDR 19% vs BFLY "
            "47.1%; not verified here, since that would mean computing the target series before "
            "locking). Chosen on unconditional payoff properties only, never on the signal relation."
        ),
        "timing_and_lookahead": (
            "Everything in the signal and controls is known at the S_k close; BFLY sets its new strikes "
            "before 11:00 ET on R_k. The return window includes the final overnight of the expiring "
            "position (S_k close -> R_k SOQ), and excludes the final overnight of the new position "
            "(S_{k+1} close -> R_{k+1}); disclosed, not adjusted. CNDR, like BFLY, sets strikes before "
            "11:00 ET on R_k."
        ),
        "stage1_window": "203 complete cycles: signal dates 2009-10-15 .. 2026-08-20, last cycle ending 2026-09-17. Historical and closed (no rolling end).",
        "min_n_per_stage": 180,  # Stage 1 has 203; the floor only guards against a data-loading failure
        "primary_test": (
            "Spearman rank correlation between slope_k and excess_return_k over the Stage 1 cycles. "
            "Null: 10,000 permutations of the cycle pairing, seeds [42, 43]; one-sided p = share of "
            "permuted rho >= observed rho. Non-overlapping cycles, so no Newey-West adjustment applies. "
            "Spearman is primary because short-volatility returns are fat-tailed and left-skewed and a "
            "verdict should not hinge on a few crash months; Pearson is a declared robustness check."
        ),
        "bonferroni_family_size": 1,  # one payoff, one horizon, one statistic are primary; everything else is robustness
        "alpha_uncorrected": 0.05,
        "alpha_per_test_one_sided": 0.05,
        "effect_size_threshold_spearman": 0.15,  # family-wide floor, same as IV / SPY GEX
        "vrp_control_gate": {
            "status": "MANDATORY, equal priority to the primary test (same standing as SPY GEX v3's volatility_control_gate).",
            "controls": (
                "(a) ln(VIX_close(S_k)); (b) VRP proxy = (VIX_close(S_k)/100)^2 - 252 x mean of squared "
                "daily SPX log returns over the 21 trading days ending S_k (Bollerslev, Tauchen & Zhou 2009)."
            ),
            "test": (
                "Partial Spearman: rank-transform slope, target and both controls; residualize the slope "
                "ranks and the target ranks on the two control ranks by OLS; correlate the residuals. Null: "
                "10,000 permutations of the residual pairing, seeds [42, 43], one-sided."
            ),
            "pass_condition": "Partial correlation POSITIVE and significant at 0.05 one-sided (both seeds).",
            "interpretation_if_it_fails": "Any slope effect is attributed to the volatility level or the current VRP -> REJECTED.",
        },
        "robustness_rule": (
            "Pinned in advance (user decision 2026-10-02) to avoid the IV Stage 1 ambiguity (Section 33). "
            "The vrp_control_gate is not one of the sign checks: it must be significant (see its "
            "pass_condition), and its failure is an automatic REJECTED. The other 13 declared checks are "
            "SIGN-ONLY: each passes if its statistic has the HYPOTHESIZED SIGN, without needing independent "
            "significance; oos_r2_vs_historical_mean passes only if OOS R^2 > 0. AT MOST ONE of these 13 may "
            "fail, and that one may NOT be subsample:post_johnson_sample_2014plus, whose failure is an "
            "automatic REJECTED regardless of the others. Two or more failures -> REJECTED."
        ),
        "sign_checks_count": 13,
        "max_sign_check_failures_allowed": 1,
        "sign_checks_that_must_always_pass": ["subsample:post_johnson_sample_2014plus"],
        "gates_that_must_always_pass": ["vrp_control_gate:partial_spearman_ln_vix_and_vrp_proxy"],
        "robustness_definitions": {
            "alternate_payoff": "Primary test with BFLY, PUT, BXM excess returns in place of CNDR. BFLY (short ATM straddle, 5%-OTM wings) was the draft's primary. PUT/BXM carry large equity beta (AQR: Israelov & Nielsen), so they are consistency checks, not cleaner tests.",
            "alternate_statistic:pearson": "Pearson correlation, same data.",
            "alternate_signal:ln_vix6m_over_vix_from_2008": "Signal ln(VIX6M/VIX), cycles from the first signal date with VIX6M (2008-01-17): 224 cycles, adds the 2008 crisis.",
            "subsample:post_johnson_sample_2014plus": "Cycles with S_k >= 2014-01-01 (153): outside Johnson's 1996-2013 sample.",
            "subsample:post_index_launch_2015_08plus": "Cycles with S_k >= 2015-08-03 (134): CNDR and BFLY were both launched 2015-08-03; earlier values are Cboe back-tests.",
            "nonlinearity:bottom_quintile": "Expanding-window quintile cut (first 36 cycles as burn-in, cutoff from past slopes only): mean excess return in bottom-quintile cycles minus all other cycles; hypothesized sign NEGATIVE (Johnson's concentration in the lowest SLOPE quintile).",
            "oos_r2_vs_historical_mean": "Goyal & Welch (2008) / Campbell & Thompson (2008): from cycle 61 on, forecast with an expanding-window OLS of return on slope, benchmark = expanding historical mean (the 'always sell' baseline); pass if OOS R^2 > 0.",
            "stambaugh_bias_corrected": "Amihud & Hurvich (2004) augmented-regression slope coefficient for the persistent predictor; hypothesized sign POSITIVE.",
            "partial_control:lagged_own_return": "Partial Spearman controlling for the previous cycle's CNDR excess return (practitioner momentum claim); hypothesized sign POSITIVE.",
            "drop_top5_abs_return_cycles": "Primary test without the 5 cycles with the largest |excess return| (concentration check, cf. V1's Phase 7).",
            "alternate_null:stationary_block_bootstrap": "p-value from a stationary block bootstrap (mean block 6 cycles) of the target, preserving volatility clustering; reported, sign rule applies to rho.",
        },
        "economic_check": (
            "Reported, NOT part of the verdict, but required before any trading use (Section 1). Timed "
            "strategy: hold CNDR in cycle k unless slope_k is below the expanding 20th percentile of past "
            "slopes (first 36 cycles burn-in), in which case hold T-bills. Report annualized excess "
            "return, Sharpe, max drawdown and worst cycle vs always-on CNDR, and the BREAK-EVEN round-trip "
            "cost per roll (as % of index value) at which the timed strategy's advantage disappears, "
            "compared with an estimate from real SPY/SPX quotes (EODHD end-of-day spreads, Section 26). "
            "Cboe values all option legs at bid-ask MIDPOINTS, so index returns exclude trading costs."
        ),
        "stage2": (
            "DIRECTIONAL / INFORMATIVE ONLY -- NOT A PASS/FAIL GATE (user decision 2026-10-02). Cycles "
            "whose signal date S_k is strictly after the registration date; analyzed once, at N = 36 "
            "forward cycles (~3 years); earlier looks are exploratory only. Reported: Spearman rho, its "
            "sign, and its permutation p. It does NOT change this experiment's verdict in either "
            "direction: a same-sign Stage 2 does not upgrade SUGGESTIVE to VALIDATED, and an opposite-"
            "sign Stage 2 does not downgrade it. Reason: power at N = 36 is ~21% at rho = 0.15 and ~41% "
            "at 0.25 (POWER_ANALYSIS), so a pass/fail gate would mostly measure noise. SUGGESTIVE is "
            "the ceiling of this pre-registration; any stronger claim needs a NEW, separately pre-"
            "registered confirmatory test. This rule is fixed now so it cannot be reinterpreted later."
        ),
        "verdict_ceiling": "SUGGESTIVE",
    },
    model_version=None,
    pricing_methodology="cboe_strategy_index_values_mid_quote_no_costs_economic_check_adds_costs",
    execution_assumptions=(
        "none in the verdict -- the test uses Cboe index values (mid-quote, no costs); the economic "
        "check adds a break-even cost analysis; any live use needs its own sizing and execution work "
        "(e.g. XSP mini-SPX iron condors)"
    ),
    train_period=("2009-10-15", "2026-09-17"),
    validation_period=None,
    test_period=None,  # Stage 2 is prospective and rolling (parameters.stage2), so it cannot be dated now
    random_seeds=[42, 43],
    code_version="vix_termstructure_vrp_index_timing_v1",
    testing_family_declaration="INDEPENDENT_SINGLE",
    applicability_lock=[
        ("data_integrity", True), ("lookahead_audit", True), ("timestamp_safety", True),
        ("sample_size_adequacy", True), ("statistical_testing", True), ("reproduction", False),
        ("primary_test_significant", False), ("effect_size_meets_threshold", False),
        ("multiple_testing_survived", False), ("robustness_survived", False),
        ("oos_survived", False),
        ("primary_performance_test_significant", False), ("concentration_check", False),
        ("pricing_accuracy_meets_threshold", False), ("pricing_coverage_meets_threshold", False),
    ],
    oos_validation_claimed=False,
    declared_robustness_checks=[
        "vrp_control_gate:partial_spearman_ln_vix_and_vrp_proxy",  # MANDATORY gate
        "alternate_payoff:BFLY", "alternate_payoff:PUT", "alternate_payoff:BXM",
        "alternate_statistic:pearson",
        "alternate_signal:ln_vix6m_over_vix_from_2008",
        "subsample:post_johnson_sample_2014plus",
        "subsample:post_index_launch_2015_08plus",
        "nonlinearity:bottom_quintile",
        "oos_r2_vs_historical_mean",
        "stambaugh_bias_corrected",
        "partial_control:lagged_own_return",
        "drop_top5_abs_return_cycles",
        "alternate_null:stationary_block_bootstrap",
    ],
)

# POWER ANALYSIS -- outside the ExperimentConfig, so it never changes the hash (Section 1 convention).
from power_analysis import power_table, power_one_sided, mde_r

_SPEARMAN_N = lambda n: (n - 3) / 1.06 + 3  # Fieller-Hartley-Pearson: var(atanh rho_s) ~ 1.06/(n-3)
POWER_ANALYSIS = power_table(
    n=203, alpha=0.05, rs=(0.10, 0.15, 0.20, 0.25), computed="2026-10-02",
    note=("Pearson Fisher-z figures at N = 203 cycles (one observation per monthly cycle, so N is also "
          "the effective N). Primary statistic is SPEARMAN; with the 1.06 variance inflation: power "
          "39.5% / 66.7% / 87.3% / 96.9% at rho = 0.10 / 0.15 / 0.20 / 0.25, MDE at 80% = 0.179. "
          "Simulation check (4,000 draws per cell, persistent AR(1)=0.7 predictor, fat-tailed t(3) payoff "
          "with doubled left tail, Gaussian copula at the target Spearman rho): 40.4% / 68.0% / 87.5% / "
          "96.8%, matching the analytic figures. Plausible size: Johnson's next-month OOS R^2 for S&P "
          "straddles is ~2-10% (|r| ~0.14-0.32); CNDR's OTM shorts, capped wings and T-bill dilution "
          "may weaken the relation relative to ATM straddles. The vrp_control_gate (partial correlation, "
          "2 controls) has slightly less power. A REJECTED means 'no effect >= ~0.18 detected'. "
          "Must-pass sign check (post-2014 subsample, N = 153): chance its sign flips by noise when the "
          "true rho is 0.15 / 0.18 / 0.20 / 0.25 = 3.6% / 1.5% / 0.8% / 0.1%."),
)
POWER_ANALYSIS["spearman"] = {
    f"{n}": {"power_at_rho": {f"{r:.2f}": round(power_one_sided(r, _SPEARMAN_N(n), 0.05), 3)
                              for r in (0.10, 0.15, 0.20, 0.25)},
             "mde_at_80pct": round(mde_r(_SPEARMAN_N(n), 0.05), 3)}
    for n in (203, 153, 134, 36)
}  # 203 = Stage 1; 153 / 134 = the two required subsample checks (sign only); 36 = Stage 2 lock

# LITERATURE CHECK (2026-10-02, ~30 min) -- what each source implies for baselines and controls.
LITERATURE_CHECK = {
    "Johnson 2017 JFQA (read in full text)": "Sets the sign (SLOPE negatively predicts long-variance returns, so positively predicts short-vol). LEVEL does not predict; SLOPE is incremental to implied-minus-expected variance -> vrp_control_gate. Effect concentrated in the lowest quintile -> nonlinearity check. Reports OOS R^2 -> oos_r2 check. Sample 1996-2013 -> post-2014 subsample.",
    "Bollerslev, Tauchen & Zhou 2009 RFS": "VIX^2 minus realized variance is the standard VRP proxy -> control (b).",
    "Goyal & Welch 2008 RFS; Campbell & Thompson 2008": "In-sample predictors often fail out of sample against the historical mean -> oos_r2_vs_historical_mean, with 'always sell' as the baseline.",
    "Stambaugh 1999; Amihud & Hurvich 2004": "Persistent predictors bias predictive-regression slopes -> stambaugh_bias_corrected.",
    "Simon & Campasano 2014 (VIX futures basis)": "Contango predicts short-VIX-futures profits, robust to costs; equity-beta hedging mattered -> corroborates the sign; motivates a near-delta-neutral primary payoff (CNDR; BFLY as a check) over PUT/BXM.",
    "AQR (Israelov & Nielsen 2014/2015; 'Understanding the VRP' 2018)": "PUT/BXM returns mix equity beta with the VRP; only the short-volatility part earns the premium -> PUT/BXM are consistency checks only.",
    "Cboe BFLY methodology (read in full)": "Roll third Friday (holiday -> prior business day); strikes before 11:00 ET; legs valued at bid-ask midpoints (no costs) -> economic_check with break-even costs; T-bill account = 10x worst payoff -> excess returns; launched 2015-08-03, earlier values back-tested -> post-launch subsample.",
    "Cboe CNDR methodology (read in full, 2026-10-02)": "Same roll rule, 11:00 ET strike selection, midpoint pricing, 10x-max-loss T-bill account and 2015-08-03 launch as BFLY; short ~0.20-delta put/call, long ~0.05-delta put/call. The cycle design carries over unchanged.",
    "Not found / not covered": "No direct post-2017 replication of Johnson on Cboe strategy indices turned up in this search. Johnson's NOISE (Hu, Pan & Wang) and dealer-leverage controls were insignificant in his paper and are not replicated here (not freely available at this frequency).",
}

DECISION_RULES = """
SUGGESTIVE (the CEILING of this pre-registration) requires ALL of:
  1. N >= 180 cycles loaded (203 expected).
  2. Primary: Spearman rho(slope, CNDR excess return) > 0 with one-sided permutation p < 0.05
     (both seeds).
  3. rho >= 0.15.
  4. vrp_control_gate PASSES (partial rho > 0, p < 0.05 one-sided, both seeds). MANDATORY.
  5. subsample:post_johnson_sample_2014plus has the hypothesized sign. MANDATORY.
  6. Of the 13 sign-only checks (parameters.robustness_rule; oos_r2 counts as one, passing only
     if OOS R^2 > 0), AT MOST ONE fails, and it is not the post-2014 subsample.

REJECTED if N >= 180 and any of: primary not significant; rho < 0.15; vrp_control_gate fails
  (automatic); post-2014 subsample has the wrong sign (automatic); two or more of the 13 sign
  checks fail.
INCONCLUSIVE only if N < 180 (a data-loading failure, not a design outcome).

STAGE 2 (36 forward cycles after registration) is DIRECTIONAL / INFORMATIVE ONLY. Its rho, sign
  and p are reported; it never changes the verdict: same sign does not upgrade SUGGESTIVE to
  VALIDATED, opposite sign does not downgrade it. Anything stronger than SUGGESTIVE needs a NEW,
  separately pre-registered confirmatory test.
Economic check: reported with Stage 1 whatever the verdict; required before any live use.
"""

if __name__ == "__main__":
    import json
    print("=" * 100)
    print("CONFIG (trial #13) -- printing only; registration is a separate step")
    print("=" * 100)
    print("experiment_id:", config.experiment_id)
    print("hypothesis:", config.hypothesis)
    print("date_range / train_period:", config.date_range, config.train_period)
    print("declared_robustness_checks:", list(config.declared_robustness_checks))
    print("\nCONFIG HASH:", config.config_hash)
    print("\nPOWER_ANALYSIS:", json.dumps(POWER_ANALYSIS, indent=1))
    print(DECISION_RULES)
    print("This script never calls preregister_experiment() or run_experiment().")

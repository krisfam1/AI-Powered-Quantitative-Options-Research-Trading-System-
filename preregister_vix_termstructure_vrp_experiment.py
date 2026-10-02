"""
DRAFT pre-registration, trial #13 in the program tally (CLAUDE.md Section 1, Section 63).
Created 2026-10-02. Takes the slot freed when the cross-sectional straddle hypothesis
(trial #12, Section 62) was HELD -- a deliberate reallocation approved by the user for this
specific replacement, not an automatic reopening of the slot.

HYPOTHESIS IN ONE LINE: the slope of the VIX term structure, ln(VIX3M / VIX) at the close before
each monthly SPX option roll, POSITIVELY predicts the next roll-to-roll excess return of the Cboe
S&P 500 Iron Butterfly Index (BFLY), a capped-loss, near-delta-neutral short-volatility strategy.
Upward slope (contango) -> larger short-vol returns; inverted slope -> smaller or negative.

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
his results hold with "alternate geometric definitions of SLOPE"), a different payoff (Cboe BFLY,
a capped-loss short straddle), and a mostly post-publication sample (153 of 203 cycles start
2014 or later). See LITERATURE_CHECK below for the full baseline/control review.

WHAT HAS BEEN LOOKED AT BEFORE LOCKING (data-existence only, same discipline as every prior
pre-registration): series date coverage and missing-day counts; the number of cycles with both
signal and return endpoints present (scratchpad script vrp_feasibility.py, 2026-10-02). NO slope
value, NO index return, NO relationship between them has been computed or viewed. Disclosed
contamination that cannot be avoided: the market history (2008, 2018 "Volmageddon", 2020) and the
published literature are public knowledge, and the hypothesis direction was taken from Johnson.

THIS FILE CONSTRUCTS AND PRINTS THE CONFIG FOR REVIEW ONLY. It never calls
preregister_experiment() or run_experiment(). Registration (which locks the hash in
research_database.db) is a separate, deliberate step after user review.
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
        "excess return (over 4-week T-bills) of the Cboe S&P 500 Iron Butterfly Index (BFLY). An "
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
            "is an exchange holiday (BFLY methodology; e.g. 2014-04-17, 2026-06-18). Signal date "
            "S_k = the trading day before R_k. Cycle k runs from the close of S_k to the close of "
            "S_{k+1}. Trading days = dates present in Cboe's SPX history file. A roll date in the "
            "future is never inferred (the drafting check's fake 2026-10-01 'roll' is the bug class "
            "to avoid: a cycle needs both real endpoints)."
        ),
        "signal": "slope_k = ln(VIX3M_close(S_k) / VIX_close(S_k)). Positive = upward-sloping (contango).",
        "target": (
            "excess_return_k = BFLY(S_{k+1}) / BFLY(S_k) - 1 - rf_k, where rf_k = 4-week T-bill coupon-"
            "equivalent yield on S_k (or the latest prior Treasury business day) x (calendar days from "
            "S_k to S_{k+1}) / 365. Excess return is required because BFLY holds T-bills equal to 10x "
            "the options' worst-case payoff, so the T-bill rate is a large share of its raw return and "
            "rates move slowly with the volatility regime."
        ),
        "timing_and_lookahead": (
            "Everything in the signal and controls is known at the S_k close; BFLY sets its new strikes "
            "before 11:00 ET on R_k. The return window includes the final overnight of the expiring "
            "position (S_k close -> R_k SOQ), and excludes the final overnight of the new position "
            "(S_{k+1} close -> R_{k+1}); disclosed, not adjusted."
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
            "Pinned in advance to avoid the IV Stage 1 ambiguity (Section 33): every declared robustness "
            "check other than the vrp_control_gate passes if its statistic has the HYPOTHESIZED SIGN; it "
            "does not need independent significance. The oos_r2 check passes only if OOS R^2 > 0. A "
            "check with the wrong sign is a reversal and triggers REJECTED."
        ),
        "robustness_definitions": {
            "alternate_payoff": "Primary test with CNDR, PUT, BXM excess returns in place of BFLY. PUT/BXM carry large equity beta (AQR: Israelov & Nielsen), so they are consistency checks, not cleaner tests.",
            "alternate_statistic:pearson": "Pearson correlation, same data.",
            "alternate_signal:ln_vix6m_over_vix_from_2008": "Signal ln(VIX6M/VIX), cycles from the first signal date with VIX6M (2008-01-17): 224 cycles, adds the 2008 crisis.",
            "subsample:post_johnson_sample_2014plus": "Cycles with S_k >= 2014-01-01 (153): outside Johnson's 1996-2013 sample.",
            "subsample:post_bfly_launch_2015_08plus": "Cycles with S_k >= 2015-08-03 (134): BFLY values before its launch date are Cboe back-tests.",
            "nonlinearity:bottom_quintile": "Expanding-window quintile cut (first 36 cycles as burn-in, cutoff from past slopes only): mean excess return in bottom-quintile cycles minus all other cycles; hypothesized sign NEGATIVE (Johnson's concentration in the lowest SLOPE quintile).",
            "oos_r2_vs_historical_mean": "Goyal & Welch (2008) / Campbell & Thompson (2008): from cycle 61 on, forecast with an expanding-window OLS of return on slope, benchmark = expanding historical mean (the 'always sell' baseline); pass if OOS R^2 > 0.",
            "stambaugh_bias_corrected": "Amihud & Hurvich (2004) augmented-regression slope coefficient for the persistent predictor; hypothesized sign POSITIVE.",
            "partial_control:lagged_own_return": "Partial Spearman controlling for the previous cycle's BFLY excess return (practitioner momentum claim); hypothesized sign POSITIVE.",
            "drop_top5_abs_return_cycles": "Primary test without the 5 cycles with the largest |excess return| (concentration check, cf. V1's Phase 7).",
            "alternate_null:stationary_block_bootstrap": "p-value from a stationary block bootstrap (mean block 6 cycles) of the target, preserving volatility clustering; reported, sign rule applies to rho.",
        },
        "economic_check": (
            "Reported, NOT part of the verdict, but required before any trading use (Section 1). Timed "
            "strategy: hold BFLY in cycle k unless slope_k is below the expanding 20th percentile of past "
            "slopes (first 36 cycles burn-in), in which case hold T-bills. Report annualized excess "
            "return, Sharpe, max drawdown and worst cycle vs always-on BFLY, and the BREAK-EVEN round-trip "
            "cost per roll (as % of index value) at which the timed strategy's advantage disappears, "
            "compared with an estimate from real SPY/SPX quotes (EODHD end-of-day spreads, Section 26). "
            "Cboe values all option legs at bid-ask MIDPOINTS, so index returns exclude trading costs."
        ),
        "stage2": (
            "Prospective and rolling: cycles whose signal date S_k is strictly after the registration "
            "date. Lock at N = 36 forward cycles (~3 years); run once. Replication = same sign of the "
            "Spearman rho; significance reported but not required, because power at N = 36 is only ~21% "
            "at rho = 0.15 and ~41% at 0.25 (see POWER_ANALYSIS). Earlier looks are exploratory only."
        ),
    },
    model_version=None,
    pricing_methodology="cboe_strategy_index_values_mid_quote_no_costs_economic_check_adds_costs",
    execution_assumptions=(
        "none in the verdict -- the test uses Cboe index values (mid-quote, no costs); the economic "
        "check adds a break-even cost analysis; any live use needs its own sizing and execution work "
        "(e.g. XSP mini-SPX iron butterflies)"
    ),
    train_period=("2009-10-15", "2026-09-17"),
    validation_period=None,
    test_period=None,  # Stage 2 is prospective and rolling (parameters.stage2), so it cannot be dated now
    random_seeds=[42, 43],
    code_version="vix_termstructure_vrp_index_timing_v1_draft",
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
        "alternate_payoff:CNDR", "alternate_payoff:PUT", "alternate_payoff:BXM",
        "alternate_statistic:pearson",
        "alternate_signal:ln_vix6m_over_vix_from_2008",
        "subsample:post_johnson_sample_2014plus",
        "subsample:post_bfly_launch_2015_08plus",
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
          "straddles is ~2-10% (|r| ~0.14-0.32); BFLY's capped wings and T-bill dilution should not "
          "change a rank correlation much but may weaken it. The vrp_control_gate (partial correlation, "
          "2 controls) has slightly less power. A REJECTED means 'no effect >= ~0.18 detected'."),
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
    "Simon & Campasano 2014 (VIX futures basis)": "Contango predicts short-VIX-futures profits, robust to costs; equity-beta hedging mattered -> corroborates the sign; motivates a near-delta-neutral primary payoff (BFLY) over PUT/BXM.",
    "AQR (Israelov & Nielsen 2014/2015; 'Understanding the VRP' 2018)": "PUT/BXM returns mix equity beta with the VRP; only the short-volatility part earns the premium -> PUT/BXM are consistency checks only.",
    "Cboe BFLY methodology (read in full)": "Roll third Friday (holiday -> prior business day); strikes before 11:00 ET; legs valued at bid-ask midpoints (no costs) -> economic_check with break-even costs; T-bill account = 10x worst payoff -> excess returns; launched 2015-08-03, earlier values back-tested -> post-launch subsample.",
    "Not found / not covered": "No direct post-2017 replication of Johnson on Cboe strategy indices turned up in this search. Johnson's NOISE (Hu, Pan & Wang) and dealer-leverage controls were insignificant in his paper and are not replicated here (not freely available at this frequency).",
}

DECISION_RULES = """
Stage 1 SUGGESTIVE (the most Stage 1 alone can earn) requires ALL of:
  1. N >= 180 cycles loaded (203 expected).
  2. Primary: Spearman rho(slope, BFLY excess return) > 0 with one-sided permutation p < 0.05
     (both seeds).
  3. rho >= 0.15.
  4. vrp_control_gate PASSES (partial rho > 0, p < 0.05 one-sided, both seeds). MANDATORY.
  5. Every other declared robustness check has the hypothesized sign (sign only; pinned in
     parameters.robustness_rule), and oos_r2_vs_historical_mean > 0.
VALIDATED additionally requires Stage 2 (36 forward cycles, prospective) to have the same sign.

REJECTED if N >= 180 and any of: primary not significant; rho < 0.15; vrp_control_gate fails;
  any robustness check has the wrong sign; OOS R^2 <= 0.
INCONCLUSIVE if: N < 180 (a data-loading failure, not a design outcome); or Stage 1 passes and
  Stage 2 has not reached 36 cycles; or Stage 2 reverses sign (a conflict needs a new,
  separately pre-registered follow-up).
Economic check: reported with Stage 1 whatever the verdict; required before any live use.
"""

if __name__ == "__main__":
    import json
    print("=" * 100)
    print("DRAFT CONFIG -- FOR REVIEW, NOT YET PREREGISTERED (trial #13)")
    print("=" * 100)
    print("experiment_id:", config.experiment_id)
    print("hypothesis:", config.hypothesis)
    print("date_range / train_period:", config.date_range, config.train_period)
    print("declared_robustness_checks:", list(config.declared_robustness_checks))
    print("\nCONFIG HASH:", config.config_hash)
    print("\nPOWER_ANALYSIS:", json.dumps(POWER_ANALYSIS, indent=1))
    print(DECISION_RULES)
    print("NOT PREREGISTERED. This script never calls preregister_experiment() or run_experiment().")

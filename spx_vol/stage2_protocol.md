# Stage 2 protocol: does a market-state feature predict the SPX volatility-premium gap? (fixed 2026-10-17)

**Committed BEFORE any feature-vs-target statistic was computed. No change after results.** This replaces the original "exploratory statistics / structural breaks" Stage 2, which is not run.

**What this is not:** no hypothesis is registered, no hash is made and no slot is used. There is no trading P&L, no option-index data (BXM, PUT, CNDR, BFLY), no SPY and no broker or API calls. Every run goes in the append-only search ledger.

---

## 1. Target (one)

**G_t = VIX_t² − 100² · (252/21) · Σ_{i=1..21} r²_{t+i}**, in VIX² points (percent²; VIX = 20 gives 400).
- r_j = ln(C_j / C_{j−1}), the SPX close-to-close log return (Yahoo `^GSPC` closes, cleaned in Stage 1).
- The target uses only the returns on sessions t+1 … t+21. It is missing unless t+21 lies inside the data the step may touch.
- **Descriptive only:** the mean of G_t over the development rows is reported. It is not part of any test.

## 2. Features (exactly 3, from Stage 1's 127; fixed now)

| # | Stage 1 name | Formula (data through the close of t only) |
| --- | --- | --- |
| 1 | `fut_slope__raw` | CM60_t − CM30_t: the VIX futures constant-maturity curve, linear in days to expiry on settlement prices (Stage 1 protocol §2.1). **The futures-curve version is usable:** CM60 is never missing in 2008–2016. CM30 is extrapolated on 113 days, which are kept and flagged. |
| 2 | `vvix_over_vix__raw` | VVIX_t / VIX_t |
| 3 | `skew__raw` | SKEW_t (Cboe close) |

Raw levels are used, so no 250-day warm-up is lost. No swapping, transforms, windows or other features.

## 3. Models

- **Baseline:** G_t = a + b₁·VIX_t + b₂·RVtrail_t + e, where RVtrail_t = 100² · (252/21) · Σ_{i=0..20} r²_{t−i}, the trailing 21-day close-to-close realized variance in percent², known at t.
- **Augmented, one per feature:** baseline + c·X_t. The three features are tested one at a time; there is no combined model.
- **Fit:** OLS.

## 4. Fit scheme (out of sample)

- **Usable rows** have every input (VIX, RVtrail, X) and the target present. The same rows are used for the baseline and the augmented model, so each feature's comparison is paired.
- **Refits** happen on the first session of each calendar month. At a refit date T the training rows are s ≤ T − 42 sessions: a purge of 21 (the target ends by T − 21) plus an embargo of 21.
- **Minimum training:** a refit is used only once it has at least 756 training rows (3 years). The first forecast origin is the first refit date that meets this.
- **Forecasts:** each origin t uses the latest refit T ≤ t.
- **Development evaluation:** origins from the first valid refit to the last t with t+21 ≤ 2016-12-30.
- **Score:** improvement = 1 − SSE_aug / SSE_base over the evaluation origins, reported as a % reduction in squared error.
- **Bootstrap:** circular moving blocks of 42 sessions over evaluation origins, 10,000 resamples, seed 42. The baseline and augmented errors are resampled together, and the improvement is recomputed in each replicate.

## 5. Development pass rule (2008–2016 only; `dev_guard` stays at 2016-12-31)

**Development sign** := the sign of c in the final development refit (the last monthly refit with T ≤ 2016-12-30). That model is frozen for validation.

A feature **passes only if ALL four hold:**

- **(a)** The improvement is > 0 **and** its two-sided bootstrap percentile interval at level 1 − 0.05/3 (98.33%: percentiles 0.833 and 99.167) excludes zero, i.e. the lower bound is > 0. That is a Bonferroni correction for 3 features.
- **(b)** The sign of c is the same in both halves of the sample.
  - The usable development rows are split at the midpoint date (the median row date).
  - Half 1 drops its last 21 rows, so no half-1 target overlaps half 2.
  - Each half gets an in-sample OLS of the augmented model, and both signs of c must be equal and non-zero.
- **(c)** The improvement stays > 0 (point estimate) when every row dated 2008-01-02 … 2009-12-31 is removed from both training and evaluation, rerunning the same scheme with the same 756-row minimum.
- **(d)** Under the alternative target G′_t = ln(VIX_t² / (100² · (252/21) · Σ_{i=1..21} r²_{t+i})), an in-sample OLS of the augmented model, on the same training rows as the final development refit, gives a c with the same sign as the development sign. This is a descriptive robustness check only, not a second test.

Each feature's development step is **one run**: (a)–(d) are computed inside it, and it gets **one ledger row**. **Exactly 3 runs.** If a bug is found, it is fixed and the affected run(s) are run once more; both are kept in the ledger and both are disclosed.

## 6. Validation rule (2017–2020; ONLY if at least one feature passed Section 5)

- If no feature passes, validation is skipped entirely and the report says so.
- **Each passing feature gets one run** through a separately named function, `run_validation()`. It is the only code that may read data up to 2020-12-31, and it does so for that single run. Anything dated 2021-01-01 or later raises an error in every step, and a test checks this.

**Specification:** frozen, with the same feature, the same baseline and the same Section 4 scheme.
- The expanding scheme continues: monthly refits through 2020, training rows s ≤ T − 42, all rows from 2008 on.
- The first validation refit, on 2017's first session, trains on rows through 2016 only, so it reproduces the frozen 2016 model's training set.
- Evaluation origins: 2017-01-03 to the last t with t+21 ≤ 2020-12-31.
- The forecasts from the frozen final development coefficients, without refitting, are also reported, as description only.

**Validation passes only if all of these hold:**
1. The improvement is > 0.
2. The sign of c at the last validation refit equals the development sign.
3. The two-sided 95% bootstrap interval of the improvement (42-session blocks, 10,000 resamples, seed 42) excludes zero.

A feature that fails is dropped. Results are reported either way, and there is no retuning.

## 7. Weaknesses stated in advance

1. **The development window is dominated by 2008.** With the 3-year minimum, the 2008–2010 crisis and aftermath sit in training, and evaluation starts in early 2011. Check (c) removes 2008–09 entirely.
2. **Overlapping targets:** consecutive G_t share 20 of 21 returns, so the effective sample is much smaller than the row count. That's why the bootstrap uses 42-day blocks.
3. **G is mostly positive,** since VIX usually runs above realized volatility. A feature can look useful just by tracking the size of a premium that is always there. The baseline (VIX + trailing RV) is meant to absorb that.
4. **A few volatility episodes** (2010, 2011, 2015–16) drive most of the squared error. A squared-error score rewards getting those right and says little about calm periods.
5. **No SPX option prices:** VIX stands in for implied volatility. There is no trading P&L, and nothing from 2021 onward.

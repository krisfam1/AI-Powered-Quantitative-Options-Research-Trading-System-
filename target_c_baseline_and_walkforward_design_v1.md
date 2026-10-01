# Steps 3 & 4: Ticker-Identity Baseline Design and Walk-Forward Validation Design

**Date: 2026-09-29. Design only — no preregistration written, no hash computed, no data touched, no code run. Target C (relative-to-own-history) locked per approval. Builds on `broader_universe_feasibility_report.md` (Step 1) and `target_design_comparison_v1.md` (Step 2). Does not touch RF v1/v2, XGBoost v1, or regularized XGBoost v2 (CLAUDE.md Section 58, permanently closed).**

---

## 0. Condition 2 resolved first: minimum trailing-history requirement for ticker-date eligibility

This was requested as a standalone, pre-specified decision, not deferred into Step 3/4 — resolved here explicitly before anything else, since both steps below depend on it.

**Target C's definition** (`target_design_comparison_v1.md`, Section 1): `z_i,t = (raw_i,t − trailing_mean_i) / trailing_std_i`, where the trailing mean/std come from ticker *i*'s own history strictly before *t*. This requires a locked lookback window length and a locked minimum-population rule within that window.

**Lookback window: 126 trading days (~6 months), locked now.**

Reasoning, weighing the real tradeoff explicitly rather than picking a round number:
- A full year (252 days) gives a more stable mean/std estimate but costs more burn-in on exactly the newest, thinnest-history tickers this broader universe was built to include (e.g. ARM, listed 2023-09-14, ~762 total trading days per the Step 1 feasibility report — a 252-day burn-in would consume roughly a third of its usable life before its first eligible observation). It is also slower to adapt if a ticker's real volatility regime genuinely shifts (e.g., after a major business change), which works against the very idea Target C is built on (comparing current behavior to a *representative* recent regime, not a stale one).
- A short window (e.g. 20-63 days, the kind of length used for this project's existing `trailing_realized_vol_20d` *feature*) is the wrong tool here — that feature answers "what's recent realized vol," a different, shorter-horizon question from "what is this ticker's typical/representative regime," which is what Target C's denominator needs to characterize.
- 126 trading days is a standard middle-ground choice in realized-volatility literature and balances estimation stability, regime-adaptiveness, and burn-in cost on the newest tickers reasonably.

**Eligibility rule**: within the fixed 126-trading-day calendar window immediately preceding the observation date, at least **113 of 126 (~90%)** must have a valid, computable raw target reading. Below that threshold, the ticker-date is **excluded, never imputed or substituted** — consistent with this project's standing discipline elsewhere (the EODHD id-date rule, GEX's no-substitution-on-missing-T-1 rule). Applied identically to all 59 tickers, no per-ticker exceptions.

**Disclosed cost, to be verified empirically at data-generation time, not assumed now**: for the newest tickers (ARM, RIVN, LCID, SOFI, COIN, PLTR, AFRM — Step 1's IPO-limited group), this burn-in requirement pushes their first eligible observation roughly 6 months past their real listing date (further still if EODHD's own options-chain depth for these specific names doesn't extend all the way back to listing — not independently confirmed in Step 1's audit for every one of these 7 tickers individually, and must be checked at data-generation time, not assumed to match the 6-ticker/SPY 2023-10-02 cliff). This is a modest, disclosed cost, not a blocking one.

**Mandatory robustness check declared now, not left implicit**: `alternate_lookback:252day` — rerun the entire target construction with a 252-trading-day window (minimum population 227/252, same ~90% rule) to confirm the primary result isn't an artifact of the specific 126-day choice. This mirrors this project's established pattern of testing an alternate specification for exactly this kind of design decision (e.g. IV term structure's alternate DTE bucket, strike positioning's alternate moneyness band).

---

## 1. Step 3: Ticker-identity / fixed-effects baseline design

**Per explicit instruction: this stays in the design as a mandatory, pre-specified gate, even though Target C already structurally reduces the risk it guards against. It is not downgraded to optional or advisory.**

### 1.1 Why the naive Section 58 method needs adapting, not just reusing verbatim

Section 58's "ticker-only baseline" (predict each ticker's own historical mean of the *raw* target) is degenerate under Target C — the raw target is already, by construction, demeaned relative to each ticker's own trailing history, so its full-training-period average is close to zero for every ticker almost by definition. A literal transplant of Section 58's baseline would be a trivial, uninformative check. The construction below adapts the same underlying idea to what Target C can actually leak: not a persistent *mean* level (structurally removed), but a persistent *residual drift* (a rolling window imperfectly tracks a slowly-trending regime, leaving a small but real non-zero average deviation) or a per-ticker *variance* difference (heteroskedasticity even after centering).

### 1.2 The two-part mandatory gate

**Part 1 — Ticker-only baseline model.** For each ticker, compute the mean of the *actual* Target-C value (`z_i,t`, not the raw target) over that ticker's own training-period observations only: `baseline_prediction_i = mean_train(z_i,*)`. This constant is then used as that ticker's prediction for every observation in the locked primary test set — identical mechanics to Section 58's method, just applied to the already-transformed target.

**Part 2 — Real model with ticker dummies.** Whichever model(s) the eventual hypothesis test specifies (model class/comparison to be settled in a later step, not here) are fit with the real feature set **plus explicit one-hot ticker dummy columns** added as additional inputs — the identical mechanism Section 58 used (`analyze_ticker_fixed_effects.py`), giving the model every opportunity to use ticker identity directly, so that "incremental" is measured after both routes to ticker-identity are available to it.

### 1.3 Locked decision rule (before any result exists)

On the same locked, non-overlapping primary test set used for the main hypothesis test:

- **PASS** requires both: (a) incremental R² = R²(model + features + ticker dummies) − R²(ticker-only baseline) **> 0**, and (b) a paired one-sided Wilcoxon test on per-observation absolute error (model+dummies' error < baseline's error) significant at the same corrected α used for the primary hypothesis test.
- **FAIL** if either (a) or (b) fails to clear.

**Why this bar, not the 0.05 R²-delta floor reused elsewhere in this project**: that floor (Sections 45/46/48/51) was calibrated for a different question — "does a richer model meaningfully beat a simpler one." Here the question is narrower and more binary: "does the model add anything at all beyond knowing which ticker it is." Section 58 already showed the realistic alternative is not "a small positive margin" but **outright negative** incremental R² across every model in that entire track — so the appropriate bar is simply "provably beats it," not an arbitrary additional margin on top. A margin requirement here would risk manufacturing a false failure on a target that, if Target C's structural logic holds, should show a small baseline effect to begin with.

**Expected magnitude, disclosed as an expectation only, not assumed or pre-committed to**: because Target C already centers per ticker, the ticker-only baseline's absolute R² here should be far smaller than Section 58's ~0.50 (closer to 0, reflecting only residual drift/heteroskedasticity, not a full mean level) — but this must be verified empirically once real data exists, not assumed. The gate applies at whatever magnitude the baseline turns out to have.

### 1.4 Secondary, disclosed diagnostic (not a gate)

A per-ticker training-set **variance** of `z` (not mean) is reported alongside the primary gate, to make visible whether any model's error correlates with ticker-level heteroskedasticity even after centering — the smaller, second-order risk flagged in `target_design_comparison_v1.md` Section 2.7. This is informational, not pass/fail, since it tests a genuinely different question from Section 58's original mean-recovery finding.

---

## 2. Step 4: Walk-forward validation design

**Terminology note, disclosed rather than silently resolved**: "walk-forward validation" can mean either (a) a single chronological train/val/test holdout (what every prior experiment in this project's ML track used), or (b) genuine rolling-origin cross-validation with multiple sequential folds. Given this experiment is explicitly meant to be methodologically stronger than the four closed volatility experiments (broader universe, structurally-safer target, mandatory ticker-identity gate), the design below implements **(b)**, a real multi-fold rolling-origin scheme, inside this project's already-established Stage 1 (historical) / Stage 2 (rolling, prospective) two-stage structure — not a replacement for that structure, an enhancement of what happens *inside* Stage 1. Flagged explicitly so this can be corrected if a simpler single-holdout was actually intended.

### 2.1 Stage 1 — historical window, K-fold expanding-window walk-forward

- **Panel structure**: unbalanced by design — every ticker enters the panel only once it clears the Section 0 burn-in requirement (126 trading days, ≥90% populated). Calendar date range shared across all tickers; ticker coverage within that range varies naturally (the original 6 tickers enter earliest; IPO-limited tickers enter later). This matches this project's own established pattern (e.g. IV term structure, GEX experiments splitting purely on calendar date with naturally uneven per-ticker coverage).
- **Stage 1 calendar range (placeholder, to be reconfirmed against real data at execution time, per this project's standing disclosed-placeholder discipline)**: from the earliest date any ticker clears eligibility, through **2026-06-30**. Stage 2 begins immediately after.
- **Fold structure**: **K = 4 expanding-window folds** (a default, adjustable once the real, verified date range is known). Training set grows with each fold (no data is discarded between folds); each fold's test block is a contiguous, non-overlapping, strictly-later period than its own training data:

  ```
  Fold 1: train [Stage1_start, T1)   test [T1, T2)
  Fold 2: train [Stage1_start, T2)   test [T2, T3)
  Fold 3: train [Stage1_start, T3)   test [T3, T4)
  Fold 4: train [Stage1_start, T4)   test [T4, Stage1_end)
  ```

  with T1–T4 chosen to give roughly equal-length test blocks (~5–6 months each, given a ~2-year usable Stage-1 range) — exact boundaries to be pinned to real calendar dates once the true eligible-date range is confirmed at execution time, not invented now.
- **Hyperparameter tuning**: retuned independently within each fold's own training data via nested CV (never informed by that fold's own test period, and never informed by any later fold's data) — preserves genuine walk-forward integrity fold by fold, rather than tuning once globally and reusing across folds.
- **Primary test-set construction**: all four folds' test-period observations are **pooled first**, and the established per-ticker-per-ISO-week thinning rule (Sections 44/45/46/48/51's locked, non-overlapping test-set mechanism) is applied **once, to the pooled set** — not separately per fold. Thinning per fold independently and then combining could leave near-adjacent weeks standing across a fold boundary, reintroducing exactly the serial-correlation risk the thinning rule exists to prevent. One pooled thinning pass avoids that.
- **Primary hypothesis test**: run once, on the pooled/thinned primary test set — a single decision, not four separate ones, matching this project's standing preference for one locked primary test with a single explicit verdict.
- **New robustness check, specific to this design — `fold_stability`**: report each fold's own result individually (not just the pooled number) and require **direction consistency across all four folds** (not necessarily individual significance) as part of the declared robustness-check menu — the direct walk-forward analog of this project's established "leave-one-ticker-out must not reverse direction" convention, applied here to "leave-one-time-block-out" instead.

### 2.2 Stage 2 — rolling, prospective, open-ended

Matches this project's already-established Stage 2 convention exactly (IV term structure, RF v2, regularized XGBoost v2): fixed start immediately after Stage 1 ends (2026-07-01, placeholder pending real-date reconfirmation), open end determined purely by a data-existence check (record count > 0 for the most recent available date), continuing until N≥100 is reached, then locking that exact realized set for one test — never influenced by inspecting the actual target/feature relationship while waiting. **Not yet built**: this dataset has no automated nightly accumulation job yet (unlike RF v2's `RF_v2_Stage2_Nightly_Update`) — flagged as a to-do at data-generation time, not yet actioned.

### 2.3 Lookahead-safety, reconfirmed explicitly for this design

- Target C's own trailing mean/std use only data strictly before the observation date (Section 0) — unaffected by fold structure.
- No fold's training window ever includes a date from its own test window or from any later fold's test window.
- **ADDED 2026-10-01 — purge (date separation alone was not enough):** the targets are *forward* realized vols, so a training row dated within *h* trading days of the test start has a label built from test-period prices. Each fold's training set (and every nested-CV inner split) drops its last **max(h, 20)** trading days before the test start: h = the target horizon (20 primary; 50 for the 50-day check), 20 = the longest feature lookback (`trailing_realized_vol_20d`). Test blocks are unchanged. No post-test embargo is needed, since expanding folds never train on later data. See the pre-registration's `fold_structure.purge_rule`.
- Hyperparameter tuning is confined to each fold's own train+val slice, never touching that fold's test period or any subsequent fold.
- Stage 2 remains genuinely prospective relative to Stage 1's own end date, exactly as established elsewhere in this project.

### 2.4 Interaction with Step 3's gate

The ticker-identity gate (Section 1) is evaluated on the **same pooled, thinned Stage-1 primary test set** as the main hypothesis test — one shared test set serves both the primary hypothesis test and the mandatory baseline gate, not two separately-constructed samples. This keeps the two checks directly comparable and avoids a second, independent source of sampling variation between them.

---

## 3. Open items disclosed, not yet resolved — flagged rather than decided unilaterally

- Exact fold boundary dates (T1–T4) depend on the real, verified per-ticker eligible-date range — cannot be pinned to literal calendar dates until data generation actually runs (consistent with every prior experiment's disclosed-placeholder practice in this project).
- Whether EODHD's options-chain depth for the 7 IPO-limited tickers (ARM, RIVN, LCID, SOFI, COIN, PLTR, AFRM) matches the already-confirmed 2023-10-02 cliff for the original 6 tickers/SPY, or has its own, later cliff — not independently verified in Step 1's audit for each of these specifically, needs a targeted check before the data-generation pass.
- Stage 2's automated accumulation job for this new dataset does not exist yet.
- Model class(es) for the primary hypothesis test itself, the actual predicted horizon(s), effect-size floor, and the overall hypothesis statement are intentionally **not addressed here** — out of scope for Steps 3–4, reserved for a later step.

**Note preserved from Step 2, not lost**: Target A (same-date cross-sectional rank) remains a legitimate, separate future hypothesis that would genuinely use this universe's cross-sectional breadth — deliberately not pursued now, to be revisited once real relative-value execution infrastructure exists.

**Status: design only. Nothing preregistered, nothing hashed, no data touched.** Awaiting review before proceeding.

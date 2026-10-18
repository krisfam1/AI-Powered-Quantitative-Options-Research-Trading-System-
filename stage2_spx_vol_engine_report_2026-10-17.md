# SPX volatility-state engine: Stage 2 report (2026-10-17)

**Question:** does any of three pre-chosen market-state features predict the SPX volatility-premium gap better than a simple baseline?
- The gap: G = VIX² minus the SPX realized variance over the next 21 sessions.
- The baseline: VIX plus trailing 21-day realized variance.

**Verdict: no state feature predicts the gap.** All three failed the development step (2008–2016). As the protocol requires, validation (2017–2020) was **skipped**, and those years were never read.

**What this stage was not:** no hypothesis was registered, no hash made and no slot used. There was no trading P&L, no option indexes and no SPY. Nothing from 2021 onward was touched.

---

## 1. Proof the protocol came first

| Event | Time (UTC) | Time (ET) |
| --- | --- | --- |
| Protocol `spx_vol/stage2_protocol.md` committed: **`ebdd22d727c07bfa0dc5ddce7071b39e3078898c`** | 2026-10-18 02:42:25 | 2026-10-17 22:42:25 |
| The 3 development runs, logged to the search ledger | 2026-10-18 02:44:51 | 22:44:51 |

No feature-vs-target statistic was computed before the commit. Before the runs, the only checks on real data were these:
- The three Stage 2 features equal the Stage 1 feature file exactly.
- The non-missing counts: 2,267 / 2,265 / 2,266.

Neither check involves a target.

## 2. Setup (as committed)

- **Target:** G_t = VIX_t² − 100²·(252/21)·Σ r²_{t+1..t+21}, in VIX² points. **Descriptive only:** the mean of G over the development rows is **+88 VIX² points**, so on average VIX overstated what SPX then realized. For scale, VIX 20 means 400.
- **Features** (Stage 1 names), each tested alone on top of the baseline:
  1. `fut_slope__raw` = CM60 − CM30 (the futures-curve version);
  2. `vvix_over_vix__raw` = VVIX / VIX;
  3. `skew__raw` = SKEW.
- **Baseline:** G ~ VIX + trailing 21-day realized variance, by OLS.
- **Scheme:**
  - expanding window, refit on the first session of each month;
  - a 42-session gap (purge 21 + embargo 21);
  - at least 756 training rows (3 years), so the first forecast is on **2011-04-01**;
  - evaluated through 2016-11-30, about 1,427 forecast dates;
  - 69 refits, the last on 2016-12-01, trained on ~2,183 rows.
- **Score:** % reduction in out-of-sample squared error against the baseline. Block bootstrap with 42-day blocks and 10,000 resamples. The interval is 98.33% (Bonferroni for 3 features).

## 3. Development results (2008–2016)

| Feature | Improvement vs baseline | 98.33% interval | (a) better and significant | (b) same sign both halves | (c) still better without 2008–09 | (d) same sign on log target | **Passes?** |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `fut_slope__raw` | **−91.2%** (worse) | −336% to −20% | Fail | Pass (+296 / +35) | Fail (−12.5%) | Pass (+0.157) | **No** |
| `vvix_over_vix__raw` | **+2.9%** | −8.1% to +42.0% | Fail (interval includes 0) | Fail (+103 / −29) | Fail (−1.1%) | Fail (−0.020 vs dev sign +) | **No** |
| `skew__raw` | **−18.5%** (worse) | −71% to −2% | Fail | Fail (+31 / −2.2) | Fail (−8.6%) | Fail (−0.002 vs dev sign +) | **No** |

**What the table means:**
- **Futures slope** made the forecasts much *worse*: 91% more squared error, and the interval is entirely below zero. Its coefficient keeps its sign but shrinks about 8× between the two halves (296 to 35). An unstable size like that hurts out-of-sample forecasts badly when the curve is steep.
- **VVIX / VIX** had a small positive point estimate (+2.9%), but the interval runs from −8% to +42%, which is noise. Its sign flips between halves. Without 2008–09 it is slightly worse than the baseline, and on the log target its sign reverses.
- **SKEW** made the forecasts worse, flipped sign between halves, and flipped again on the log target.
- **Check (c):** dropping 2008–09 moved the first forecast to 2013-04-01 (~927 dates), and all three were negative.

**Final development coefficients** on the feature (c), for reference: slope +132.5, VVIX/VIX +88.0, SKEW +11.3, in VIX² points per unit of feature. They're kept in `data_snapshots/spx_vol_engine/results/stage2_results.json`.

## 4. Validation (2017–2020)

**Not run.** The protocol allows validation only when at least one feature passes development, and none did. `run_validation()` exists and is tested (it refuses 2021+ dates), but it was never called on real data. The 2017–2020 data was not read in this stage.

## 5. Search ledger

`spx_vol/store/spx_vol.db`, table `search_ledger`: **29 rows** in total.
- 26 are from Stage 1.
- **3 are from Stage 2**, one per feature, matching the 3 runs.
- No bug was found, so there were no reruns, and no validation rows.

## 6. Tests

19 tests pass: 6 for Stage 2, plus Stage 1's 13 still passing after the guard changes.
- **(a) 2021+ blocked:** `dev_guard`, `val_guard` and the new always-on `lock_guard` raise on 2021 dates. `build_inputs` with the validation guard, `run_validation` and `dev_run` all refuse data that reaches into 2021 (or 2017, for the development step).
- **(b) No look-ahead in features:** randomly changing every input after a date leaves the features and baseline inputs at earlier dates unchanged.
- **(c) Target and gap:** G at t equals a hand computation over t+1…t+21. Changing the close at t+22 or later leaves it unchanged, and changing t+21 changes it. Every refit trains only on rows at least 42 sessions back, with at least 756 rows.
- **(d) Ledger count equals run count:** checked against a temporary ledger.

## 7. Wording issue in the protocol (disclosed; no effect)

Protocol §6 says the first validation refit "reproduces the frozen 2016 model's training set". That's not exactly true: a refit on 2017's first session, with its 42-session gap, trains on rows through early November 2016, while the frozen 2016-12-01 refit trains through early October 2016. Validation wasn't run, so this has no effect. It would need correcting in the text before any future validation.

## 8. What this cannot tell us

- **No SPX option prices.** VIX stands in for SPX implied volatility. The real 30-day SPX ATM or skewed implied vol could behave differently.
- **No trading P&L.** A better forecast of the gap wouldn't by itself be a profitable trade, and no costs were modelled.
- **One dominant crisis.** 2008–10 sits in training, and evaluation (2011–2016) is mostly calm with a few spikes. Squared error is dominated by those spikes.
- **Overlapping targets:** neighbouring days share 20 of 21 returns, so the effective sample is far smaller than ~1,427.
- **Nothing from 2017 onward:** not 2018, not 2020, not 2022. A feature that works only in those regimes wouldn't show up here.
- **Only 3 features, raw levels, one horizon, a linear model.** Failing here doesn't rule out percentiles, interactions, regimes or nonlinear models. It does make the simple, plausible versions unlikely to help.

## 9. Recommendation (not started)

**Stop feature hunting on this target for now.**
- Stage 1 showed VIX alone beats price-history forecasts of SPX volatility. Stage 2 shows three standard state variables don't improve on VIX + trailing realized volatility for predicting the gap.
- The most useful next step is **descriptive**: map how the gap G behaves *by regime*, using statsmodels Markov switching on development years only, so we know when VIX overstates or understates. That would come before testing any further predictor.
- It would need its own protocol committed first, and the remaining features shouldn't be tried one by one.
- The search ledger already holds 29 runs. Any future confirmatory test must count them.

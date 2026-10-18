# SPX volatility-state engine: architecture and research plan (v1, 2026-10-17)

**Status: approved by the user 2026-10-17, Stage 0 only.** Chosen answers to Section 8: the discovery/confirmation split; the 2021+ lock; stand-ins only for SPX option prices; free downloads and a separate virtual environment; the smaller feature set. The Stage 0 data audit is `stage0_spx_vol_engine_audit_2026-10-17.md`. Nothing is registered, and no hypothesis slot is used until confirmation, which needs separate approval. Section 1 explains where the slot comes in.

Start dates marked *(verify)* are my best knowledge and get checked in Stage 0. The ones marked *(checked)* were read from files in this repo today.

---

## 0. Summary

- The spec describes a large **search**: about 20 relationships, 13 statistics each, 6 windows, interactions, 5 regime methods, 9 anomaly detectors, 8 targets and 7 horizons. That is tens of thousands of combinations. A search that size will turn up "significant" results by chance, however carefully each test is run.
- So the plan has **two parts**:
  1. **Discovery (Stages 1–7):** explore on development data only, and record every configuration tried in a search ledger.
  2. **Confirmation (Stages 8–9):** freeze at most 3 hypotheses, pre-register them under `tiered_v1`, and test each once on held-out data that nothing in discovery touched.
- Confirmation is what uses the **last hypothesis slot**: one trial, with up to 3 tests, Bonferroni-corrected. The engine and the daily report get built only after that (Stages 10–12).
- **Data is the binding constraint.** The SPX option surface (ATM IV, 25-delta put and call IV, the SPX options term structure) is not available free back to 2004. I propose starting without it and using the VIX-index family plus SKEW as proxies (Section 2).
- **The targets have to be the things that actually pay**, because this project has already learned that forecasting realized volatility mostly recovers the IV that is already priced (§33):
  - For VIX changes, beat the VIX futures curve, which already prices in mean reversion. Beating "VIX will mean-revert" is not enough.
  - For the volatility premium, the target is the payoff VIX² − realized variance.
  - For realized volatility, beat a HAR-RV model plus the VIX level.

---

## 1. How this fits the project's rules

| Rule | How the plan handles it |
| --- | --- |
| No new hypothesis until a slot is free (§1) | One slot is open. It is used only at the confirmation step (Stage 8), not for exploration. |
| Every trial counts once in the ledger, and the DSR uses the trial count | The confirmatory trial gets a row in `hypothesis_ledger.csv` **when it is registered**. The search ledger (Section 6.4) records how many configurations discovery tried, so the DSR and PBO can use the real search breadth and not just "1". |
| Pre-registration under `tiered_v1`, with hard gates and soft checks | The baseline-beating test (Section 4.2) is a **hard gate**. Stress-period and estimator checks are soft checks. |
| A volatility-level control (§43) | Every target is tested **incremental to** VIX level + HAR-RV, or to the futures curve. |
| Fixed effects for heterogeneous groups (§1, §58) | The groups here are regimes. Permutation nulls are blocked by regime and episode, not shuffled day by day. |
| CPCV for cross-validation (§1) | Model selection inside discovery uses purged and embargoed CPCV, and reports PBO. |
| Data already seen | Trial #13 used the Cboe files from 2009 to 2026, but only the VIX3M/VIX slope at monthly rolls against CNDR/PUT/BXM returns. **No confirmatory claim may involve that relationship.** Everything else in the files is unexamined. |
| Don't touch existing systems | New folder `spx_vol/` with its own data store. It doesn't touch the bots, existing databases, the registry or open experiments. |
| Research only | A ~$500 account can't trade SPX, VIX futures or variance. "Economically significant" here means **after realistic costs on the instrument that would express the trade**, judged as research. It is not a plan to trade. |

---

## 2. Data

### 2.1 Inventory

| Series | Source | Start | Status |
| --- | --- | --- | --- |
| SPX daily close | Cboe CSV (in repo) | 1975 *(checked)* | Have |
| SPX daily OHLC | Free public index history (e.g. Stooq/Yahoo `^GSPC`) | Decades *(verify)* | Free. **Open prices need a quality check:** for some vendors and years the SPX "open" is stale or equals the prior close, which would break the Parkinson, Garman–Klass, Rogers–Satchell and Yang–Zhang estimators. |
| VIX OHLC | Cboe (in repo) | 1990-01-02 *(checked)* | Have |
| VIX3M OHLC | Cboe (in repo) | 2009-09-18 in this file *(checked)*. An older VXV series may go back to 2007 *(verify)*. | Have |
| VIX6M OHLC | Cboe (in repo) | 2008-01-02 *(checked)* | Have |
| VIX9D | Cboe | ~2011 *(verify)* | Free |
| VIX1Y | Cboe | Later than VIX6M *(verify)* | Free, optional |
| VVIX | Cboe | ~2006–2007 *(verify)* | Free |
| SKEW | Cboe | 1990 *(verify)* | Free |
| VIX futures, every listed maturity, daily settlement | Cboe CFE historical data | 2004-03 *(verify)* | Free. Needs a per-contract to constant-maturity build (Section 3.2). |
| T-bill rates | Treasury (in repo, 2007+) | 2007 *(checked)* | Have; extend back if needed. |
| SPX intraday bars | No free long history | — | **Not available.** The proxy is SPY 5-minute bars from Alpaca (IEX feed), about 2016 onward *(verify)*. IEX is a thin feed, so it gives realized-variance estimates only, and the 5-minute RV estimator is tested on 2016+ only. |
| SPX option surface: ATM IV, 25-delta put and call IV, term structure, put − call IV | Paid: OptionMetrics, ORATS, Cboe DataShop. EODHD's SPX coverage is **unknown** and, if it exists, starts ~2023. | — | **Not available for 2004+.** User decision (Section 8). |

### 2.2 What the gaps mean

- **The full "core" state vector starts around 2008** (VIX, VIX6M, VVIX, SKEW, VIX futures, SPX OHLC). Adding VIX9D or the file's VIX3M moves the start to 2009–2011. So there are two tiers:
  - **Core vector:** 2008 onward. 2008 is covered only if VVIX and the futures go back that far *(verify)*.
  - **Extended vector:** core plus VIX9D and VIX3M, ~2011 onward.
- **Surface proxies used without option data:**
  - ATM 30-day IV → VIX.
  - Term structure → VIX9D / VIX / VIX3M / VIX6M.
  - Skew → SKEW. It measures the tail, not 25-delta skew, so it is a weaker proxy.
  - Put IV − call IV can't be built. It is dropped until surface data exists.

### 2.3 Point-in-time handling

- Every raw file is snapshotted with a SHA-256 manifest, as in `data_snapshots/vrp_timing_20261002/`. All analysis reads the snapshot, never a live download.
- **Timestamps.** SPX closes at 16:00 ET, while VIX and VIX futures settle later. The rule:
  - A row for day *t* uses only values published by the end of day *t*.
  - Decisions are assumed at the end of *t*.
  - Every forward target starts at the close of *t* and ends at the close of *t + h*.
  - The ~15-minute VIX/SPX close mismatch is disclosed. It is not exploitable by a strategy that acts after both are published.
- Rolling statistics use only rows up to and including *t*. That is enforced by one shared rolling-window helper with a unit test that compares it against a naive recompute on truncated data.
- **Revisions:** Cboe index histories can be revised (e.g. VIX methodology backfills). The snapshot date is recorded, and pre-2003 VIX is the backfilled new-methodology series. That's a reason not to go earlier than 2004 for VIX-based features anyway.

---

## 3. System architecture

```
spx_vol/
  data/        fetchers (one per source) → raw snapshots + manifest
  panel.py     point-in-time daily panel (one row per session, all series aligned)
  rv.py        realized-volatility estimators
  curve.py     VIX futures constant-maturity curve, slope, curvature
  features.py  relationship variables + rolling statistics (shared PIT helper)
  targets.py   forward targets (with explicit horizon and overlap metadata)
  regimes/     HMM, GMM, Markov-switching, change-point, clustering
  anomaly/     detectors + ensemble + explanation
  analogs.py   nearest-neighbour analog engine
  models/      baselines, regressions, tree models, calibration
  validation/  splitter (walk-forward, purged/embargoed CPCV), bootstrap,
               multiple-testing, search ledger
  report/      stage reports; later the daily report
  tests/       unit tests for every module (leakage tests first)
  store/       spx_vol.db (SQLite) — this project's own store, nothing shared
```

### 3.1 Realized volatility (`rv.py`)

- **Estimators:** close-to-close, Parkinson, Garman–Klass, Rogers–Satchell, Yang–Zhang. Plus 5-minute realized variance from SPY bars, 2016+ only.
- **Horizons:** 1, 3, 5, 10, 20, 30 and 60 days, backward-looking for features and forward-looking for targets.
- **How estimators are compared:** "best" means the most accurate *forecast target proxy*. Each daily estimator is scored by how well it predicts the 5-minute realized variance over 2016+, using QLIKE loss, the standard loss for comparing variance forecasts (Patton 2011). The winner is not chosen by which one makes the signal look best. That choice is made once, in Stage 2, and logged.

### 3.2 VIX futures curve (`curve.py`)

- Per-contract daily settlements are turned into a **constant-maturity curve** at 30, 60, 90, 120 and 150 days by linear interpolation in variance time. That avoids the roll jumps a raw VX1/VX2 series has.
- Raw VX1 − VX2 and VX1/VX2 are computed too, because the spec asks for them. They are flagged as having roll artifacts.
- **Slope** = CM60 − CM30. **Curvature** = CM30 − 2·CM60 + CM90.
- **Futures-implied expected VIX change** = CM(h) − VIX spot. This is the market's own forecast, and the baseline for the VIX-change targets.

### 3.3 Relationship variables (`features.py`)

These are the spec's Section 2 list, restricted to what the data supports:
- **IV against realized:** VIX − RV, VIX / RV, at each RV horizon and the estimator chosen in Stage 2. The variance risk premium proxy is VIX² − forecast RV², using the HAR-RV forecast, so it is ex ante.
- **Term structure:** VIX9D − VIX, VIX − VIX3M, VIX3M − VIX6M.
- **Vol of vol:** VVIX / VIX.
- **Skew:** SKEW, and SKEW against VIX.
- **Futures against spot and the curve:** front-month futures − VIX, VX1 − VX2, VX1 / VX2, slope, curvature.
- **Dynamics:**
  - volatility momentum: 5- and 20-day change in log VIX;
  - mean-reversion speed: a rolling AR(1) coefficient of log VIX over 252 days.

**Rolling statistics: a deliberate cut from the spec.**
- The spec's grid is 13 statistics × 6 windows, which is ~78 transforms per variable, or ~1,500 features before interactions. With ~4,000 development days and only a handful of independent volatility episodes, that many features guarantees spurious findings.
- **Proposed core transforms:** percentile rank and robust z-score (median/MAD), at 252 days and the expanding window, plus rate of change at 5 and 20 days.
- The rest of the grid (mean, SD, skewness, kurtosis, acceleration, EWMA, and the 20/60/126/504-day windows) is available as an **extended set**. It is tested only in Stage 5, as a pre-declared sensitivity check: does a finding survive other windows? It is not a pool to search for new findings.
- **Interactions:** the spec's six examples are pre-declared. New interactions found in discovery are logged in the search ledger like everything else.

### 3.4 Targets (`targets.py`)

Each target is stored with its horizon so the splitter can purge correctly.

| Target | Definition | Baseline it must beat |
| --- | --- | --- |
| Forward RV | log of forward RV at h = 1, 5, 10, 20 days | HAR-RV (Corsi 2009) + log VIX |
| VIX change | log VIX(t+h) − log VIX(t) | The futures-implied change (Section 3.2), and AR(1) |
| **Futures return** (tradeable) | CM30 futures return over h | Zero, and a curve-slope-only model |
| Volatility premium payoff (tradeable) | VIX²/12 − realized 21-day variance (a variance-swap proxy) | Unconditional mean, and a VIX-level-only model |
| IV–RV convergence | A hazard: days until VIX/RV returns inside its regime's interquartile range | Regime-only hazard |
| SPX return, and absolute return | Over h = 1, 2, 3, 5, 10, 20, 60 days | Zero / expanding mean for direction; HAR + VIX for absolute return |
| Tail and drawdown | P(max drawdown over h > x%), with x pre-declared at 2, 5 and 10% | VIX-level-only logistic |
| Upside excursion | Max over h | Same |

The spec's 7 horizons × 8 targets = 56 target series. Discovery reports all of them. **Confirmation can use at most 3.**

### 3.5 Regimes (`regimes/`)

- **Methods:** Gaussian HMM (`hmmlearn`), Markov-switching autoregression (`statsmodels`), GMM (`sklearn`), change-point detection (`ruptures`, PELT), and k-means / agglomerative clustering on the core vector.
- **No-lookahead rule.** Regimes are fitted only on data up to *t*, refitted on an expanding window every 21 sessions. The label for day *t* is the **filtered** state probability, not the smoothed one. Smoothed HMM states use future data, which is the most common leakage in regime research. A unit test enforces this.
- **Mapping to the spec's six named regimes** (low/stable, low/rising, medium, high/unstable, crisis, post-shock normalization):
  - These are defined by **rules** on VIX percentile, the 20-day change and time since the last VIX peak. They act as a fixed, interpretable reference labelling.
  - Each statistical method's states are compared against them (agreement, persistence, transition matrix).
  - Statistical labels are not renamed after the fact to fit the narrative.
- **Number of regimes:** chosen by BIC within development data only, then frozen.
- **Usefulness test:** does conditioning on a regime improve out-of-sample prediction over the unconditional version? That is decided per method in Stage 4/8. "The clusters look sensible" doesn't count.

### 3.6 Anomaly detection (`anomaly/`)

- **First tier**, simple and interpretable:
  - robust Mahalanobis distance (MCD covariance);
  - GMM negative log-likelihood;
  - regime-conditional density (the percentile of today's vector within its own filtered regime);
  - EVT (peaks over threshold, GPD) for the tail of each univariate relationship.
- **Second tier**, kept only if it beats the first out of sample: Isolation Forest, LOF, One-Class SVM, PCA reconstruction error, and an autoencoder (PyTorch, which is installed).
- Every detector is fitted on a rolling or expanding window up to *t* and scores *t*.
- **Ensemble.**
  - Each detector's raw score becomes its out-of-sample percentile rank among past scores.
  - The weights are estimated by **nested walk-forward**: weights at time *t* come only from the predictive usefulness the detectors showed before *t*, measured on one pre-declared primary target.
  - Weights are reported with their stability over time, plus a detector correlation matrix: nine detectors that agree are really one.
  - The 0–100 score is the percentile of the weighted score.
- **Explanation.**
  - For Mahalanobis, the score splits exactly into per-variable contributions (via the Cholesky factor), and those are reported.
  - For the other detectors, SHAP on a surrogate model, or leave-one-variable-out deltas.
  - Each driver comes with its univariate percentile **and** its conditional percentile given the other variables. That gives the spec's "each variable looks normal but the combination is rare" output.

### 3.7 Analog engine (`analogs.py`)

- **Distance options:** Mahalanobis on the robust-standardized core vector (primary), PCA-space Euclidean, cosine, and regime-restricted nearest neighbours. Only history before *t* is searched, with an exclusion gap of at least 2× the longest target horizon.
- **Overlap is the big problem.** Twenty-three "analogs" taken from consecutive days of the same 2020 episode are really one observation.
- **Fix:** collapse analogs into **independent episodes** (days within h sessions of each other count once) and report both counts, e.g. "23 days, 4 episodes".
- **Output per horizon:**
  - mean, median, SD, the 5/25/75/95th percentiles, win probability and N, as the spec asks;
  - a bootstrap interval resampled by episode;
  - the same statistics for the **unconditional** and the **VIX-level-only** analog sets. Without those comparisons the analog output has no context.

### 3.8 Models and distributional forecasts (`models/`)

- **Model ladder,** simplest first:
  1. the unconditional value;
  2. the baseline for each target (Section 3.4);
  3. linear, logistic and quantile regression on a handful of features;
  4. LightGBM / XGBoost (XGBoost is installed; LightGBM and SHAP need installing).
- **Rule from the spec, adopted:** a more complex model is used only if it beats the simpler one out of sample, with the difference significant under a Diebold–Mariano test with HAC errors, or under a bootstrap.
- **Distributions:**
  - quantile regression at 5/25/50/75/95, fitted to avoid quantile crossing, for continuous targets;
  - calibrated logistic or isotonic regression for event probabilities.
- **Scoring:**
  - probabilities: Brier score (with its reliability and resolution parts), log loss, reliability diagrams, and the calibration slope and intercept;
  - quantiles: pinball loss, and interval coverage (does the 90% interval contain 90%?).
- **Feature attribution:** SHAP for tree models, coefficients for linear ones. Attribution is a description of the model, not evidence that a relationship is real.

---

## 4. Validation framework

### 4.1 Time splits (proposed; user decision)

| Block | Dates | Use |
| --- | --- | --- |
| Development | 2004 (or the core-vector start) → 2016-12 | Discovery, walk-forward model selection, CPCV. **Contains 2008, 2010, 2011, 2015.** |
| Validation | 2017-01 → 2020-12 | Out-of-sample check of what discovery finds, used to choose ≤ 3 confirmatory hypotheses. **Contains 2017, February 2018, March 2020.** |
| **Locked test** | 2021-01 → 2026-10-01 | Touched once, in Stage 9, after pre-registration. **Contains 2022.** |
| Prospective | 2026-10-02 onward | Forward data that nobody has seen. The report runs on it after build. |

- **Why the locked test is 2021+:** it is the only way the confirmatory test contains a real stress year (2022) that no one has seen. The cost is that March 2020 sits in validation, so it informs the choice of hypotheses.
- **Alternative:** lock 2019+ so that March 2020 is held out too, with development shortening to 2004–2014 and validation to 2015–2018.

### 4.2 Statistics

- **Overlapping targets:** HAC (Newey–West) errors with lag ≥ h, and a stationary bootstrap with mean block ≥ 2h. The effective N is reported next to the raw N.
- **Purge and embargo:** every train/test boundary purges training rows whose target window overlaps the test block. The embargo after each test block is max(h, 21) sessions.
- **CPCV and PBO** for model selection within development (López de Prado; Bailey et al. 2017).
- **Search breadth:**
  - Benjamini–Hochberg FDR across everything screened in discovery, used for ranking, not for claims.
  - White's Reality Check / Hansen SPA for "is the best of these better than the baseline?"
  - Bonferroni across the ≤ 3 confirmatory tests.
  - DSR (the pre-live checklist, §1) using the search ledger's breadth.
- **Hard gate for any confirmatory hypothesis:** an out-of-sample improvement over the target's baseline (Section 3.4), with significance at the declared α. Example: for forward RV, beating HAR + VIX by a pre-declared QLIKE margin.
- **Power, before anything is locked:** computed with `power_analysis.py` at the locked test's effective N. A design with < 80% power at the effect floor gets reconsidered before registration, not after.

### 4.3 Falsification checklist (run on every candidate in validation, then again at the lock)

1. **Leakage:** the result disappears when the target is shuffled within regime-blocked episodes (a placebo). The result also survives a deliberate one-day extra lag on every feature.
2. **Regime-specific?** The sign holds within each rule-based regime that has enough N. It is reported per regime.
3. **Sample size:** effective N and the number of episodes, not just days.
4. **Lookback periods:** the result survives the extended windows (Section 3.3).
5. **Estimator choice:** it survives at least one other RV estimator.
6. **Costs**, for tradeable targets: VX futures at 1 and 2 ticks per side plus fees. The variance-swap proxy is haircut by a pre-declared bid/ask on SPX options; until we have real SPX spreads, use SPY EODHD medians (§26) as a stand-in and say so.
7. **Named episodes:** the 2008 financial crisis, 2017 (record-low vol), February 2018 (Volmageddon), March 2020, 2022 (slow bear market with low VIX). Each is reported separately. The result must not depend on any one of them: leave-one-episode-out keeps the sign.
8. **Later unseen data:** the locked test, then prospective data.
9. **Multiple testing:** still significant after the corrections in Section 4.2.

---

## 5. Three labels kept separate in every report

- **Unusual:** a high anomaly score. A descriptive statement, with no claim attached.
- **Predictive:** beats the baseline out of sample, after corrections.
- **Economically significant:** predictive **and** positive after realistic costs on an instrument that expresses the view, at 0.5×, 1× and 1.5× cost (§26 convention).

The daily report labels every line with one of these three.

---

## 6. Implementation plan

Each stage ends with a short report to the user and **stops for approval** before the next, as the spec requires.

| Stage | Spec step | Output | Notes |
| --- | --- | --- | --- |
| 0 | — | Data audit: every source's real start date, gaps, OHLC quality, and futures contract coverage. Optional EODHD SPX-chain check (~a few hundred requests). Power estimate. | No forward returns computed. |
| 1 | 1 | Snapshots + manifest; `panel.py`; PIT tests. | Library installs: statsmodels, hmmlearn, ruptures, arch, lightgbm, shap. |
| 2 | 2–3 | Descriptive statistics on **development only**. RV estimator comparison (QLIKE). Stationarity (ADF/KPSS) and structural breaks (Bai–Perron or PELT). | Descriptive. |
| 3 | 4 | Regime models, filtered labels, comparison with the rule-based labels. | |
| 4 | 5 | Univariate relationship anomalies, unconditional against regime-conditional. | First predictive screens, development only, logged. |
| 5 | 6 | Multivariate anomalies, ensemble, explanations. | |
| 6 | 7 | Analog engine with episode counting. | |
| 7 | 8 | Predictive tests against baselines, walk-forward + CPCV in development. Validation block, once. | Picks ≤ 3 candidates. |
| 8 | — | **Pre-registration** of ≤ 3 hypotheses under `tiered_v1`: hash, ledger row, power block. **Uses the last slot.** | User approval required. |
| 9 | 9 | The locked test, run once. Verdict. | |
| 10 | 10–11 | Ensemble and distributional models, stress tests, on what survived. | If nothing survives, the engine can still be built as a **descriptive** tool, labelled "unusual" only. |
| 11–12 | 11–12 | Daily report (an HTML page or a DB-backed dashboard), run nightly against prospective data. | The task follows the existing pattern (§60) once it is approved. |

### 6.4 Search ledger

Every configuration evaluated against a target in Stages 4–7 is logged to `spx_vol.db:search_ledger`. Each row holds: feature set, transform, window, regime method, detector, target, horizon, metric, data block, and timestamp. It is append-only. The DSR, PBO and Reality Check use it, and so does the disclosure in the pre-registration.

---

## 7. Realistic expectations

- **Well-documented, likely to be confirmed:** VIX mean-reverts, and volatility clusters (HAR-RV works).
- **Likely priced in already:** most of that mean reversion is already in the futures curve. A sign of "VIX will fall" does not imply that short VIX futures make money.
- **Known and real, but risky:** the average volatility premium (VIX² > realized variance), which has crash risk.
- **The open questions this engine can answer:** whether **conditional** information (regime, relationship anomalies) improves on those baselines out of sample. A small improvement that survives is the realistic best case.
- **Statistically the hardest:** tail and drawdown prediction. Independent crisis episodes since 2004 number in the single digits.

---

## 8. Decisions needed before Stage 0

1. **The two-part design:** discovery on development data, then up to 3 confirmatory hypotheses that use the last slot.
2. **Split dates** (Section 4.1): the 2021+ lock, or the 2019+ alternative.
3. **The SPX option surface:** proceed with VIX-family proxies only (recommended for now), or also run the EODHD SPX-chain coverage check (~a few hundred requests), or price a paid source (the ORATS purchase was declined before).
4. **Downloads and installs:** free public data from Cboe, CFE and a daily-OHLC source; pip installs of statsmodels, hmmlearn, ruptures, arch, lightgbm and shap.
5. **The feature cut** (Section 3.3): the core transforms for discovery, with the full grid as sensitivity only.

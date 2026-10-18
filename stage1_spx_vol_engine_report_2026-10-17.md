# SPX volatility-state engine: Stage 1 report (2026-10-17)

**What Stage 1 was:** data cleaning, feature construction, and a comparison of volatility estimators on development years only (2008-01-02 → 2016-12-30). It was approved by the user on 2026-10-17.

**What it was not:** a test of any hypothesis. No hypothesis was formed, no slot used and no trading P&L computed. BXM, PUT, CNDR and BFLY weren't touched, and nothing from 2017 onward was loaded for analysis.

**The rules came first.** The protocol (`spx_vol/stage1_protocol.md`) was committed as **`e2ff0b6` at 2026-10-17 22:29:42 ET**, before any feature was computed or anything scored. The only scored run was logged to the search ledger at 22:33:42 ET.

---

## 1. Plain-language summary

- **At the primary 21-day horizon, no estimator built from SPX's own price history beats VIX as a forecast of next-month SPX volatility.**
  - VIX, used directly as the forecast, had a clearly lower forecast error (QLIKE) than the best history-based model, the standard HAR model on close-to-close returns. The 95% interval of the difference excludes zero.
  - The best history-based model did not beat a plain trailing 21-day realized volatility or an exponentially weighted average (EWMA) by more than the noise.
- **The fancier range-based estimators** (Parkinson, Garman–Klass, Rogers–Satchell, Yang–Zhang) **did not beat simple close-to-close.** Following the pre-set rule, the features use close-to-close realized volatility.
- **At the secondary 5-day horizon** the picture is similar: raw VIX has the lowest error, and Parkinson-HAR is not significantly better than close-to-close HAR. One benchmark (calibrated VIX) broke down at 5 days (Section 4.3).
- **The data is clean enough to build on.** 127 features were built with no look-ahead, which the tests confirm. A few small gaps remain and are listed in Section 2.4.

**Reading the result.** It's a valid result, and it matches the published literature: implied volatility is a better forecast of SPX's next month than past prices are. VIX also carries a risk premium, which makes it run high on average, and QLIKE penalizes forecasts that are too low more than forecasts that are too high, so that premium helps VIX on this loss. On MSE (squared error) the ranking is different. Section 4 has both.

---

## 2. Cleaning (Task A)

Raw files were never modified. Outputs are in `data_snapshots/spx_vol_engine/clean/`: `spx_daily.csv`, `vol_indices.csv`, `vx_futures.csv`, plus `manifest.json` with the source SHA-256s, row counts by block and the rows affected by each rule.
- The cleaning code runs on all years.
- For 2017 onward the manifest records **row counts only**, with no value statistics.

### 2.1 Calendar

NYSE sessions are taken from the Yahoo `^GSPC` dates: 2,267 sessions in development, 1,007 in validation and 1,454 locked.

### 2.2 SPX

| Rule | Result (development years) |
| --- | --- |
| Use Yahoo O/H/L/C; Cboe close kept as a cross-check | 2,267 rows; Cboe close present on all |
| Cboe and Yahoo closes differ by more than 0.1% | **0 days** |
| Invalid OHLC (H < L, or O/C outside the range) | 0 |
| **Stale open** (open = previous close) | **164 days** (157 of them in the 2010–2016 evaluation period), mostly 2011–2013 |

**Could not be cleaned:** the 164 stale opens have no free fix without SPY, which the SPX-only rule forbids except for 2004–2006. Per the protocol, on those days the open-based estimators fall back to close-to-close for that day. SPY wasn't used anywhere.

### 2.3 Volatility indexes

- Closes only, aligned to NYSE sessions.
- VIX rows on market-closed days: **0 in development** (1 before 2008, 33 in the locked years; dropped and counted only).
- VVIX's 2006-03-15 print is flagged (outside the window).
- The single high < low rows in VIX6M (2019) and VIX1Y (2018) are flagged; only closes are used.

### 2.4 VIX futures

| Rule | Rows affected |
| --- | --- |
| Prices before 2007-03-26 divided by 10 | 3,942 (all before 2008, so none in the window) |
| 2013 handover: one row per contract and date | 1,427 duplicates removed. **No missing sessions remain** (previously a 95-day hole). |
| Missing or ≤ 0 settlement dropped | 331 in development, 33 before 2008 |
| Rows on non-sessions dropped | 9 in development (9 each in validation and locked, counted only) |
| Zero open, high < low | Flagged, not dropped; only the settlement is used |
| Expiry date | Last trade date before 2013; Cboe's listed expiry from 2013. For the 44 development-era contracts with a listed expiry, it equals the last trade date in every case. |

19,684 development rows remain, across 274 contracts in all years.

**Remaining gaps and quirks, kept as they are and flagged:**
- **VVIX:** 2 missing sessions (2010 and 2013). **SKEW:** 1 missing (2011-02-09). Their features are missing on those days only (1–4 rows each).
- **Constant-maturity 30-day point:** extrapolated (no contract is less than 30 days from expiry) on 113 days, flagged `flag_cm_extrapolated`. CM90 and CM150 are never missing.
- **Front-month rolls:** 108 in 2008–2016, flagged `flag_vx_roll`. `vx1_minus_vx2` jumps on those days by construction.
- **Late starts:** VIX3M from 2009-09-18 and VIX9D from 2011-01-04, so their features start then.

---

## 3. Features (Task B)

All 127 columns are exactly as listed in the protocol (Section 2), built with close-to-close RV as the pre-set rule chose.
- **Base variables (19):** VIX; RV5 and RV21; VIX − RV21; VIX / RV21; VIX / RV5; trailing VRP = (VIX/100)² − (RV21/100)²; VIX9D − VIX; VIX − VIX3M; VIX3M − VIX6M; futures basis CM30 − VIX; futures slope CM60 − CM30; curvature CM30 − 2·CM60 + CM90; VX1 − VX2; VVIX / VIX; SKEW; 5- and 20-day VIX momentum; rolling 252-day AR(1) of log VIX.
- **Transforms:** for the 16 level and spread variables, raw, percentile rank (252-day and expanding), robust z-score (252-day and expanding), and 5- and 20-day change, so 7 each. For the 3 dynamics variables: raw, 252-day percentile and 252-day robust z.
- **Interactions:** the 6 pre-declared ones.
- **Not built:** any put − call IV or option-based skew feature, since there is no SPX option data.

**Files:**
- `data_snapshots/spx_vol_engine/features/features_dev_2008_2016.csv`: 2,267 rows × 127 features, plus 3 flag columns.
- `vx_curve_dev_2008_2016.csv`: the curve.

**When features become available:** 2008-01/03 for raw values and short changes; late 2008 to early 2009 for 252-day statistics; 2009-09 to 2010 for the VIX3M features; 2011–2012 for the VIX9D features.

**No look-ahead**, checked by tests on synthetic data:
1. Features computed on data cut at a date are identical to the full-data features up to that date.
2. Randomly changing every input after a date leaves every earlier feature exactly unchanged.

**No feature was related to any target in this stage.**

---

## 4. Estimator comparison (Task C)

### 4.1 Setup

All of this is as committed in the protocol:
- **Target:** SPX forward close-to-close realized variance over 21 sessions (primary) and 5 sessions (secondary), annualized.
- **Forecast origins:** 2010-01-04 → 2016-11-30 for h = 21 (1,741 dates) and → 2016-12-22 for h = 5 (1,757 dates).
- **Fitting:** expanding-window OLS refitted every 21 sessions, with a purge of h plus an embargo of h. The training data starts in 2008, so the 2008 crisis is in training only.
- **Bootstrap:** circular block, blocks of 42 days (h = 21) and 21 days (h = 5), 2,000 replications.
- **Losses:** QLIKE (primary) and MSE.

**Model names:**

| Name | What it is |
| --- | --- |
| `_raw21` | That estimator's trailing 21-day value used as the forecast |
| `_har` | A fitted model on its 5-, 21- and 63-day values |
| `VIX_raw` | (VIX/100)² |
| `VIX_cal` | a + b·(VIX/100)², fitted |
| `EWMA` | Exponentially weighted average, λ = 0.94 |

Estimators: **CC** close-to-close, **P** Parkinson, **GK** Garman–Klass, **RS** Rogers–Satchell, **YZ** Yang–Zhang.

### 4.2 Results, h = 21 (primary)

Lower is better. The QLIKE interval is the bootstrap 95% interval of the model's mean loss.

| Model | QLIKE | 95% interval | MSE (×10⁻⁴) | Δ QLIKE vs `CC_har` [95% interval] |
| --- | --- | --- | --- | --- |
| VIX_cal | **0.294** | 0.201–0.423 | 7.79 | −0.102 [−0.179, −0.004] |
| VIX_raw | 0.307 | 0.245–0.379 | 8.50 | −0.089 [−0.128, −0.051] |
| EWMA | 0.394 | 0.261–0.559 | 7.60 | −0.002 [−0.121, +0.142] |
| CC_har | 0.396 | 0.328–0.469 | 10.95 | — |
| P_har | 0.408 | 0.340–0.480 | 10.61 | +0.012 [−0.002, +0.025] |
| YZ_har | 0.427 | 0.357–0.503 | 11.52 | +0.031 [+0.010, +0.050] |
| GK_har | 0.431 | 0.360–0.507 | 11.32 | +0.035 [+0.013, +0.055] |
| RS_har | 0.441 | 0.369–0.521 | 12.20 | +0.045 [+0.019, +0.069] |
| CC_raw21 | 0.539 | 0.355–0.751 | 9.11 | +0.143 [−0.029, +0.343] |
| P_raw21 | 0.616 | 0.397–0.880 | **7.09** | +0.220 [+0.012, +0.471] |
| YZ_raw21 | 0.631 | 0.409–0.898 | 7.23 | +0.235 [+0.021, +0.491] |
| RS_raw21 | 0.675 | 0.440–0.966 | 7.51 | +0.279 [+0.049, +0.549] |
| GK_raw21 | 0.678 | 0.436–0.977 | 7.31 | +0.282 [+0.047, +0.563] |

**Rule A (which estimator the features use):**
- The best of the five HAR models is **CC_har** itself, so close-to-close is adopted.
- The range-based HAR models are significantly *worse* than close-to-close: GK, RS and YZ have intervals entirely above zero, and P's touches zero.

**Rule B (does the best history-based model, CC_har, beat the benchmarks beyond noise?)**

| Benchmark | Δ QLIKE, CC_har − benchmark [95% interval] | Beats beyond noise? |
| --- | --- | --- |
| Trailing RV (CC_raw21) | −0.143 [−0.342, +0.029] | **No** (interval includes 0) |
| EWMA | +0.002 [−0.142, +0.121] | **No** |
| VIX_raw | +0.089 [+0.051, +0.128] | **No: VIX is significantly better** |
| VIX_cal | +0.101 [+0.004, +0.179] | **No: VIX is significantly better** |

### 4.3 Results, h = 5 (secondary; no decision weight)

| Model | QLIKE | 95% interval | MSE (×10⁻⁴) |
| --- | --- | --- | --- |
| VIX_raw | **0.474** | 0.413–0.537 | 12.07 |
| P_har | 0.507 | 0.439–0.582 | 12.56 |
| CC_har | 0.515 | 0.441–0.599 | 13.15 |
| EWMA | 0.519 | 0.417–0.642 | 12.34 |
| YZ_har | 0.532 | 0.460–0.610 | 13.78 |
| GK_har | 0.536 | 0.464–0.613 | 13.38 |
| RS_har | 0.549 | 0.474–0.628 | 14.50 |
| CC_raw21 | 0.628 | 0.488–0.793 | 13.83 |
| P_raw21 | 0.675 | 0.514–0.868 | 12.71 |
| YZ_raw21 | 0.693 | 0.526–0.899 | 13.06 |
| GK_raw21 | 0.733 | 0.552–0.958 | 13.21 |
| RS_raw21 | 0.740 | 0.560–0.966 | 13.46 |
| VIX_cal | 1,463 (broken; see below) | — | 11.63 |

- **Rule A at h = 5:** P_har is the best HAR model, but it is not significantly better than CC_har (−0.008 [−0.029, +0.010]). It would also select close-to-close.
- **Rule B at h = 5:** P_har beats trailing RV (−0.120 [−0.258, −0.007]), but not EWMA (−0.012 [−0.101, +0.066]) or raw VIX (it's worse: +0.034 [+0.013, +0.057]).
- **Why VIX_cal broke at h = 5:** the fitted line had a slope above 1 and a negative intercept (about −0.026 + 1.23·VIX²/10⁴ at the first fit). So on calm days, with VIX below ~15, it forecast a *negative* variance. The protocol's floor of 1e-6 then applied on 289 days, and QLIKE is enormous for a near-zero forecast. That's a real weakness of a linear model in variance, kept as it is. Its MSE (11.63) is normal.

### 4.4 MSE tells a different story (secondary)

- Under MSE at h = 21, the plain trailing range estimators (P_raw21 at 7.09, YZ, GK, RS) and EWMA are lowest, and every fitted HAR is highest (10.6–12.2).
- MSE is dominated by a few very-high-volatility days, which makes it a noisy loss here.
- The HAR fits lean on the 2008 crisis in training (first-fit intercept 0.065 annualized variance). That makes them forecast high in calm years, which QLIKE penalizes less than MSE does.
- MSE carries no decision weight under the protocol.

### 4.5 Caveats

- One evaluation period (2010–2016), dominated by calm markets with a few spikes (2010, 2011, 2015–16). The intervals are wide.
- These are 13 models compared without a multiple-testing correction, as the protocol says. The search ledger records all 26 runs.
- VIX's advantage under QLIKE is partly mechanical: VIX runs high (the volatility premium), and QLIKE punishes forecasts that are too low more than ones that are too high.

---

## 5. Search ledger (Task D)

- `spx_vol/store/spx_vol.db`, table `search_ledger` (append-only).
- **26 rows** = 13 models × 2 horizons, from **1** real execution (run 2026-10-18 02:33:42–43 UTC). That matches the number of runs exactly.
- Code was checked on synthetic data first; synthetic runs are never logged.
- Feature construction relates nothing to a target, so it has no ledger rows.

## 6. Deviations from the protocol

1. **D1 (declared in the protocol itself):** the futures curve is interpolated linearly in days to expiry on price, not "variance time". The design doc was updated the same way.
2. **D2 (found while building features, before any feature touched a target):** the protocol said 252-day statistics "need 252 values". Taken literally, one missing VVIX or SKEW day blanked 252 days of every 252-day statistic.
   - The window now needs ≥ 250 non-missing values, and the percentile rank uses the actual count.
   - Effect: those features start 2 sessions earlier, and only the genuinely missing days stay blank.
   - It affects no score. A test covers it.

No other deviations.

## 7. Code and tests

- **Code:** `spx_vol/common.py` (paths, block dates and `dev_guard`), `clean.py`, `estimators.py`, `features.py`, `compare.py`, `test_stage1.py`.
- **The guard:** `dev_guard()` raises `LockedDataError` for any date after 2016-12-31 (or before 2008-01-02). The feature loader stops reading each clean file at its first 2017 row, so later years are never parsed for analysis.
- **Tests:** 13, all passing (`spx_vol\.venv\Scripts\python -m unittest test_stage1`, run from `spx_vol/`). They cover:
  - the guard (including that the analysis functions refuse 2017 dates);
  - the stale-open fallback;
  - Yang–Zhang against a hand computation;
  - QLIKE;
  - the forward target and its end-of-window cutoff;
  - the purge/embargo of training rows;
  - curve interpolation;
  - feature count;
  - the missing-value window rule;
  - the two look-ahead tests.
- **Data** (clean files, features, results JSON) is in `data_snapshots/spx_vol_engine/` and isn't committed.

## 8. What Stage 1 does not decide

Stage 1 makes no claim about any feature. What happens next (Stage 2: exploratory statistics, stationarity and structural breaks on development data) needs your approval.

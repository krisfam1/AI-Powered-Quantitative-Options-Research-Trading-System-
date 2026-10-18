# Stage 1 protocol: cleaning rules, feature list, estimator comparison (fixed 2026-10-17)

**Written and committed BEFORE any feature was computed or any estimator was scored.** Nothing below may change after scores are seen. Any deviation found necessary during the run is reported as a deviation; the protocol itself is not edited.

**Scope:**
- Development years only: 2008-01-02 → 2016-12-30.
- Data from 2004–2007 stays on disk, unused.
- Nothing from 2017 onward is loaded for analysis.
- Every analysis function calls `dev_guard()`, which raises an error if any date is after 2016-12-31.
- Cleaning code runs on all years, but for 2017+ it only counts rows.

**SPX-only rule:**
- The only target here is SPX's own forward realized variance.
- SPY isn't used. The stale SPX opens in 2008–2016 are handled by the fallback rule in Section 3.1, not by SPY repair.
- The option-index series (BXM, PUT, CNDR, BFLY) aren't touched in this stage.

---

## 1. Cleaning rules (Task A)

Raw files in `data_snapshots/spx_vol_engine/` are never modified. Output goes to `data_snapshots/spx_vol_engine/clean/`, with a manifest of source hashes, row counts and the rows affected by each rule.

1. **Calendar:** NYSE sessions are the Yahoo `^GSPC` dates. Every series is aligned to them, and rows on non-sessions are dropped and counted (VIX has 34).
2. **SPX:**
   - Use Yahoo `^GSPC` O/H/L/C, which is internally consistent.
   - Cboe's SPX close is kept as a cross-check column. A date where the two differ by more than 0.1% is flagged; Stage 0 found none in 2008–2016.
   - `stale_open` = 1 when open == previous close exactly.
   - A row is flagged invalid if H < L, or O or C falls outside [L, H]. Invalid rows get the same fallback as stale opens.
3. **Volatility indexes:**
   - Use closes only for VIX, VIX9D, VIX3M, VIX6M, VVIX and SKEW.
   - Flag VVIX's 2006-03-15 print as `bad_print`. It's outside the window, so the flag is informational.
   - The single high < low rows in VIX6M (2019-07-05) and VIX1Y (2018-12-03) are flagged; only closes are used, so nothing else changes.
4. **VIX futures:**
   - Monthly contracts only, settlement price only.
   - Divide every price field by 10 for trade dates before 2007-03-26.
   - Drop rows whose settlement is missing or ≤ 0.
   - Open = 0 and high < low are flagged, not dropped, since only the settlement is used.
   - **2013 handover:** key each row by contract expiry month and keep one row per (contract, date): the current-format row if its settlement is > 0, else the archive row.
   - Drop rows on non-sessions.
   - Expiry proxy = the contract's last trade date in the data.
   - DTE = calendar days from the trade date to the expiry proxy.

## 2. Feature list (Task B)

Computed on 2008-01-02 → 2016-12-30 only, with **no warm-up data from before 2008**. Every value at date *t* uses data up to the close of *t* only.

**Notation:**
- RV*w* = the chosen estimator's *w*-day window estimate, annualized and in vol points: 100·√(annualized variance). The chosen estimator comes from the rule in Section 3.5; if that rule picks close-to-close, RV is close-to-close.
- CM*τ* = constant-maturity VIX futures price at *τ* calendar days.

### 2.1 Futures curve construction

- **CMτ**, for τ ∈ {30, 60, 90, 120, 150}: interpolate linearly in DTE between the two contracts that bracket τ, i.e. F₁ + (F₂ − F₁)(τ − d₁)/(d₂ − d₁).
  - If τ is below the shortest DTE, use the shortest contract and set `cm_extrapolated` = 1. If τ is above the longest, the value is missing.
  - **Deviation from the design text:** design §3.2 said "linear in variance time". Futures prices are expected VIX levels, not variances, so interpolating in DTE on price is the standard constant-maturity convention. The design is updated to match.
- **VX1** = the contract with the smallest DTE ≥ 1. **VX2** = the next one.
- **`vx_roll`** = 1 on a day when VX1's identity changes from the previous session.

### 2.2 Base variables (19)

| # | Name | Formula | Available from |
| --- | --- | --- | --- |
| 1 | `vix` | VIX close | 2008 |
| 2 | `rv5` | RV5 | 2008 |
| 3 | `rv21` | RV21 | 2008 |
| 4 | `vix_minus_rv21` | VIX − RV21 | 2008 |
| 5 | `vix_over_rv21` | VIX / RV21 | 2008 |
| 6 | `vix_over_rv5` | VIX / RV5 | 2008 |
| 7 | `vrp_trail` | (VIX/100)² − (RV21/100)² | 2008 |
| 8 | `ts_9d` | VIX9D − VIX | 2011-01-04 |
| 9 | `ts_3m` | VIX − VIX3M | 2009-09-18 |
| 10 | `ts_6m` | VIX3M − VIX6M | 2009-09-18 |
| 11 | `fut_basis` | CM30 − VIX | 2008 |
| 12 | `fut_slope` | CM60 − CM30 | 2008 |
| 13 | `fut_curv` | CM30 − 2·CM60 + CM90 | 2008 |
| 14 | `vx1_minus_vx2` | VX1 − VX2 (raw; jumps at rolls, see `vx_roll`) | 2008 |
| 15 | `vvix_over_vix` | VVIX / VIX | 2008 |
| 16 | `skew` | SKEW close | 2008 |
| 17 | `vix_mom5` | ln VIX_t − ln VIX_{t−5} | 2008 |
| 18 | `vix_mom20` | ln VIX_t − ln VIX_{t−20} | 2008 |
| 19 | `vix_ar1_252` | OLS slope of ln VIX_t on ln VIX_{t−1}, last 252 sessions | 2009 |

`vrp_trail` uses trailing realized variance, which is known at *t*. The design's ex-ante, HAR-based VRP is deferred: it needs out-of-sample fitted models and would only exist from 2010.

### 2.3 Transforms

**For base variables 1–16, each gets these 7 columns:**
- `raw`.
- `pct252`: the percentile rank of x_t among the last 252 values including *t*, as (rank − 1)/(n − 1). Needs 252 values.
- `pctexp`: the same, over all values from the first available up to *t*. Needs 252 values.
- `rz252`: (x_t − median₂₅₂) / (1.4826 · MAD₂₅₂). Missing if MAD = 0.
- `rzexp`: the same, over an expanding window. Needs 252 values.
- `chg5` and `chg20`: change over 5 and 20 sessions.
  - For positive levels (variables 1, 2, 3, 5, 6, 15, 16) this is a log difference.
  - For spreads (variables 4 and 7–14) it is a plain difference.

**For base variables 17–19:** `raw`, `pct252` and `rz252`.

### 2.4 Pre-declared interactions (6)

| Name | Formula |
| --- | --- |
| `ix_vrpgap_slope` | rz252(`vix_minus_rv21`) × rz252(`fut_slope`) |
| `ix_vrpgap_vvix` | rz252(`vix_minus_rv21`) × rz252(VVIX), with rz252 of the VVIX level computed for this term only |
| `ix_ratio_skew` | rz252(`vix_over_rv21`) × rz252(`skew`) |
| `ix_vixz_rvz` | rz252(`vix`) × rz252(`rv21`) |
| `ix_vvixz_minus_vixz` | rz252(VVIX) − rz252(`vix`) |
| `ix_slopepct_vrppct` | pct252(`fut_slope`) × pct252(`vrp_trail`) |

**Total: 16 × 7 + 3 × 3 + 6 = 127 feature columns,** plus flags (`vx_roll`, `cm_extrapolated`, `stale_open`).
- **Not built:** put IV − call IV, 25-delta skew and option-based ATM IV, because there is no SPX option data.
- **No feature is related to any target in this stage.**

**Look-ahead tests** (`spx_vol/test_stage1.py`):
1. **Truncation:** features computed on data cut at a date *T* must equal the full-data features at every date ≤ *T*.
2. **Perturbation:** multiplying every input after *T* by random factors must leave every feature at dates ≤ *T* unchanged.

---

## 3. Estimator comparison (Task C)

### 3.1 Daily variance proxies

All use SPX Yahoo O/H/L/C. Notation:
- r_t = ln(C_t/C_{t−1}), the close-to-close return.
- o_t = ln(O_t/C_{t−1}), the overnight return.
- u = ln(H/O), d = ln(L/O), c = ln(C/O).

| Estimator | Daily proxy |
| --- | --- |
| CC (close-to-close) | r_t² |
| P (Parkinson, with an overnight term) | o_t² + (ln H/L)² / (4 ln 2) |
| GK (Garman–Klass, with an overnight term) | o_t² + 0.5(ln H/L)² − (2 ln 2 − 1)c² |
| RS (Rogers–Satchell, with an overnight term) | o_t² + u(u − c) + d(d − c) |
| YZ (Yang–Zhang) | Window formula only: σ²_o + kσ²_c + (1 − k)·mean(RS intraday), with k = 0.34 / (1.34 + (n + 1)/(n − 1)). σ²_o and σ²_c are sample variances (n − 1) of the overnight and open-to-close returns. |

- **The overnight term is added** to P, GK and RS because the target, close-to-close variance, includes the overnight move. YZ includes it by construction.
- **Stale-open or invalid-OHLC days:** the open is unknown. For P, GK and RS the daily proxy falls back to r_t². For YZ the day counts as overnight = r_t, open-to-close = 0, RS term = 0. The number of fallback days is reported.
- **Window estimate:** E_w(t) = 252 × the mean of the daily proxy over sessions t−w+1 … t (YZ: 252 × its formula with n = w). Units are annualized variance.

### 3.2 Target, horizons and losses

- **Target:** forward close-to-close realized variance, y_h(t) = (252/h) · Σ_{i=1..h} r²_{t+i}, annualized.
  - This is the quantity relevant to "VIX minus subsequently realized SPX volatility".
  - It must lie entirely in the development years: t + h ≤ 2016-12-30, or y is missing.
- **Horizons (2):** h = 21 (primary; matches VIX's 30 calendar days) and h = 5 (secondary).
- **Losses**, on annualized variance:
  - QLIKE = y/f − ln(y/f) − 1 (primary; robust to noise in the target, Patton 2011).
  - MSE = (y − f)² (secondary).
- **Floor:** a forecast f ≤ 1e-6 is set to 1e-6, and the number of floors is reported.

### 3.3 Models (13 per horizon, so 26 runs)

**Estimator models,** for each E ∈ {CC, P, GK, RS, YZ}:
- **`E_raw21`:** f = E_21(t). No fitting.
- **`E_har`:** f = a + b₁·E_5 + b₂·E_21 + b₃·E_63, fitted by OLS (a HAR-style model with 5/21/63-session windows).

**Benchmarks:**
- **Trailing realized vol:** `CC_raw21`, which also appears among the estimator models.
- **`VIX_raw`:** f = (VIX/100)². VIX is a 30-day measure; it is used for h = 5 as well, and the mismatch is noted.
- **`VIX_cal`:** f = a + b·(VIX/100)², fitted by OLS.
- **`EWMA`:** σ²_t = 0.94·σ²_{t−1} + 0.06·252·r_t², seeded with the mean of the first 21 values of 252·r²; f = σ²_t.
- **`CC_har`:** the standard HAR benchmark, also among the estimator models.

### 3.4 Out-of-sample scheme

- **Forecast origins** run from 2010-01-04 to the last *t* with t + h ≤ 2016-12-30. All 13 models are scored on the same dates: the intersection where every model has a forecast and y exists.
- **Expanding-window refits** every 21 sessions, starting at the first origin.
  - At a refit date *T*, the training rows are the dates *s* with s ≤ T − 2h. That is a purge of h (the target ends by T − h) plus an embargo of h. Every training row also needs all its inputs and its target.
  - The forecast at origin *t* uses the most recent refit with T ≤ t.
- **Raw models** (`E_raw21`, `VIX_raw`, `EWMA`) aren't fitted.

### 3.5 Inference and the winner rule

- **Bootstrap:** a circular moving-block bootstrap over forecast dates. Block length is 21 for h = 5 and 42 for h = 21 (at least 20, and at least 2h). 2,000 replications, seed 42.
- **Reported:** each model's mean loss with a 95% percentile interval, and mean loss differences with 95% intervals.

**Rule A: which RV estimator the downstream features use**
- Primary: h = 21, QLIKE.
- Among the five `E_har` models, the best estimator is the one with the lowest mean QLIKE.
- It is **adopted only if** its QLIKE beats `CC_har` with the 95% interval of (best − CC_har) entirely below 0. **Otherwise CC is used**, as the simplest estimator and the one the target is defined in.

**Rule B: does anything beat the simple benchmarks beyond noise?**
- At h = 21 with QLIKE, take the best of the 10 estimator models.
- It "beats" a benchmark (`CC_raw21`, `VIX_raw`, `VIX_cal`, `EWMA`) only if the 95% interval of (model − benchmark) lies entirely below 0. If it beats none of them, the report says so plainly.

**Secondary reporting:** h = 5 and MSE are reported in full but carry no decision weight. These are descriptive comparisons across 13 models without a multiple-testing correction; the search ledger records all 26 runs.

### 3.6 Search ledger (Task D)

- **One row per run** (model × horizon), with the scheme, parameters and run id in `params_json`, mean QLIKE in `value` and mean MSE in `notes`.
- **Every execution on real development data appends rows,** including any rerun, so the row count always equals the number of runs actually made. Code is checked on synthetic data first, and synthetic runs are never logged.
- **Feature construction** relates nothing to a target, so it gets no ledger rows.

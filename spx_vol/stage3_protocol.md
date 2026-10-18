# Stage 3 protocol: descriptive regime map of the SPX volatility-premium gap (fixed 2026-10-17)

**User decision 2026-10-17:** after Stage 2 found no predictor, take option 1, a descriptive regime map on the development years.

**Committed BEFORE any regime label was related to the gap. No changes after results.**

**This stage is descriptive only:**
- no pass/fail, no hypothesis, no registration, no hash, no slot;
- no trading P&L, no SPY, no option indexes, no broker or API calls, no new installs;
- 2008-01-02 → 2016-12-30 only (`dev_guard`; 2017+ is never read);
- every labeling run is one row in the search ledger.

A pattern seen here is **not** a finding. Any hypothesis it suggests would need its own protocol, a development test, validation on 2017–2020 and the user's approval before it could use the slot.

**Lean rule applied** (audit recommendation): only the series this map needs are used: VIX closes, SPX closes, and the Stage 1 feature `vix__pct252`.

**Also recorded here — user decision A (2026-10-17), on the VIX futures cleaning:** rows with a zero open or high < low but a positive settlement are no-trade days carrying the exchange's official settlement price. They stay in. The Stage 1 approval's "use settlement price only" is taken as satisfied, and nothing is rerun. The tried-and-reverted literal drop is documented in commit `5d3b3a8`.

---

## 1. Quantity being mapped

The Stage 2 gap, unchanged: **G_t = VIX_t² − 100²·(252/21)·Σ_{i=1..21} r²_{t+i}**, in VIX² points.
- It is defined for t from 2008-01-02 to the last t with t+21 ≤ 2016-12-30.
- **Context columns:** VIX_t, and forward 21-day realized vol in vol points, 100·√(forward RV).

## 2. Regime labelings (exactly 5; fixed now)

All labels are **real-time**: the label at t uses data up to the close of t only. The one exception is L1/L2, as noted.

| ID | Model | Series | Labels at t |
| --- | --- | --- | --- |
| L1 | statsmodels `MarkovRegression`, k = 2, constant mean, switching variance | ln VIX_t, 2008-01-02 → 2016-12-30 | Parameters from **one fit on the full development sample**; label = argmax of the **filtered** probability at t. **Discloses parameter look-ahead** within development; for reference only. |
| L2 | Same, k = 3 | Same | Same |
| L3 | Same model as L1, k = 2 | ln VIX | **Expanding refits** on the first session of 2010, 2011, …, 2016, each on data from 2008-01-02 to the day before the refit. Each year's labels come from filtering with that refit's parameters. Fully real-time; labels start 2010-01-04. |
| L4 | Same as L3, k = 3 | ln VIX | Same as L3 |
| L5 | Rule-based | Stage 1 `vix__pct252` | Low if < 1/3, mid if 1/3 to 2/3, high if > 2/3. Starts once `vix__pct252` exists (late 2008). |

**Details:**
- **Regime order:** in every fit, regimes are sorted by their fitted mean of ln VIX, so labels read 0 = low … k−1 = high, whatever the model's internal order.
- **Fitting:** `fit(search_reps=20)` with `numpy.random.seed(42)` set just before each fit. If a fit fails to converge, that's reported, and the labeling is still reported with a warning.
- **Model choice:** BIC for k = 2 against k = 3 on the full-sample fits is **reported only**. It doesn't drop either labeling.

## 3. Outputs per labeling (descriptive)

**Per regime:**
- days, and the number of separate spells and their mean length;
- mean VIX, and mean forward 21-day realized vol;
- G: mean, median, SD, the 5th/25th/75th/95th percentiles, and the share of days with G < 0 (VIX *understated* the next month's realized variance);
- a 95% interval for mean G from a circular block bootstrap (42-session blocks within the regime's dates, 2,000 resamples, seed 42).

**Per labeling:**
- the empirical day-to-day transition matrix;
- the share of days whose 21-day forward window contains a regime change. That's a reminder that G looks forward past the label.

**For comparison:** the unconditional distribution of G over the same dates.

## 4. Search ledger

- **5 runs** (L1–L5), one ledger row each.
- `value` = the mean-G spread, high-regime mean minus low-regime mean.
- `params_json` holds the labeling id, k, scheme, BIC and convergence.

If a bug is found, it gets fixed and the affected run is repeated once, and both runs are kept and disclosed.

## 5. Tests (synthetic data)

1. `dev_guard` rejects 2017+ data in the regime functions.
2. **No look-ahead:** changing every input after T leaves the L3/L4 and L5 labels at dates ≤ T unchanged.
3. The regime order puts the highest-mean regime last.
4. The ledger count equals the run count, checked against a temporary ledger.

## 6. Weaknesses stated in advance

- **Labels are built from VIX, and G contains VIX².** Higher-VIX regimes will mechanically show larger G in VIX² points. Within-regime G shares and medians are more informative than raw differences in the means.
- **2008 dominates the high regime,** so one episode may be most of its days.
- **Overlap:** neighbouring G share 20 of 21 returns, and regimes are persistent, so the effective number of independent observations per regime is small.
- **Descriptive only:** no significance test, no multiple-testing correction and no claim.

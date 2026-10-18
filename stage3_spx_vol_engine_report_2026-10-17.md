# SPX volatility-state engine: Stage 3 report, a descriptive regime map of the volatility-premium gap (2026-10-17)

**What this stage was:** the user's option 1 after Stage 2, a **descriptive** map on development years only (2008-01-02 → 2016-12-30).

**What it was not:** a test. There is no pass/fail, no hypothesis, no registration, no hash and no slot. There is no trading P&L, no SPY, no option indexes, and no broker or API calls. Nothing from 2017 onward was read.

**Nothing here is a finding.** Any idea it suggests needs its own protocol and a development test before it could ever reach validation, let alone the slot.

**The gap:** G_t = VIX_t² − 100²·(252/21)·Σ r²_{t+1..t+21}, in VIX² points (VIX = 20 gives 400). G > 0 means VIX overstated the next month's SPX realized variance.

## 1. The rules came first

| Event | Time (UTC) | Time (ET) |
| --- | --- | --- |
| Protocol `spx_vol/stage3_protocol.md` committed, **`764fa3ab0424e234963076d559d034ccdc52e105`** | 2026-10-18 03:06:03 | 2026-10-17 23:06:03 |
| The 5 labeling runs logged to the search ledger | 03:10:34 – 03:10:50 | 23:10:34 – 23:10:50 |

The protocol also records **user decision A**: VIX futures settlements on no-trade days stay in the data, and nothing is rerun. The literal drop that was tried and reverted is documented in commit `5d3b3a8`.

## 2. The five labelings

| ID | How regimes were labeled | Real-time? | Dates covered |
| --- | --- | --- | --- |
| L1 | Markov switching on ln VIX, 2 regimes, one full-sample fit, filtered probabilities | **No:** the fitted parameters use all 2008–2016 data | 2008-01-02 → 2016-11-30 (2,246 days) |
| L2 | Same, 3 regimes | No | Same |
| L3 | Markov switching, 2 regimes, refitted each January (2010–2016) on earlier data only | **Yes** | 2010-01-04 → 2016-11-30 (1,741 days) |
| L4 | Same, 3 regimes | Yes | Same |
| L5 | Rule: terciles of VIX's 252-day percentile rank | Yes | 2008-12-26 → 2016-11-30 (1,997 days) |

- **Fits:** every Markov fit converged on the first attempt (20 random starts, seed 42), including all 7 yearly refits of L3 and L4. The no-EM fallback was never used.
- **BIC** (reported only; lower is better): k = 2 gave −517.3 and k = 3 gave −471.0. So the full-sample data prefers 2 regimes.
- **L2 collapsed to L1.** The fitted middle regime was never the most likely state on any day, so L2's labels and statistics are identical to L1's.

## 3. Results

**Unconditional, for comparison:**

| Dates | Mean G | Median G | VIX understated (G < 0) |
| --- | --- | --- | --- |
| 2008–2016 | 88 [95% CI −61, 192] | 128 | 17% of days |
| 2010–2016 | 114 [67, 156] | 116 | 15% |

**By regime.** VIX and forward vol are averages in vol points. The G interval is a 95% block bootstrap (42-day blocks).

| Labeling | Regime | Days (spells) | VIX | Fwd 21d vol | Mean G [95% CI] | Median G | G < 0 | G 5th / 95th pct | Main years |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **L1** (full fit) | low | 1,276 (18) | 15.3 | 12.4 | 55 [12, 87] | 93 | 19% | −157 / 237 | 2012–2016 |
| | high | 970 (18) | 28.9 | 24.4 | 132 [−202, 345] | 283 | 14% | **−1,325** / 771 | 2008–2011 |
| **L3** (real-time, k = 2) | low | 1,562 (11) | 16.7 | 13.1 | 86 [34, 130] | 109 | 16% | −162 / 356 | 2010–2016 |
| | high | 179 (10) | 29.4 | 22.8 | 356 [272, 443] | 306 | 6% | −17 / 884 | 2010, 2011, 2015, 2016 |
| **L4** (real-time, k = 3) | low | 1,182 (18) | 15.4 | 12.4 | 60 [0.5, 107] | 97 | 16% | −120 / 273 | 2011–2016 |
| | mid | 518 (23) | 22.9 | 17.5 | 208 [126, 280] | 222 | 13% | −196 / 554 | 2010, 2011, 2014–16 |
| | high | 41 (5) | 29.8 | 20.3 | 491 [too few days] | 395 | 0% | 226 / 933 | 2010, 2014, 2015 |
| **L5** (VIX percentile) | low | 920 (99) | 16.6 | 12.7 | 111 [61, 163] | 105 | 15% | −120 / 404 | spread out |
| | mid | 565 (164) | 19.5 | 15.0 | 147 [70, 237] | 140 | 12% | −119 / 548 | spread out |
| | high | 512 (70) | 25.7 | 20.7 | 217 [144, 293] | 206 | 12% | −139 / 733 | spread out |

**Other numbers:**
- **Persistence** (chance of staying in the same regime the next day): L1 low 0.987, high 0.981. L3 low 0.994, high 0.944. L5 is much choppier: low 0.89, mid 0.71, high 0.86.
- **Forward windows crossing a regime change:** 24% of days for L1/L2, 16% for L3, 31% for L4 and 78% for L5. Where that share is high, G mostly reflects what happened *after* the regime changed.

## 4. What the map shows (descriptive, with the warnings that apply)

1. **The gap in VIX² points grows with the VIX regime in every labeling.** That's largely **mechanical**, as the protocol warned in advance: G contains VIX², so a higher VIX means bigger numbers. The share of days when VIX *understated* realized variance (G < 0) moves much less: about 12–19% in every regime of every labeling.
2. **The two kinds of labeling disagree about the high regime, and the reason is 2008.**
   - Full-sample labels (L1) put 2008–09 in the high regime. Its median G is large (283), but its left tail is extreme: the 5th percentile is **−1,325**, from the autumn 2008 crash, when realized volatility far exceeded VIX. As a result its mean-G interval spans −202 to +345.
   - The real-time labels (L3/L4) start in 2010, so they never see 2008. Their high regime, the spikes of 2010, 2011, 2015 and 2016, shows a large positive gap and almost no understatement (6% and 0%). After those spikes, realized volatility fell back faster than VIX did.
   - **The same "high-VIX" state can mean a large premium (2010–2016 spikes) or a catastrophic loss for a seller (2008).** Nothing on the development data says which one is coming.
3. **The evidence is thin.** L3's high regime is 179 days in 10 spells. L4's is 41 days in 5 spells, too short for a 42-day block interval. Neighbouring days share 20 of 21 forward returns, so these are a handful of episodes, not hundreds of observations.
4. **The low regime still carries understatement risk:** 16–19% of low-VIX days had G < 0, and the 5th percentile was around −120 to −160. A quiet VIX isn't a guarantee.

## 5. What this cannot tell us

- **It isn't a test.** No interval here was corrected for the 5 labelings, nor for the 34 runs now in the search ledger, and nothing was validated.
- **No SPX option prices or trading P&L.** The gap measures VIX against realized variance, not what any option position would earn after costs.
- **2008 is the only real crisis in the window,** and the real-time labelings never see it.
- **Nothing from 2017 onward:** not February 2018, not March 2020, not 2022.
- **The regimes are built from VIX itself,** so the regime and the gap aren't independent quantities.

## 6. Ledger, tests, code

- **Search ledger:** **34 rows** (26 Stage 1 + 3 Stage 2 + **5 Stage 3**), equal to the runs made. Each Stage 3 row's `value` is the gap between the high and low regimes' mean G: L1 77.3, L2 77.3, L3 269.5, L4 430.8, L5 106.3. The 4 L1–L4 refits also carry their BIC and convergence in `params_json`.
- **Tests:** 23 pass, all on synthetic data (4 new for Stage 3, plus Stage 1's 13 and Stage 2's 6). The new ones cover:
  - `dev_guard` rejecting 2017+ data;
  - regime ordering, with the highest-mean regime last and over 90% recovery of known synthetic states;
  - **no look-ahead:** changing all data after a date leaves the real-time L3 and L5 labels before it unchanged;
  - the ledger count equalling the run count (5), against a temporary ledger.
- **Code:** `spx_vol/stage3.py` and `spx_vol/test_stage3.py`. Results are in `data_snapshots/spx_vol_engine/results/stage3_regime_map.json`, not committed.

**One implementation detail beyond the protocol (disclosed; no effect on results):**
- `_fit` falls back to a no-EM fit from default start values if statsmodels' EM step crashes. That happened only in tests with too few random starts. All real fits used the protocol's 20-start search.
- The tests were also changed to use the protocol's 20 starts, after 1–2 starts crashed on synthetic data.

## 7. What it suggests (not started; each would need its own protocol)

The most interesting pattern is point 2: **after VIX spikes that weren't 2008, VIX overstated the next month's SPX volatility by a wide margin. In 2008 it badly understated it.**
- A candidate hypothesis for the slot would need a pre-declared, real-time rule that tells those two cases apart.
- It would also need to be tested on 2008–2016, then validated once on 2017–2020, where February 2018 and March 2020 are the hard cases.

**Before that,** it would be sensible to restate G as a ratio (ln(VIX²/RV), already used as G′ in Stage 2). That removes the mechanical VIX² scaling seen in point 1.

My view: with only 5–10 non-2008 spike spells in development (L4 and L3 respectively), any such rule will have very little power. **Closing the SPX engine as a documented negative result remains a reasonable choice.**

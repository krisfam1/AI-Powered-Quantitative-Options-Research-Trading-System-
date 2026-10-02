# Cross-sectional straddle hypothesis — Phase 1 report (2026-10-01)

**Pipeline validation on the DEV window only (23 cycles, 2023-10-23 → 2025-09-19). NOT evidence, NOT a test.** The BLIND window (2025-10 onward) was not collected or examined. Raw output: `straddle_dev_analysis_results.json`.

## 1. Request cost (measured)
- One ticker-cycle (AAPL, 2024-03-18 → 2024-04-19) took **2 requests**: the entry snapshot (328 contracts, 7 expirations) and the exit snapshot (66 contracts). The strike filter was honored 100% and halved the records.
- The full DEV collection took **2,758 requests for 2,714 snapshots** (1.02 per snapshot, 614,577 contracts, 0 errors), about 28% of one day's ~10k quota. My earlier 6–13k estimate was too high.
- 75 snapshots are empty, all genuine EODHD gaps:
  - All of 2025-01-16 is missing. It only affects the day-before exit for one cycle.
  - 16 scattered ticker-days returned only other-day records, which the same-day filter rejected.

## 2. Pipeline checks
- **Unit tests:** 14 test cases (51 hand-computed assertions) pass.
- **Coverage:** 1,325 of 1,357 ticker-cycles evaluated. 32 were excluded: 7 splits in the holding window, 11 with under a year of price history (ARM), 14 with no quoted ATM pair.
- **Data-quality findings in EODHD open interest, both handled in the open:**
  - It's **null** on many half-dollar strikes. Treated as unknown, a rule fixed before any result.
  - It's sometimes a false **0** on obviously liquid ATM legs (TSLA, AAPL, NVDA monthlies with 245k–1.5M contracts of expiration OI and ~1% spreads). I found this after the first run had shown returns, so both versions are reported:
    - **As specified:** 0 counts as 0, giving 780 eligible ticker-cycles.
    - **Refinement:** 0 counts as unknown, giving 987.
- **The liquidity rule works:** it excludes the genuinely wide names. F and LCID were never eligible, NIO and MSTR only 9% of the time. ATM ~30-day straddles traded much tighter in 2023–25 than the single-leg, ~45-day quotes I cited earlier (SMCI median 2.4%), so SMCI is usually eligible.

## 3. Goyal–Saretto reproduction on DEV (per cycle ≈ per month)
Figures are for the as-specified rule / the zero-OI-unknown refinement.

| Measure | at mid | after quoted spreads |
|---|---|---|
| GS spread, straddle basis (top − bottom HV−IV group) | +6.5% / +10.0% (t 0.6 / 0.9) | +2.7% / +5.4% |
| Implementable book (long straddles + iron butterflies, equal capital) | +1.7% / +4.3% | −0.8% / +1.2% |
| **Delta-hedged GS spread** (isolates the volatility component) | — | **−1.5% / −0.9%** |
| Within-cycle shuffled-rank placebo, p (one-sided) | 0.25 / 0.11 | |
| Trade-level corr(signal, straddle return): raw / cycle+ticker demeaned | −0.003 / +0.010 (refinement: −0.002 / +0.034) | |

- **Direction:** the unhedged spread has the published sign, but it isn't distinguishable from noise.
- **It vanishes when hedged.** The apparent effect came from stock moves, not volatility mispricing.
- **Trade level:** the signal shows essentially no relation to straddle returns.
- **This window is unusual:** realized vol beat implied broadly (Aug-2024 and Apr-2025 shocks). Long straddles on top-group names returned +13% to +18% per cycle after costs, and short iron butterflies lost about 15% of max-loss capital per cycle (t −1.9 to −2.4). The overall vol regime, not the ranking, drove both legs.
- **Hedging cut a single leg's noise by ~60%** (SD 0.48 → 0.19) but **not the long-short spread's** (0.27 → 0.25). The spread's noise is name-specific, so it shrinks only with more names per group.

## 4. Power
Minimum detectable mean per cycle at 80% power, one-sided α = 0.05:

| Cycles available | Implementable book | Hedged spread | GS straddle basis |
|---|---|---|---|
| 23 (DEV) | 14% | 13% | 28% |
| 36 (all EODHD history) | 11% | 10% | 22% |
| 192 (2007–2023 history, same ~50-name universe) | 4.9% | 4.4% | 9.6% |

- A realistic net effect of 1–3% per cycle needs ~400–1,000+ cycles at today's breadth, which no history has.
- **Breadth is the binding constraint**, because the spread's noise is name-specific. With ~10× more names per group (a 500-name liquid universe), noise falls by roughly √10, so the 192-cycle detectable effect drops to ~1.5%.

## 5. Recommendation: NO-GO on drafting the pre-registration yet
- A confirmatory test on the 59-ticker / EODHD setup would be badly underpowered: it could only detect effects of 10–14% per cycle, against plausible net effects of 0–3%. A REJECTED from it would be uninformative.
- **Path to GO:**
  1. **Data:** the ORATS near-EOD archive, 2007 → present, 5,000+ symbols with NBBO bid/ask, is a **one-time $599 purchase**, not a subscription.
  2. **Re-scope:** extend the pipeline to a broad liquid universe (a few hundred names passing the same spread/OI rule), with 2007–2023 as untouched confirmation data.
  3. **Rerun the power analysis on that universe.** Draft the pre-registration only if its detectable effect is ≤ ~2% per cycle.
  4. **Make the delta-hedged spread the pre-registered primary metric.** It's what the literature measures, and the DEV run showed unhedged results are dominated by directional moves.
- **Unchanged until then:** the BLIND window stays untouched, and IV Stage 2 and SPY GEX v3 run as before.

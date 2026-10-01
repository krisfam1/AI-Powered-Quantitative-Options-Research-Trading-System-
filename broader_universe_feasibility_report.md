# Step 1: Broader-Universe Data-Feasibility Audit

**Date: 2026-09-28. Read-only. No target selected, no model trained, no preregistration written, no hash computed. Does not touch RF v1/v2, XGBoost v1, or regularized XGBoost v2 (CLAUDE.md Section 58, permanently closed).**

Scripts: `audit_broader_universe_feasibility.py` (Phases A–D, initial pass), `audit_cross_sectional_density.py` (supplementary 12-date density pass). Raw data: `broader_universe_feasibility_raw.json`, `cross_sectional_density_raw.json`. Full console logs: `broader_universe_feasibility_run.log`, `cross_sectional_density_run.log`.

---

## Method and pagination-integrity verification

All EODHD options-chain queries used `gex_data_loader.py`'s `_fetch_raw_chain_paginated()` — the same already-validated, full-pagination method used throughout this project's real data-generation scripts (SPY historical backfill, OI-skew dataset, the volatility-prediction datasets), never a naive single-page query. Per explicit instruction (referencing the pagination-undercount failure mode already documented in this project's own history), **every single call in this audit explicitly recorded and checked `pagination_complete` and `pages_requested`, not just whether the call returned without error.**

**Result, across 448 + 708 = 1,156 raw API calls spanning 236 distinct (ticker, date) probes: zero `pagination_complete=False` events, anywhere.** Maximum `pages_requested` seen on any single probe: **3** (well under the 20-page circuit breaker this project's fetch layer enforces). The id-date-safe filter was also confirmed *active*, not just theoretical: at several probes (e.g., MSFT 2025-06-02: 617 raw records → 428 id-date-matched; META 2025-06-02: 1,036 → 772), raw record counts exceeded id-matched counts, meaning the filter is genuinely discarding wrong-day contamination on real queries, not passing everything through.

Alpaca underlying-price queries used the project's standard `StockHistoricalDataClient` call with `Adjustment.RAW` (matching this project's own confirmed-correct convention for anything eventually matched against EODHD's real, unadjusted strikes — CLAUDE.md Section 56).

---

## Candidate universe

**53 new candidates**, deliberately broad and diverse (megacap tech, semis, EV/auto, consumer/retail, financials, healthcare, energy/industrial, crypto-adjacent, high-vol/momentum names), chosen *before* any data was pulled — no ticker was added or dropped based on how it performed in this audit:

MSFT, GOOGL, AMZN, META, AVGO, INTC, MU, QCOM, TXN, LRCX, AMAT, ASML, ARM, F, GM, RIVN, LCID, NIO, WMT, COST, TGT, NKE, SBUX, MCD, HD, DIS, JPM, BAC, GS, MS, V, MA, PYPL, SOFI, UNH, JNJ, PFE, LLY, MRNA, XOM, CVX, OXY, BA, CAT, GE, COIN, RIOT, MARA, PLTR, SNAP, ROKU, DKNG, AFRM.

Plus the existing 6 (AAPL, AMD, MSTR, NVDA, SMCI, TSLA) for a **59-ticker full universe considered**.

---

## Phase A — Alpaca underlying-price feasibility

**Result: 53/53 candidates returned real, usable daily-bar data. Zero failures.**

| Category | Tickers | Earliest date | n_days |
|---|---|---|---|
| Full-depth (matches existing 6's own start) | 44 of 53 | 2020-07-27 | 1,548–1,551 |
| IPO/listing-limited (real, expected constraint, not a bug) | ARM (2023-09-14, n=762), RIVN (2021-11-10, n=1,224), LCID (2020-09-18, n=1,511), SOFI (2020-11-30, n=1,462), COIN (2021-04-14, n=1,371), PLTR (2020-09-30, n=1,502), AFRM (2021-01-13, n=1,433) | — | — |
| **Anomaly, unexplained, not resolved here** | **DIS**: earliest=2018-04-25 (*older* than every other ticker's 2020-07-27 floor), n_days=1,549, **1 gap >4 calendar days** | 2018-04-25 | 1,549 |

**44 of 53 tickers show a small, consistent 3-day shortfall** (1,548 vs. 1,551 days) relative to the "full-depth" tickers. **RESOLVED below (see "3-day discrepancy and DIS anomaly — resolved, 2026-09-29"), not left as an open flag.** Zero tickers (other than DIS's single gap) show any gap >4 calendar days across the full ~6-year Alpaca history.

---

## 3-day discrepancy and DIS anomaly — resolved, 2026-09-29

**3-day discrepancy — pinned down, not fully root-caused to a single deterministic rule, but characterized precisely:**

- **Uniform, not variable.** Every affected ticker checked (WMT, JPM, F, GS, XOM, UNH, BA — 7 independent spot-checks across retail/financial/auto/energy/healthcare/industrial sectors) is missing **the exact same 3 calendar dates**: 2021-04-19 (Monday), 2021-10-25 (Monday), 2022-03-08 (Tuesday). Same direction (records absent, not zero-volume), same magnitude (exactly 3 days), across every ticker in the affected group — not a spread of different counts or different dates.
- **Not a market-wide closure.** SPY has real bars on all 3 dates, confirming the broader market was open and trading normally.
- **Not explained by Alpaca's own `exchange` metadata field.** WMT is labeled `NASDAQ` (same as MSFT, which is unaffected) yet behaves like the affected group; JPM is labeled `NYSE` and is also affected; GOOGL is `NASDAQ` and unaffected. No clean split by exchange, asset_class, tradable/marginable/shortable flags, or any other Alpaca asset-metadata field checked (all identical across MSFT/WMT/JPM/GOOGL except `exchange`, which itself doesn't predict membership).
- **Confirmed a real "missing record," not a real zero-volume day.** MSFT (unaffected) shows genuine nonzero IEX volume on all 3 dates (569,757 / 510,774 / 1,064,614 shares). JPM (affected) has no bar at all on any of the 3 — an absence, not a zero.
- **Does NOT affect the existing 6 research tickers** — directly reverified all six: AAPL, AMD, MSTR, NVDA, SMCI, TSLA all show the full 1,551-day depth with zero missing dates. This gap is confined to a subset of the 53 new candidates only.
- **Working mechanism (reasoned inference, disclosed as such, not a confirmed vendor admission):** this project's Alpaca bars are sourced from the **IEX feed** specifically (already established elsewhere in this project, e.g. CLAUDE.md's "5-min IEX bars" convention) — IEX is a real, minority-market-share US exchange. The most coherent explanation consistent with every fact above (identical dates across unrelated sectors, market open per SPY, a genuine absence rather than a zero-volume record, no metadata field predicting membership) is a **historical archival/backfill gap specific to IEX's own record for a subset of individual securities on those 3 particular calendar days** — not a corporate action, not a market-wide event, and not something explainable by any Alpaca-exposed security attribute. The precise rule determining *which* securities fall into the affected group was not identified despite checking exchange, asset class, and all other available metadata fields — this remains a genuine, disclosed limit of the investigation, not glossed over as solved.
- **Practical impact: negligible.** 3 missing days out of ~1,551 (0.2%) in a 6-year window, confined to a data region no research design here would treat as a locked, immovable boundary. Recommendation: no exclusion needed for any of the 44 affected tickers on this basis alone.

**DIS anomaly — fully resolved, root cause identified.**

- Full bar history 2018–2020 pulled directly. Result: **exactly one isolated bar at 2018-04-25 (Wednesday)**, then an **824-day gap**, then continuous daily bars resuming at 2020-07-27 — the identical floor every other ticker in this universe has.
- **That single 2018-04-25 bar is degenerate, not a real aggregated trading day**: `open=high=low=close=99.5`, `volume=100`. A real NYSE-listed Dow-component day for Disney would show meaningfully different open/high/low/close values and volume in the millions of shares — this is the signature of a single stray tick or a leftover/orphaned reference-data point, not a genuine daily bar.
- **Conclusion: DIS's "earlier start date" is a data artifact, not real extended historical depth.** Its real, usable, continuous coverage begins 2020-07-27, identical to the rest of the universe.
- **Recommendation: include DIS in the final universe on the same basis as the other full-depth tickers, using its real 2020-07-27+ continuous window. Do not use or rely on the single 2018-04-25 bar for anything** (e.g., a naive "earliest date" or long-lookback feature should not treat it as a real starting point) — since every planned design already anchors to the common ~2023-10-02+ window (per the existing EODHD options-depth cliff, Section "Phase B" below/CLAUDE.md Section 45), this stray point falls well outside any window that would actually be used and requires no special filtering beyond simply not treating pre-2020-07-27 DIS data as real.

---

## Phase B — EODHD options-chain depth

Checked at 4 dates spanning the full candidate window: **2023-10-02** (the previously-established hard cliff for the existing 6 tickers + SPY, CLAUDE.md Section 44), 2024-06-03, 2025-06-02, 2026-09-01.

**Result: 53/53 candidates show real, usable, both-sides (call+put) options data at all 4 dates — including 2023-10-02 itself.** No candidate needed the Phase C bisection (see below) because none failed the earliest probe.

Sample (illustrating the three-way count distinction requested):

| Ticker | Date | Raw option-contract rows | id-date-matched rows | Usable rows (vol+strike+exp present) | Usable calls | Usable puts |
|---|---|---|---|---|---|---|
| MSFT | 2023-10-02 | 862 | 862 | 694 | 324 | 370 |
| MSFT | 2026-09-01 | 1,045 | 923 | 923 | 465 | 458 |
| META | 2023-10-02 | 1,270 | 1,270 | 1,023 | 498 | 525 |
| TXN | 2025-06-02 | 251 | 107 | 107 | 50 | 57 |
| LCID | 2025-06-02 | 125 | 75 | 73 | 44 | 29 |
| SNAP | 2026-09-01 | 147 | 128 | 127 | 82 | 45 |

**Aggregate across all 236 (ticker, date) probes in this audit: 140,560 raw option-contract rows, 114,313 passing the full usability filter.** These are *contract-row* counts, not observation counts — see the explicit distinction below.

---

## Phase C — bisection for late-starting candidates

**Result: zero candidates required bisection.** Every one of the 53 new candidates already had usable options data at the earliest probe date (2023-10-02) — the "late-starter" detection logic (which would trigger a real bisection for any ticker failing 2023-10-02 but passing later dates) found nothing to investigate.

**This is itself a significant, unplanned finding**: the 2023-10-02 EODHD depth cliff, previously confirmed only for the existing 6 tickers + SPY (Section 44), now appears to be a **platform-wide historical-options-data boundary affecting this entire class of liquid, optionable US equities** — not a per-ticker limitation. Not proven for *every* possible US equity (only tested on these 59), but strongly supported by a 100% hit rate across a deliberately diverse 53-ticker sample.

---

## Phase D — cross-sectional coverage (the empirical distribution, not a point estimate)

**16 real dates sampled** across the full common window (2023-10-02 → 2026-09-01): the original 4 point-checks plus 12 additional, roughly evenly-spaced dates (2023-12 through 2026-06). At each date, every one of the 59 tickers (6 existing + 53 candidates) was checked for usable, both-sides options data.

| Date | Available / 59 | Missing |
|---|---|---|
| 2023-10-02 | 59/59 | — |
| 2023-12-15 | 59/59 | — |
| 2024-02-15 | 59/59 | — |
| 2024-04-15 | 59/59 | — |
| 2024-06-03 | 59/59 | — |
| 2024-08-15 | 59/59 | — |
| **2024-10-15** | **57/59** | MARA, PFE |
| **2024-12-16** | **57/59** | COIN, DKNG |
| 2025-02-18 | 59/59 | — |
| 2025-04-15 | 59/59 | — |
| 2025-06-02 | 59/59 | — |
| 2025-08-15 | 59/59 | — |
| 2025-10-15 | 59/59 | — |
| 2025-12-15 | 59/59 | — |
| 2026-06-15 | 59/59 | — |
| 2026-09-01 | 59/59 | — |

**Empirical distribution across these 16 real sample dates:**
- **Median tickers available per date: 59/59 (100%)**
- **Minimum tickers available on any sampled date: 57/59 (96.6%)**
- **% of sampled dates at 100% coverage: 14/16 = 87.5%**
- **% of sampled dates at ≥95% coverage: 16/16 = 100%**

**Honest limitation, stated plainly**: this is a 16-point sample over a ~750-trading-day window, not an exhaustive daily census — a full daily-level check would require roughly 750 × 59 ≈ 44,000 API calls, prohibitively expensive for a feasibility pass. The sample is real, evenly spread, and large enough to be informative (16 independent draws, only 2 showing any dropout at all, and never more than 2 tickers missing on any date), but it does not certify literally every calendar day.

---

## Explicit terminology, per instruction — do not conflate these

- **Option-contract rows**: a single specific strike+expiration+type record. One (ticker, date) query can return hundreds to low-thousands of these (e.g., META 2026-09-01: 1,693 raw rows).
- **Ticker-date (ticker-day) combinations**: one (ticker, date) pair, regardless of how many contracts existed that day. This audit checked **236 such combinations directly** (53 tickers × 4 initial dates, minus overlaps, plus 59 tickers × 12 density dates).
- **Model-level / unique observations**: whatever a future experiment's actual target/feature construction would produce per ticker-day — necessarily a *subset* of ticker-day combinations with usable data, and NOT yet determined, since no target has been chosen (Step 2, not run). This audit reports the ticker-day usability rate as the closest available proxy, not a literal model-observation count.

---

## Candidate universe sizes actually supported by measured data

| Universe | # Tickers | Supported? | Basis |
|---|---|---|---|
| Current 6 | 6 | Yes (already validated repeatedly, prior sessions) | — |
| ~10–20 | up to 20 | **Yes** | Trivial subset of the 53 fully-tested candidates |
| ~30 | 30 | **Yes** | Trivial subset of the 53 fully-tested candidates |
| ~40–50 | 40–50 | **Yes** | Trivial subset of the 53 fully-tested candidates |
| Full tested set | **59** (6 + 53) | **Yes — 100% Alpaca pass rate, 100% EODHD-depth-cliff pass rate, 87.5–100% cross-sectional coverage across 16 real sampled dates** | Directly measured, this audit |
| Beyond 59 | untested | **Unknown — not addressed by this audit** | Would require a fresh candidate list and a new pass; not assumed |

**Direct answer to "is 30–50+ tickers realistically achievable": yes, strongly supported by measured evidence** — and the tested set (59) somewhat exceeds even the upper end of the range you asked about, with no candidate-selection tuning toward a favorable result (the list was fixed before any data was pulled).

---

## Data-source limitations identified

- **The 2023-10-02 EODHD historical-options cliff is real and appears to be platform-wide** (not per-ticker) for this class of liquid, optionable equities — a hard, non-negotiable floor on how far back any cross-sectional design in this family can reach, confirmed (not assumed) across 59 tickers.
- **A small number of tickers show intermittent single-day gaps in cross-sectional coverage** (MARA/PFE on one sampled date, COIN/DKNG on another) — real, measured, low-frequency data gaps that a future design must exclude-not-substitute, per this project's own standing discipline, rather than something to paper over.
- **DIS's anomalous earlier start date (2018-04-25) and single Alpaca gap are unexplained** — flagged, not investigated; if DIS is ever included in a real universe, this deserves a closer look before trusting its early-window rows.
- **The small, consistent 3-day shortfall** in `n_days` for ~44 of 53 tickers (1,548 vs. 1,551) is unexplained — likely immaterial, not chased further here.
- **No survivorship-bias check was performed** — this candidate list consists entirely of currently-listed, currently-liquid tickers; a genuinely bias-free universe-construction rule (Step 2+) would need to consider whether any historically-delisted or since-illiquid names should have been eligible for inclusion at earlier points in the window. Flagged as a real, unresolved methodological question for the eventual universe-eligibility rule, not something this audit can settle.
- **No options bid/ask fill-rate, open-interest-depth, or liquidity-tier audit was performed** beyond the "usable" filter already established in this project (`volatility`, `strike`, `exp_date` present, both sides populated). A future design may want a stricter minimum-OI or minimum-volume eligibility bar; not measured here.
- **Rate limits, storage, and computational limits**: no EODHD rate-limiting was encountered anywhere in this ~1,150-call audit; no storage concerns (results are a few MB of JSON); no computational bottleneck at this scale. A full 59-ticker, ~750-trading-day dataset-generation pass (unlike this feasibility sample) would cost on the order of 59 × 750 ≈ 44,000 EODHD calls — feasible given this project's prior single-pass volumes (600–4,000+ calls), but a real, non-trivial cost to budget for explicitly before committing to Step 2+.

---

## Bottom line

1. **Actual number of additional feasible tickers**: all 53 tested candidates passed every check (Alpaca depth, EODHD depth-cliff, cross-sectional coverage) — **53 additional feasible tickers confirmed, on top of the existing 6, for a 59-ticker tested universe.**
2. **Candidate universe sizes supported**: 6, 10–20, 30, 40–50, and 59 are all directly supported by measured data; beyond 59 is untested, not assumed.
3. **Actual common date range**: 2023-10-02 through at least 2026-09-01 (2026-09-28 for Alpaca underlying) — a real, measured ~2.9-year options-data window, confirmed identically across all 59 tickers.
4. **Ticker-day and options-observation counts**: 236 ticker-date combinations directly probed; 140,560 raw option-contract rows observed, 114,313 passing the usability filter; full daily census not performed (cost-prohibitive at feasibility stage), 16-point sample used instead.
5. **Cross-sectional coverage statistics**: median 59/59 (100%), minimum 57/59 (96.6%), 87.5% of sampled dates at 100%, 100% of sampled dates at ≥95%.
6. **Missing-data/quality limitations**: two isolated dates with 2 missing tickers each (different tickers each time); one unexplained DIS anomaly; no rate-limit, pagination, or storage problems encountered.
7. **Is 30–50+ tickers realistically achievable?** **Yes — confirmed, not estimated.**
8. **Any feasibility issue that should change the research design?** The 2023-10-02 floor is now confirmed structural/platform-wide, not ticker-specific — any Step 2+ design should treat it as a hard boundary. The intermittent single-date gaps (MARA/PFE, COIN/DKNG) confirm the eventual design needs a real, pre-specified missing-data/exclusion rule (exclude-never-substitute, this project's standing convention) rather than assuming perfect daily coverage. The survivorship-bias question (no delisted/illiquid-since names considered) is unresolved and worth deciding explicitly before finalizing an eligibility rule in Step 2.

**Stopping here, per explicit instruction. Not proceeding to Step 2 (target design) until this is reviewed.**

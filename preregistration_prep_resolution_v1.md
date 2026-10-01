# Pre-Preregistration Resolution: IPO-Ticker Depth, Real Fold Boundaries, Stage 2 Automation

**Date: 2026-09-29. Resolves the three conditions attached to the Steps 3-4 approval, before the full preregistration is written. All three checked against live data, not assumed.**

---

## 1. Do the 7 IPO-limited tickers have a later effective start than the 2023-10-02 EODHD depth cliff?

**No — confirmed directly, no special rule needed.**

**Check 1 — real EODHD options data AT the known 2023-10-02 cliff, for all 7 tickers**, via `_fetch_raw_chain_paginated` (the same already-validated method used throughout this project):

| Ticker | Raw records | id-date-matched, volatility-populated |
|---|---|---|
| ARM | 490 | 457 |
| RIVN | 424 | 412 |
| LCID | 266 | 203 |
| SOFI | 358 | 279 |
| COIN | 732 | 669 |
| PLTR | 464 | 399 |
| AFRM | 444 | 393 |

All 7 show substantial, real, populated data on the cliff date itself — not a stray single record. **Every one of the 7 tickers' real-world listing date is already before 2023-10-02** (ARM 2023-09-14 is the latest, still ~18 days before the cliff), so there was never a genuine "hasn't been listed yet" constraint operating within this project's usable window in the first place — the earlier design document's framing ("these tickers would lose roughly the first 6 months of their listed life to burn-in") was an overstatement, corrected here: within the 2023-10-02+ window this project actually uses, these 7 tickers were never IPO-constrained at all.

**Check 2 — density within the critical first 126-trading-day window** (2023-10-02 through 2024-06-30, sampled at every 5th real trading day, 28 samples), to rule out sparse/gappy coverage even where the cliff-date check alone looked fine:

All 7 IPO-limited tickers, plus two established controls (AAPL, MSTR), showed **28/28 (100%) sampled dates populated**, zero gaps.

**Conclusion**: the 7 IPO-limited tickers interact with the 126-day trailing-history burn-in requirement **identically** to the original 6 tickers — no special eligibility rule (later start, exclusion, or otherwise) is needed. `START_DATE = "2023-10-02"` is correct as a single, shared constant for the full 59-ticker universe, not just the original 6.

**One real, already-known exception, unrelated to IPO timing — disclosed, not newly discovered here**: the Step 1 cross-sectional density check found COIN missing data on 2024-12-16 (alongside DKNG that same date, and MARA/PFE on a different date, 2024-10-15) — all well after the window checked here, and all already covered by this project's standing discipline of excluding (never substituting) any ticker-date with insufficient EODHD coverage. This is an ordinary, sporadic single-date gap, not evidence of a systematic depth-cliff problem for any of these tickers.

---

## 2. Real fold boundary dates, computed against live data

Computed using `gex_data_loader.py:get_real_trading_days()` (SPY reference calendar, the same method used throughout this project for trading-day arithmetic) — **not placeholder ranges**, per the explicit instruction citing this project's repeat history of stale date-window bugs (SPY GEX's N-off-by-one, IV term structure's hardcoded `test_period`).

- **Real trading-day count, 2023-10-02 through today (2026-09-29)**: 749 days.
- **Stage1_start**: the 126th real trading day on/after 2023-10-02 (clears the burn-in requirement) = **2024-04-02**.
- **Stage1_end**: set to leave the *largest* candidate horizon (50-day) genuinely computable as of today, plus a 5-trading-day safety buffer against exactly the kind of off-by-one already found once in this project (SPY GEX's "today's still-forming session" bug, Section 43) = **2026-07-10** (55 real trading days of buffer beyond it exist as of today).
- **Total real trading days within the Stage 1 window**: 569.

**K=4 expanding-window folds** (corrected design: the 569-day Stage-1 window is split into 5 equal blocks of ~113 real trading days each — the first block serves purely as Fold 1's initial training period, and blocks 2-5 are the four test blocks, so every fold has genuine prior training history, not a degenerate zero-length one):

| Fold | Train | Test |
|---|---|---|
| 1 | 2024-04-02 → 2024-09-11 (113d) | 2024-09-12 → 2025-02-25 (113d) |
| 2 | 2024-04-02 → 2025-02-25 (226d) | 2025-02-26 → 2025-08-08 (113d) |
| 3 | 2024-04-02 → 2025-08-08 (339d) | 2025-08-11 → 2026-01-21 (113d) |
| 4 | 2024-04-02 → 2026-01-21 (452d) | 2026-01-22 → 2026-07-10 (116d, includes a small end-of-window rounding remainder folded into the final block) |

- **Stage2_start**: the real next trading day after Stage1_end = **2026-07-13**.
- **Real trading days already available for Stage 2, as of today**: 55.

These are the actual, live-data-verified boundaries — not the design document's earlier placeholders (which had been reasoned but not yet computed). They will be re-verified once more against `broader_universe_volatility_dataset.db`'s real saved dates immediately before Stage 1 is executed, per this project's standing discipline of never trusting a boundary as locked until the moment of actual execution.

---

## 3. Stage 2 automation — built now, alongside Stage 1, not after

**New script**: `generate_broader_universe_volatility_dataset.py` — a direct extension of the already-validated `generate_xgboost_volatility_dataset.py` (CLAUDE.md Sections 45/56), with every feature/fetch/Greeks function reused verbatim, parameterized to the full 59-ticker universe and a new database (`broader_universe_volatility_dataset.db`). Same idempotency discipline (exclusive lockfile, `UNIQUE(ticker, obs_date)` + `INSERT OR IGNORE`).

**Deliberate design choice**: this one script serves as *both* the Stage-1 historical backfill and the ongoing Stage-2 accumulation mechanism — there is no separate "Stage 2 script" to build later, because as each new real trading day closes, one more ticker-day per ticker crosses the 50-day-forward-computability line automatically, extending the eligible dataset without any code change.

**Registered and running:**
- **Scheduled task `BroaderUniverse_Volatility_Nightly_Update`**, daily 20:30 ET, settings mirrored exactly from `RF_v2_Stage2_Nightly_Update`'s template (battery/idle/multiple-instance settings all matched) — confirmed registered, `State: Ready`.
- **A real backfill run was started in the background today (2026-09-29)**, not deferred — confirmed working on first inspection (AAPL: 750 daily bars, 680 candidate trading days, matching the expected count). This is a large job: extending the same per-ticker-day EODHD fetch pattern that took roughly 4,068 ticker-days for the original 6 tickers to **roughly 40,000 ticker-days for the full 59-ticker universe** — realistically a multi-hour, possibly multi-session job, disclosed honestly rather than estimated as quick. It is safe to interrupt and resume at any time (idempotent, resumes from wherever it left off), and the nightly scheduled task will pick up where any interrupted run left off regardless.

**Net effect**: unlike RF v2, this dataset's Stage 2 will never sit at zero rows waiting for someone to remember to build automation — the mechanism exists and is already running before the preregistration itself is even finalized.

---

**Status: all three conditions resolved. Proceeding to write the full preregistration next**, per instruction.

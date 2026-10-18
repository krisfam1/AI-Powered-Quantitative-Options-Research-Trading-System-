# SPX volatility-state engine: compliance audit (2026-10-17)

## Verdict: COMPLIED WITH MINOR DEVIATIONS

The work kept to the rules that matter most, all verified from git, code, the search ledger and stored files:
- the data split, with nothing from 2017 onward analysed;
- protocols committed before scoring;
- an append-only search ledger whose count matches the runs (29);
- no hypothesis slot, registration or hash;
- SPX-only targets;
- no broker calls beyond the approved 4 EODHD requests;
- raw data unchanged (299 of 299 hashes match);
- no data committed, and CLAUDE.md under 150,000 characters at every commit.

Every headline number in the Stage 1 and Stage 2 reports matches the stored ledger and result files.

The deviations are small and mostly disclosed.
- **The one that contradicts an approval's wording:** VIX futures rows with a zero open or high < low were *flagged, not dropped*. That includes listing-day placeholders whose settlement price is positive, which were also kept. It was disclosed, it can only have touched the futures-slope feature, and that feature failed by a wide margin.
- **One stored-vs-reported mismatch:** the Stage 0 report says the EODHD check had "no error response", but one of its 4 requests returned HTTP 404.

**Efficiency:** the plan was much larger than the decisions needed. 124 of the 127 features, most of the 13 forecast models and several downloads (VIX1Y, VIX1D, SPY daily, the 239 MB options sample, 2004–2007 futures) played no part in any decision. Stage 2 recomputed its 3 features independently of the feature file.

**Failed items:** none of the 12 checklist rules failed. The mismatch above is in Part E.

**Could not be verified** (details in the last section):
- the ledger's history through git (the database isn't tracked);
- that the system Python and the bots' environment are byte-for-byte unchanged;
- the cut-off end of the Stage 1 approval;
- how many placeholder rows were kept in 2008–2016 (finding out needs a new computation, which this audit didn't do).

**How this audit was done:** read-only, by reading code, git history, the ledger (opened read-only) and the stored result files. No scoring was rerun and no statistic was computed on any data. The only things executed:
- SHA-256 hashes of the raw files;
- character counts of CLAUDE.md at each commit;
- the 19 unit tests, which use synthetic data only (the real ledger stayed at 29 rows afterwards).

Commits reviewed: baseline `8a3205b` (2026-10-06) → `dfa3c8c`, `e2ff0b6`, `700d2be`, `ebdd22d`, `e138fd9`.

---

## Part A: plan vs delivery

The rows follow the design file's own stage table (`spx_vol_state_engine_design_v1.md` §6, "Stage" / "Spec step").

| Design stage (spec step) | What the design said | Status | Reason | Where | Approved? |
| --- | --- | --- | --- | --- | --- |
| 0 (—) | Data audit, EODHD SPX-chain check, power estimate | **DONE WITH CHANGES** | Done (`stage0_…audit…md`). EODHD check: 4 requests, no SPX/SPXW/VIX options. **No power estimate made**, since nothing was testable yet. | Stage 0, `dfa3c8c` | Stage 0 approval (2026-10-17), items 3–4. The power estimate wasn't asked for in that approval's deliverable list. |
| 1 (1) | Snapshots + manifest; `panel.py`; point-in-time tests; installs | **DONE WITH CHANGES** | Snapshots and manifest in Stage 0. The "panel" is three clean CSVs from `clean.py`, not a `panel.py`. Point-in-time tests in `test_stage1.py`. **Only 4 of 6 libraries.** | Stage 0 `dfa3c8c`; Stage 1 `700d2be` | Stage 1 approval, decision 2 ("Do NOT install hmmlearn, ruptures…") |
| 2 (2–3) | Descriptive statistics (development only); RV estimator comparison by QLIKE against **intraday** RV; stationarity and structural breaks | **REPLACED / partly done** | The estimator comparison was done in Stage 1 against **forecast-based** scoring. Descriptive statistics, stationarity and breaks were **not run**, replaced by the narrow gap test. | Stage 1 `e2ff0b6` (protocol), `700d2be`; Stage 2 `ebdd22d`, `e138fd9` | Stage 1 approval, decision 3 (forecast-based scoring); Stage 2 approval ("REDEFINED… the original… is NOT to be run") |
| 3 (4) | Regimes: HMM, Markov switching, GMM, change-point, clustering | **NOT YET STARTED** | HMM and change-point libraries not installed; only statsmodels Markov switching is allowed | — | Stage 1 approval, decision 2 |
| 4 (5) | Single-variable anomalies, unconditional vs regime-conditional | **NOT YET STARTED** | — | — | — |
| 5 (6) | Multivariate anomalies, ensemble, explanations | **NOT YET STARTED** | — | — | — |
| 6 (7) | Analog engine | **NOT YET STARTED** | — | — | — |
| 7 (8) | Predictive tests against baselines, then the validation block once | **DONE WITH CHANGES (narrow)** | Stage 2 tested 3 pre-chosen features against one target (G = VIX² − forward 21-day realized variance) under fixed pass rules. All failed development; **validation not run.** | Stage 2 `ebdd22d`, `e138fd9` | Stage 2 approval |
| 8 (—) | Pre-registration of ≤ 3 hypotheses (uses the slot) | **NOT YET STARTED** | Nothing passed | — | — |
| 9 (9) | Locked test, run once | **NOT YET STARTED** | — | — | — |
| 10 (10–11) | Ensemble and distributional models, stress tests | **NOT YET STARTED** | — | — | — |
| 11–12 (11–12) | Daily report / dashboard | **NOT YET STARTED** | — | — | — |
| Design §3.3 (feature engineering, used by stages 4–7) | Core transforms | **DONE AS PLANNED** | 127 columns, exactly as in the Stage 1 protocol | Stage 1 `700d2be` | Stage 0 approval, item 5 (smaller feature set); Stage 1 approval, Task B |

**The specific changes asked about:**

| Change | What happened | Approved? |
| --- | --- | --- |
| Original Stage 2 (exploratory statistics, stationarity, structural breaks) replaced by the narrow gap test | Not run. The narrow test ran under `stage2_protocol.md`. | Yes: the Stage 2 approval says "REDEFINED… NOT to be run" |
| Put IV − call IV feature dropped | Never built. Already planned as dropped in design §2.2 (no SPX option data), and listed in the Stage 1 protocol §2.4. | Yes: Stage 0 approval item 3 (stand-ins only); Stage 1 approval Task B ("NO put-IV-minus-call-IV feature") |
| Intraday benchmark replaced by forecast-based scoring | Stage 1 scored estimators on forecasting forward close-to-close variance. | Yes: Stage 1 approval, decision 3 |
| hmmlearn and ruptures not installed | No Python 3.14 builds; not installed. Requirements file header notes it. | Yes, after the fact: the Stage 0 approval asked for all six; the Stage 1 approval, decision 2, says do not install |
| 2008 start instead of 2004 | Every Stage 1–2 analysis starts 2008-01-02 (`common.py:12`, `dev_guard`). 2004–2007 data stays on disk unused. | Yes: Stage 1 approval, decision 1 |
| SPY use | SPY daily OHLC downloaded and given quality counts in Stage 0. SPY options counted in the free sample. **Never used** in Stage 1 or Stage 2 code: grep finds SPY only in `stage0_fetch.py`, `stage0_audit.py` and `stage0_eodhd_check2.py`. Not used to repair stale opens. | Yes: Stage 0 approval item 4 (download); Stage 1 approval rule 5 (no SPY targets; repair only if needed) |

---

## Part B: rule compliance checklist

**1. Data split respected. PASS** (one note)

**Every place a date limit is set:**
- `common.py`:
  - line 12: `DEV_START` = 2008-01-02;
  - line 13: `DEV_END` = 2016-12-31;
  - line 15: `LOCK_START` = 2021-01-01;
  - line 18: `ANALYSIS_MAX_DATE` = `DEV_END`;
  - line 25: `VAL_MAX_DATE` = 2020-12-31;
  - lines 28–32: `lock_guard`, which raises for 2021+;
  - lines 35–40: `val_guard`;
  - lines 43–53: `dev_guard`, which calls `lock_guard` first.
- `features.py`:
  - line 16: `LAST_DEV_SESSION` = "2016-12-30";
  - lines 23–41: `read_dev_csv` stops at the first later row and then calls the guard;
  - line 54: `build_curve` guard;
  - line 133: `base_variables` guard.
- `compare.py` lines 116–117: `dev_guard` on its inputs.
- `stage2.py`:
  - lines 26–29: `load(last_date, guard)`;
  - line 111: `dev_run` uses `dev_guard`;
  - lines 158–164: `run_validation` uses `val_guard`, with a 2017-01-03 evaluation start;
  - line 190: `main` loads with "2016-12-30" and `dev_guard`.
- `clean.py` line 119: a dev-only check (≤ 2016-12-31).

**Loaders that read later years:**
- **`clean.py`** reads all years. The Stage 1 approval allows that ("cleaning code so it can run on all years"). For 2017+ it writes row-level flags into the clean CSVs but reports only row counts (`counts_by_block`, and `dev_count` for flag totals).
- **`stage0_audit.py`** computed data-quality value checks over all years in Stage 0, including the locked years: one-day spike prints, OHLC flags, stale-open counts, Cboe vs Yahoo close agreement (which named 2019-02-28 and 2021-08-11). An ad-hoc check during Stage 0 also printed the share of days with both an upper and a lower wick, per year through 2026.
  - These are quality checks, not relationships, and the Stage 0 approval allowed "quality".
  - The stricter Stage 1 rule ("must not compute any statistic of values" in later years) came later. **Note, LOW.**

**No analysis or scoring code path loaded values after 2016-12-31:**
- `run_validation` was never called on real data. There are no `val_2017_2020` ledger rows.
- `stage2_results.json` reads `"validation": "SKIPPED: no feature passed development"`.

**2. Protocol before scoring. PASS**

| Protocol | Commit time (UTC) | First scored ledger row (UTC) | Gap |
| --- | --- | --- | --- |
| `stage1_protocol.md` `e2ff0b6` | 2026-10-18 02:29:42 | 02:33:42 (Stage 1, 26 rows) | 4 min 0 s |
| `stage2_protocol.md` `ebdd22d` | 2026-10-18 02:42:25 | 02:44:51 (Stage 2, 3 rows) | 2 min 26 s |

The clean manifest was created at 02:33:31, also after `e2ff0b6`. The Stage 1 feature file was built after scoring, because Rule A picks the estimator first. That order is consistent with the protocol.

**3. Search ledger. PASS** (partly verifiable)
- 29 rows, ids 1…29 with no gaps. 4 run ids: 1 for Stage 1's 26 rows, and 3 for Stage 2, one per feature.
- Triggers `search_ledger_no_update` and `search_ledger_no_delete` abort any UPDATE or DELETE.
- **Could not be verified through git:** `spx_vol.db` is gitignored (`.gitignore:73 *.db`), so there is no git history of its rows. The evidence is the triggers plus contiguous ids.

**4. Hypothesis slot. PASS**
- `hypothesis_ledger.csv`: last commit `f20f8bd` (2026-10-05), not in the diff since the baseline, and clean in the working tree.
- No code in `spx_vol/` references `research_database`, `hypothesis_ledger` or any registry, and nothing was hashed or registered.

**5. SPX-only rule. PASS**
- Every scored target is SPX's own forward variance (Stage 1) or VIX² minus SPX forward variance (Stage 2).
- SPY appears only in Stage 0 download and audit code (see Part A). There is no SPY in `clean.py`, `features.py`, `compare.py` or `stage2.py`.

**6. Broker and network calls; downloads. PASS** (one wording mismatch, see Part E)
- **Network code:** `stage0_fetch.py:19, 48` (Cboe, Yahoo, historicaldata.net; all free) and `stage0_eodhd_check.py:37` (EODHD).
- **EODHD logs:** request 1 got 200 (underlying-symbols); the follow-up made 3 more, getting 200 (underlying-symbols again), 200 (SPX direct) and **404** (VIX direct). **4 of 20, no quota error.** The token isn't stored in either log.
- No Alpaca or broker code anywhere in `spx_vol/`. Nothing was purchased.
- **Downloads:** 299 raw files with manifest entries; **SHA-256 of all 299 matches `manifest.json`**. That's every raw file, not a sample. The manifest also lists 4 derived JSON entries.

**7. Isolation. PASS** (partly verifiable)
- `git diff --name-status 8a3205b HEAD`: only `CLAUDE.md` is modified; every other change is a new file under `spx_vol/` or a new report. No bot file changed.
- `spx_vol/.venv` is ignored (`.gitignore:56`). Every pip install in this work used `spx_vol\.venv\Scripts\python.exe`.
- **Could not be verified:** that the system Python's site-packages, which the bots use, are unchanged. There is no baseline package list to compare against.

**8. No look-ahead. PASS** (19 of 19 tests pass on synthetic data; read and confirmed)
- **`test_stage1.TestNoLookahead`:**
  - `test_truncation`: features from data cut at T equal the full-data features up to T.
  - `test_perturb_future`: random changes to every input after T leave the features at ≤ T unchanged.
- **`TestTargetAndPurge`:** forward target = t+1…t+h, missing at the end; training rows ≤ T − 2h.
- **`test_stage2.TestNoLookahead`:** perturbation test for the baseline inputs and the 3 features; G equals a hand computation over t+1…t+21; a change at t+22 has no effect, while a change at t+21 does.
- **`TestSchemeAndLedger`:** gap of 42, minimum training of 756.
- **Gap, LOW:** the Stage 1 comparison inputs (window estimates) aren't perturbation-tested directly. They are trailing rolling means, and Stage 2's perturbation test covers the same trailing realized variance.

**9. No trading P&L; no BXM/PUT/CNDR/BFLY. PASS.** Grep of `spx_vol/*.py` for BXM, PUT_History, CNDR, BFLY, pnl and profit finds nothing.

**10. Raw data never modified. PASS.** 299/299 hashes match. The clean manifest's 297 source hashes all equal the Stage 0 manifest. The clean, feature and result outputs are separate files.

**11. Commits are code and docs only; CLAUDE.md size. PASS**

| Commit | Files | CLAUDE.md (characters, CRLF) |
| --- | --- | --- |
| `8a3205b` (baseline) | — | 148,616 |
| `dfa3c8c` | CLAUDE.md, requirements, design, Stage 0 report | 149,252 |
| `e2ff0b6` | 6 Stage 0 scripts, `search_ledger.py`, Stage 1 protocol, design | (not touched) |
| `700d2be` | CLAUDE.md, 6 Stage 1 code files, Stage 1 report | 149,543 |
| `ebdd22d` | Stage 2 protocol | (not touched) |
| `e138fd9` | CLAUDE.md, `common.py`, `features.py`, `stage2.py`, `test_stage2.py`, Stage 2 report | 149,762 |

No `.csv`, `.db` or data `.json` was committed. Note: `data_snapshots/spx_vol_engine/` isn't gitignored, only left untracked, so a careless `git add .` would commit 246 MB.

**12. Stage 2 validation correctly skipped. PASS**
- `stage2.main` calls `run_validation` only for features in `passed_dev`, which was `[]`.
- `run_validation` exists as an unused code path.
- `test_stage2.TestLock` confirms that `dev_guard`, `val_guard` and `lock_guard` raise on 2021 dates, and that `build_inputs`, `run_validation` and `dev_run` refuse data reaching into 2021, or 2017 for development.

---

## Part C: deviations and errors

| # | Deviation | Disclosed? | Approved? | Changed a score? | Severity |
| --- | --- | --- | --- | --- | --- |
| 1 | **VIX futures rows with a zero open or high < low were flagged, not dropped.** The Stage 1 approval said "use settlement price only (drop listing-day placeholders, zero opens, high<low)". Only rows with a settlement ≤ 0 were dropped, so listing-day rows with a positive placeholder settlement were kept (e.g. the first row of `VX_2024-01-17.csv`: open 0, high 23.65 < low 27.00, settle 25.00). | Yes: Stage 1 protocol §1.4 (committed before scoring) and report §2.4 | No; it contradicts the approval wording | Could only affect the futures curve, so in Stage 2 only `fut_slope__raw` (CM60 − CM30). Placeholders mostly sit on far-dated new listings. **The size of the effect wasn't measured.** The feature failed by −91% and failed (c) as well. | **MEDIUM** (wording breach; probably no change to the decision) |
| 2 | 252-day windows accept ≥ 250 non-missing values (Stage 1 deviation D2) | Yes (Stage 1 report §6) | No (made during construction, before any feature met a target) | No: the Stage 1 scores don't use features, and Stage 2 used raw features | LOW |
| 3 | Futures curve interpolated linearly in days to expiry on price, not "variance time" (D1) | Yes: written into the protocol before scoring, and the design updated | Implicitly (later approvals cite those commits) | No (protocol fixed before scoring) | LOW |
| 4 | 164 stale SPX opens in 2008–2016 left unrepaired; the open-based estimators fall back to close-to-close on those days | Yes (protocol §3.1, report §2.2) | Consistent with the SPX-only rule (SPY repair only for 2004–2006) | It makes the range estimators slightly more like close-to-close on 157 evaluation days. Their ranking against close-to-close was already clearly worse at h = 21. | LOW |
| 5 | Wrong sentence in the Stage 2 protocol: the first validation refit doesn't reproduce the frozen 2016 training set | Yes (Stage 2 report §7) | n/a | No (validation never ran) | LOW |
| 6 | Calibrated VIX produced negative variance at h = 5 (floored on 289 days; QLIKE 1,463) | Yes (Stage 1 report §4.3) | Follows the protocol's floor rule | Only the secondary horizon, with no decision weight. It makes "P_har beats VIX_cal" at h = 5 trivially true. | LOW |
| 7 | Only 4 of the 6 approved libraries installed | Yes (Stage 0 report, requirements header) | Accepted later (Stage 1, decision 2) | No | LOW |
| 8 | Stage 0 computed value-based quality checks in the locked years (spikes, stale opens, source agreement, and an ad-hoc wick share per year) | Partly: the Stage 0 report gives them as data quality | Stage 0 allowed "quality". The stricter rule came in Stage 1. | No | LOW |
| 9 | The Stage 0 report says the EODHD check had "no quota or error response", but the VIX direct query returned **HTTP 404** (shown as "0 records") | No: the wording is inaccurate | — | No (the conclusion "no VIX options" stands) | LOW |
| 10 | Commit `9591c5c` was amended to `dfa3c8c` to strip a stray BOM from the message, against the "prefer a new commit" guideline; local only, same content | No | No | No | LOW |
| 11 | The Stage 1 protocol says "every analysis function calls `dev_guard()`". Pure helpers (`estimators.*`, `compare.forward_target`, `ewma`) don't; their callers do. | No | — | No | LOW |
| 12 | `e138fd9` (Stage 2) changed the Stage 1 files `common.py` and `features.py` after Stage 1 scoring (guard parameters, `lock_guard`). The defaults are unchanged, Stage 1's 13 tests still pass, and nothing was rescored. | Yes (Stage 2 report §6) | Implicitly | No | LOW |
| 13 | The CLAUDE.md pointer says "VIX beat every history-based RV forecast at 21 days". That's true for the point estimates; significance was only tested against CC_har and the Rule B benchmarks. | No | — | No | LOW |
| 14 | The Stage 1 approval was cut off mid-deliverable, and the missing part was inferred | In the chat summary, not in the report | — | Unknown | LOW (could not verify) |
| 15 | Stage 2 check (b) "split at the midpoint of dates" was implemented as the median row date of usable rows | Implicitly (report gives the split date 2012-06-29 / 07-02) | Reasonable reading | No | LOW |

---

## Part D: efficiency

**1. What could have been skipped without changing any decision:**
- **Features:** 124 of the 127 were never used in a decision. Stage 2 used 3 raw features and recomputed them in `stage2.build_inputs`; the feature file only served as a cross-check. The approvals did order the 127 (Stage 0 item 5, Stage 1 Task B), so this is a cost of the plan, not a breach.
- **Estimator models:** of 13 models × 2 horizons, Rule A ("close-to-close unless a range estimator beats it") and Rule B could have been decided with about 5: CC_har, CC_raw21, VIX_raw, EWMA and one range-estimator HAR. The 5 raw-window range models and the h = 5 horizon carried no decision weight.
- **Downloads:** never used in any decision:
  - VIX1Y and VIX1D (VIX1D lies entirely in the locked years);
  - SPY daily;
  - the 239 MB options sample, which had a quality-only role;
  - VIX futures 2004–2007, after the 2008 start.
- **Exploratory work:** the Stage 0 per-series quality audit was useful (it found the ×10 futures units, the 2013 hole and the stale opens). The extended spike and wick checks weren't needed.

**2. Wall-clock time** (from git commit and stored timestamps, ET, 2026-10-17; approval arrival times aren't in git):

| Stage | Start evidence | End (commit) | Duration |
| --- | --- | --- | --- |
| Stage 0 | First download 22:08:33 | `dfa3c8c` 22:21:57 | ~13 min |
| Stage 1 | Protocol `e2ff0b6` 22:29:42 (previous commit 22:21:57) | `700d2be` 22:36:26 | ~7 min after the protocol (~14.5 min after Stage 0) |
| Stage 2 | Protocol `ebdd22d` 22:42:25 | `e138fd9` 22:45:47 | ~3.5 min after the protocol (~9 min after Stage 1) |

The design proposal came before Stage 0 and has no commit of its own (it was first committed in `dfa3c8c`).

**3. Scope creep** (done though no approval asked for it):
- Downloading VIX1Y and VIX1D. The approval's stand-in list didn't name them, though item 4 approved Cboe's free files in general.
- The second EODHD script (`stage0_eodhd_check2.py`), within the 20-request budget.
- The ad-hoc wick-share check over all years.
- Raw-window versions of every estimator: declared in the protocol, but not requested.
- A descriptive "frozen 2016 coefficients" path in `run_validation`: declared in the protocol, never run.

All minor. The larger scope (127 features, anomaly and analog design) came from the user's spec and design approvals.

**4. Asked for but not done:**
- **Two of the six libraries** (later reversed by the user).
- **Dropping the zero-open and high < low futures rows** (deviation 1).
- **A power estimate:** in the design's Stage 0, not in the approval.
- **Whatever followed the cut-off Stage 1 deliverable line:** unknown.

**5. What a leaner version would have looked like.** Start from the one question that was actually decidable: does anything beat VIX for SPX volatility, or for the VIX-versus-realized gap?
- Pick the 3 test features first, and build only those plus the baseline inputs: VIX, trailing close-to-close RV, CM30 and CM60 from the futures curve, VVIX and SKEW, for 2008–2016.
- Clean only the series those need.
- Compare VIX against 2–3 history-based forecasts at one horizon.
- Run the 3-feature gap test.

That is roughly a fifth of the code. It would have reached the same two conclusions (VIX wins; no state feature helps) with fewer downloads and a much smaller search ledger, which also matters later for the Deflated Sharpe Ratio. **Recommendation: yes, adopt a rule like "choose the test features and the decision rule before building any feature set; build only what the chosen test needs."** Keep the wider feature library only for a stage that has explicitly been approved as exploratory, and log its breadth.

---

## Part E: independent sanity checks (stored values only, nothing recomputed)

**Stage 1** (`data_snapshots/spx_vol_engine/results/stage1_estimator_comparison.json` against `search_ledger` rows 1–26 and the Stage 1 report):
- Every model's QLIKE in the ledger `value` field equals the results file exactly, and every MSE in the ledger `notes` field equals the stored MSE. That's 26 of 26.
- Every number in report §4.2–4.3 matches the stored values (QLIKE, intervals, MSE ×10⁻⁴, Δ vs CC_har with intervals). So do:
  - Rule A (CC_har is best; CC adopted at h = 21; P_har best at h = 5 but not significant);
  - Rule B (none beaten at h = 21; at h = 5, CC_raw21 and VIX_cal beaten);
  - fallback days 164 / 157;
  - n_eval 1,741 / 1,757;
  - blocks 42 / 21;
  - VIX_cal h = 5 floors 289.
- **No mismatch.**

**Stage 2** (`stage2_results.json` against ledger rows 27–29 and the Stage 2 report):
- The improvement figures match the ledger `value` and the report exactly: −91.171 / +2.936 / −18.541%.
- The intervals (98.33%), the half-sample coefficients, check (c) (−12.46 / −1.07 / −8.59%), check (d) and the mean G of 88.05 all match.
- The run ids match between the ledger and the results file. `passed_dev` = [] and validation = SKIPPED.
- **No mismatch.**

**Stage 0** (EODHD log against the Stage 0 report): **mismatch.** The report says "no quota or error response", but the stored log shows statuses 200, 200, 200 and **404** (the VIX direct query). The conclusion (no VIX options on EODHD) still holds; the wording doesn't.

---

## Items that FAILED

None of the 12 checklist rules. One stored-vs-reported mismatch (Part E, Stage 0 EODHD wording). One deviation from an approval's wording (Part C #1, futures placeholder rows).

## Items that could not be verified, and why

1. **The ledger's append-only history through git:** `spx_vol.db` is gitignored. The only evidence is the database triggers and contiguous ids.
2. **That the system Python and the bots' environment are unchanged:** there is no baseline package listing to compare against. The evidence is that every install used the venv's own Python, and that no bot file changed in git.
3. **How many placeholder or zero-open futures rows were kept in 2008–2016, and their effect on CM30/CM60:** finding out needs a new computation on the data, which this audit was not allowed to do.
4. **The cut-off end of the Stage 1 approval:** the text isn't available.
5. **Wall-clock time per stage from approval to delivery:** approval times aren't recorded in git, so the durations above run from the first evidence of work.

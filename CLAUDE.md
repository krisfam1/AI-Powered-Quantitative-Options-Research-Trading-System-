# AI Option Trading Bot — Project Memory

**Read this file at the start of every session in this folder.** It is the persistent memory for this research project, since each Claude Code session otherwise starts with zero history. Keep it updated as work progresses — when something here becomes stale (a bug gets fixed, an experiment closes out, a status changes), edit this file directly.

**Last updated: 2026-10-06** (F1 and the SPY 1-day iron fly closed HELD before registration, Sections 64–65; archive pass 4. Earlier, 2026-10-05: tiered_v1 judgment calls user-approved; pre-live checklist with DSR; CPCV note; `hypothesis_ledger.csv`; Modern Standby root cause of the 10/4 task failures. Earlier, 2026-10-02: cross-sectional straddle HELD / INCONCLUSIVE, data-limited; ORATS declined. Section 62. Its slot reallocated to trial #13, VIX term-structure → CNDR, which was REJECTED at Stage 1 the same day. Section 63. **Tiered verdict framework `tiered_v1` adopted, go-forward only. Section 1**).

**This memory is split across TWO files: `CLAUDE.md` (this file, loaded automatically) and `CLAUDE_ARCHIVE.md` (never loaded automatically, so open it deliberately).** Section numbers are unchanged across both. A section marked "Archived 2026-10-01" or "Condensed 2026-10-05" here is a stub: either a one-paragraph locator, or for still-active sections (3, 7, 40, 52; and since pass 3, 26's operations part, 33, 43, 60, 62) a current-state summary whose full history lives in the archive. See Section 61 for the read-the-archive-first rule and the archived-identifier index.

**Reorganization / correction notice history:**
- **Archive passes:** pass 1 and pass 2 (2026-10-01), pass 3 (2026-10-05) and pass 4 (2026-10-06, `archive_pass4_20261006.py`; limit now counted with CRLF) each moved text verbatim to `CLAUDE_ARCHIVE.md` and passed a byte-for-byte restore check. Backups and their SHA-256s are in `CLAUDE_ARCHIVE.md`: pass 3's header for pass 3, and pass 3's "Header" block for passes 1 and 2. Pass 3's round trip was verified by `archive_pass3_20261005.py` on the file as committed in `57079e8`. Later edits to condensed sections are ordinary updates, not part of the pass.
- **Known cross-document drift:** the claude.ai `research-manifest.md` (not synced) still shows RF v2 as Stage-1-VALIDATED. Here it's REJECTED on clean data (Sections 48/56/58). The manifest's section numbers also differ (e.g. its "Section 24" = Section 60 here). Fix the manifest by hand.
- **Manifest propagation backlog (condensed 2026-10-06, archive pass 4; the full bullets are verbatim in `CLAUDE_ARCHIVE.md`, Pass 4):** straddle HELD and ORATS declined (§62); trial #13 registered and REJECTED (§63); `tiered_v1` and its user-approved judgment calls, no retrofit of IV v2 / SPY GEX v3 (§1); pre-live checklist, CPCV note, `hypothesis_ledger.csv` (§1); IV literature caution (§33); sleep fixes and Wi-Fi-in-standby (§60); archive pass 3; F1 HELD (§64); SPY 1-day iron fly HELD (§65). The manifest's section numbers differ from these (e.g. vol-level control §43, group fixed effects §1/§58, economic check §33 here).

A parallel copy of this content lives in the claude.ai project "AI Option Trading Bot" (`research-manifest.md`) for cloud-session continuity. The two aren't automatically synced — if you make a significant update here, mention it back in that other conversation too (or vice versa).

---

## 1. Core philosophy (do not violate)

- **V1 is frozen** — the original strategy/backtest is a permanent benchmark/control. Never delete it, never modify it in place, even when superseded by better methodology. **V1 is a control, not a bar every signal must clear** — the objective is discovering genuine, repeatable, economically exploitable phenomena in the data, not beating V1 specifically. A signal can fail to beat V1 for reasons that have nothing to do with whether it's real (V1's architecture may simply exclude the conditions where that signal matters — e.g. its bullish-only gate structurally excludes exactly the market conditions a volatility-regime signal would need). Explicit reminder, added 2026-09-22 after three rejections in a row (V1 itself, GEX call-wall-distance, GEX net gamma regime): **a string of rejected hypotheses is the research process working correctly, not the project failing.**
- **Every new idea is a hypothesis, not an assumption.** Nothing gets treated as "working" until independently validated.
- **Failures must be root-caused**, not just declared "doesn't work." Classify into one of: **genuine signal failure** (the theorized mechanism doesn't hold in the data) / **redundant signal** (adds nothing beyond an existing validated signal) / **strategy-context failure** (the mechanism may be real, but the population/context it was tested in — e.g. V1's restricted gate — structurally excludes the conditions where it would show up) / **data limitation** (insufficient N, granularity, or history to test it properly) / **economic/pricing failure** (destroyed by realistic pricing/execution costs, independent of signal quality) / **model limitation** (the test/model construction, not the underlying phenomenon, is inadequate) / **insufficient evidence** (result is genuinely ambiguous — not enough power to distinguish a real small effect from noise). Refined 2026-09-22 (was: genuine signal failure / redundant with existing work / incompatible with V1's restricted population / data-limited / destroyed by pricing-execution economics / model-limited / inconclusive — same categories, "incompatible with V1's restricted population" broadened to "strategy-context failure" since the same failure mode applies beyond just V1's population, e.g. any signal tested inside an unrelated gate).
- **Successes are never immediately implemented.** They need independent validation, robustness checks, out-of-sample testing, and an economic sanity check first.
- **Correctness over speed.** Weeks/months timelines are explicitly fine. Don't rush to a number.
- **North star:** long-term real profitability trading options.
- **The SQLite databases are ground truth for results** (`v1_v2_research_results.db`, `v2_pricing_log.db`, the research-framework DB from `create_research_db_schema.py`). Query them directly — don't trust a remembered number from a prior session or conversation.
- **Every ML-track experiment comparing a richer/nonlinear model against a simpler baseline must include a `shuffled_target_placebo` robustness check (target randomly permuted before training; the check PASSES if it shows NO significant effect).** Added 2026-09-25, prompted by the XGBoost feature-interaction experiment (Section 44) where this was the single most decisive check in the whole run — it confirmed the pipeline had no leakage, and directly demonstrated the tiny real-data effect size sat inside the noise band the placebo itself established. Non-negotiable for this class of experiment going forward, same severity as the id-date rule is for EODHD queries.
- **No new hypothesis until one of the current three resolves** (user decision, 2026-10-01): IV term-structure Stage 2 (v2 since 2026-10-01; locks ~2027-06-10), SPY GEX v3 (since 2026-10-01; locks ~2027-01-27), and **the cross-sectional straddle hypothesis (Section 62), which took the 59-ticker Target C slot on 2026-10-01** (Target C retired, Section 60). Design fixes to these three are fine; opening a fourth is not.
  - **2026-10-02: the straddle hypothesis is HELD / INCONCLUSIVE (data-limited) and parked, with no further spend (Section 62).**
  - **DECIDED 2026-10-02 (user): the held straddle's slot goes to trial #13, VIX term-structure timing of index volatility selling (Section 63).** This is a deliberate reallocation to that specific replacement, not an automatic rule that "held" frees a slot.
  - **2026-10-02: trial #13 REJECTED at Stage 1 (Section 63), so its slot is OPEN.** Active: IV term-structure v2, SPY GEX v3. What fills the third slot is a user decision.
  - **2026-10-06: candidate F1 (earnings) closed HELD before registration, data-limited (Section 64). The slot is still OPEN.**
  - **2026-10-06: the 1-day SPY iron fly candidate also closed HELD before registration, data-limited (Section 65). The slot is still OPEN.**
  - **DECIDED 2026-10-01 (user): slot swap, not an exception.** Target C was retired because it predicted (relative) realized vol, the same structural flaw the IV Stage 1 economic check exposed that evening (Section 33): forecasting RV mostly recovers the already-priced IV level, while a tradeable position pays RV − IV. The cross-sectional straddle hypothesis, whose payoff *is* the RV − IV gap, took its slot. The count stays at three; no exception was used.
- **TIERED VERDICT FRAMEWORK, `tiered_v1` (user decision 2026-10-02; go-forward only).** Replaces the flat-OR rule (any failed robustness check → REJECTED) for every pre-registration from 2026-10-02 on.
  - **Four tiers:**
    - **REJECTED:** a clean, decisive negative. It is the only "closed forever" tier.
    - **HELD:** couldn't cleanly resolve; resumable. It's the default for a failure that isn't a clean negative, and HELD rows form the **signal library** (trial #12 is its first member).
    - **VALIDATED_SMALL_SIZE_MONITOR:** the primary bar and the hard gates pass, with some soft-check failures.
    - **VALIDATED_FULL_CONFIDENCE:** everything passes.
  - **Hard gates vs soft checks, declared before the hash locks:**
    - Every new config must carry `parameters["tiered_grading"]` (see `tiered_verdict.py`).
    - **Hard gates:** 1–3 checks whose failure means the signal isn't real or is a known confound, e.g. the group/ticker fixed-effects baseline (Sections 1 and 58), a volatility-level control (Section 43), or an economic-relevance check (Section 33). **Any hard-gate failure → REJECTED, no exceptions.**
    - **Soft checks:** everything else. They set the tier (0 failures → FULL; up to a declared `max_soft_failures_for_small_size` → SMALL; more → HELD) and later capital sizing. **They never cause REJECTED by themselves.**
    - Hard + soft must partition `declared_robustness_checks` exactly.
  - **The significance bar is never loosened:**
    - The declared α must be ≤ 0.05 one-sided, and should equal the design's Bonferroni-adjusted α (e.g. 0.0167 for 3 horizons). The config validator can't check that against `multiple_testing.py`, so the person registering must.
    - Optional `min_abs_t_stat` (e.g. 3.0) adds a Harvey–Liu–Zhu t-bar on top.
  - **Grading order (`tiered_verdict.grade`):**
    1. Missing results → INCOMPLETE (not a verdict).
    2. Any hard gate failed → REJECTED.
    3. Primary estimate in the wrong direction → REJECTED if the design was adequately powered (≥ 80% at the declared floor) **or** the reversal is itself significant; otherwise HELD.
    4. Primary bar not met (p ≥ α, below the effect floor, or t below `min_abs_t_stat`) → **REJECTED only if adequately powered AND the confidence bound excludes the floor (a "decisive null")**; otherwise HELD.
    5. Primary bar met → FULL / SMALL / HELD by soft-failure count.
  - **USER-APPROVED 2026-10-05: the two "clean, decisive negative" interpretations (steps 3 and 4), exactly as implemented in `tiered_verdict.py`.**
    - **(a) Wrong direction** is REJECTED only if the design had ≥ 80% power at the effect floor, or the reversal is itself significant at α. Otherwise it's HELD.
    - **(b) No effect / below the floor** is REJECTED only if the design had ≥ 80% power at the floor **and** the confidence bound excludes the floor. Otherwise it's HELD. **Both conditions explicitly re-confirmed by the user on 2026-10-05**; power alone is not enough.
    - Why: without the power condition, every adequately tested null would sit in HELD and never close, and an underpowered wrong-sign blip would close an idea forever.
    - The 80% threshold is a framework constant, deliberately not declarable per experiment.
  - **Hard-gate design guidance:** a gate written as "partial correlation must be *significant*" can fail from low power alone and then REJECT a real signal. Prefer gates that test for the confound itself (e.g. "the effect collapses when the control is added"), and give hard gates enough power.
  - **Deployment ladder (informational only; nothing here makes the project ready for live capital):**
    - FULL: start small with tight limits, compare live results with the research prediction, and scale only if they match.
    - SMALL: the smallest rung only, monitoring the failed soft checks.
    - HELD: library; resuming needs a new versioned pre-registration and a slot.
    - REJECTED: closed.
  - **Code:**
    - **New:** `tiered_verdict.py` (tiers, declaration validation, pure `grade()`) and `test_tiered_verdict.py` (49 checks, all pass on a fresh schema).
    - **Changed:**
      - `experiment_config.py`: validates the declaration at construction; validation only, so no existing hash changes.
      - `experiment.py`: `preregister_experiment()` refuses a config without the declaration unless `allow_legacy_grading=True`, which only the legacy test fixtures use.
      - `run_experiment.py`: a new append-only table `experiment_primary_results`; tiered experiments skip the legacy all-or-nothing `robustness_survived` gate.
      - `verdict.py`: a tiered path, used only when the locked config declares it.
    - **Verified:**
      - Legacy test results are identical before and after on a fresh schema. The only failures are the pre-existing "Phase 6/7 record" checks, which need production rows.
      - All 6 registered configs still reproduce their registered hashes.
      - The production `research_database.db` was untouched by the tests, which ran in a scratch directory.
  - **Not retroactive:**
    - Closed verdicts stand: V1, the GEX family, the ML chain, strike positioning, and trial #13.
    - Open experiments keep their locked rules: IV term-structure v2 and SPY GEX v3.
    - **DECIDED 2026-10-05 (user): IV term-structure v2 and SPY GEX v3 are NOT retrofitted onto `tiered_v1`.** Each runs to completion under its own locked, legacy decision rules.
  - **Future consideration: Harvey–Liu–Zhu (t ≥ 3, one-sided p ≈ 0.00135).**
    - For a correlation test this needs |r| ≥ 0.29 at N = 100, 0.25 at N = 139, and 0.21 at N = 203. 80% power at r = 0.25 then needs N ≈ 229 instead of 139 (about 1.6×).
    - Candidates for the stricter bar: designs with many researcher degrees of freedom (multiple tickers, horizons, or feature sets). The program is at 13 trials.
- **PRE-LIVE CHECKLIST (added 2026-10-05; research-review item). No hypothesis gets real capital until all of these hold.** Paper trading isn't gated by this.
  1. A `tiered_v1` verdict of VALIDATED_FULL_CONFIDENCE or VALIDATED_SMALL_SIZE_MONITOR. A small-size verdict allows only the smallest rung.
  2. An economic check using real costs (EODHD end-of-day spreads at base, 0.5× and 1.5×; Section 26) that is still positive.
  3. **A Deflated Sharpe Ratio (Bailey & López de Prado 2014) of at least 0.95** on the strategy's out-of-sample return series.
     - Use the number of trials in `hypothesis_ledger.csv`, currently 13.
     - Use the actual skewness, kurtosis and track length of those returns.
     - Disclosed limitation: most trials were correlation tests that produced no Sharpe ratio, so the variance of Sharpe ratios across trials must be estimated or bounded conservatively, and the method stated.
     - No DSR code exists yet; write it, with tests, when the first candidate reaches this step.
  4. A live or paper track compared with the research prediction before any scale-up (the deployment ladder above).
  - **Section numbering:** CLAUDE.md §26 is the paper-bot audit, not a live-capital checklist. This bullet is the checklist.
- **CROSS-VALIDATION RULE FOR FUTURE DESIGNS (added 2026-10-05; research-review item): CPCV upgrade note.**
  - Any future design that uses cross-validation for model selection or evaluation (the ML track, walk-forward designs) should use **Combinatorial Purged Cross-Validation** (López de Prado 2018, *Advances in Financial Machine Learning*, ch. 7 and 12) instead of a single walk-forward path.
  - Purge training rows whose labels overlap the test period: at least max(forward horizon, longest feature window), the rule first written for Target C (Section 60, `fold_structure.purge_rule`). Add an embargo after each test block.
  - Report the distribution of out-of-sample results across paths, and the probability of backtest overfitting (PBO; Bailey et al. 2017).
  - Applies to new pre-registrations only. Neither open experiment uses cross-validation (both are single correlation tests), so neither is affected.
- **Program-level hypothesis-trial tally** (added 2026-10-01). Every hypothesis whose outcome has been examined against data, or that is pre-registered and pending, counts once; any future Deflated Sharpe Ratio or multiple-testing assessment uses this count as the number of trials. Versions of one hypothesis (v1→v2→v3) count once.
  - **Machine-readable ledger (started 2026-10-05): `hypothesis_ledger.csv`**, one row per trial. Columns: status, resolution date, pre-registration type, experiment id, final config hash, primary result, failure classification, versions, section.
    - Every new trial gets a row **when it is registered**, not when it resolves.
    - Tools read the CSV, never this file.
    - Closed trials' hashes and verdicts were checked against `CLAUDE_ARCHIVE.md` and `research_database.db` when it was created.
  1. V1 entry signal / Phase 6 · 2. ML Experiment 1 · 3. GEX call-wall-distance · 4. GEX net gamma regime · 5. Strike-positioning OI skew · 6. XGBoost feature interactions · 7. XGBoost vol vs Ridge · 8. RF vol vs Ridge (v1+v2) · 9. Regularized XGBoost vol · 10. IV term-structure slope (pending Stage 2) · 11. SPY GEX call-wall vs vol (pending) · **12. Cross-sectional straddle, Goyal–Saretto RV−IV gap (Section 62, HELD / INCONCLUSIVE, data-limited, since 2026-10-02)** · **13. VIX term-structure slope → Cboe CNDR short-vol returns (Section 63, REJECTED at Stage 1 2026-10-02, hash `188828a6…`)**.
  - The tally counts hypotheses examined against data or pre-registered, not only formally pre-registered ones: #1 (V1) and #12 (straddle) were never pre-registered.
  - Not counted: Target C (designed, never run, no outcome examined) and the 5-bar horizon exploration (exploratory, already invalidated).
  - The exploratory economic sanity check (Section 33) is analysis of trial 10, not a new trial.
- **Every pre-registration carries a `POWER_ANALYSIS` block** (added 2026-10-01): built with `power_analysis.power_table()` at the locked N and α, placed **outside** the `ExperimentConfig` so it never changes the hash. Report power at the floor effect and at r = 0.20 / 0.25, plus the smallest effect detectable with 80% power. With a low-power design, a REJECTED means "no effect ≥ that detectable size", not "no effect".
- **Before assuming a roadmap area is "untouched" or building a new script from scratch, check the actual codebase first** (grep filenames, read existing scripts). This has burned us twice: two "newly discovered" bugs already had fixes elsewhere, and the Gamma/GEX area was wrongly marked "Untouched" when a real pipeline already existed.
- **A pre-registration's `config_hash` freezes the analysis plan (hypothesis, test statistic, decision rules, thresholds) — it does NOT freeze, version, or fingerprint the contents of whatever external dataset `dataset_version` points to.** Confirmed directly from `canonical_hash.py:compute_config_hash()`: it hashes only `ExperimentConfig`'s own declared fields; it has no path that reads the referenced SQLite database, and `dataset_version` (`experiment_config.py:46`) is a plain string label, not a content hash. **Rule, made explicit 2026-09-28 after the Section 56 data-contamination fix, but consistent with every prior hash-change event in this project** (GEX call-wall-distance's `date_range` fix, IV term structure's `test_period` fix, SPY GEX's N-off-by-one/OPEX fixes, the regularized-XGBoost-v2 placebo-leak fix — every one of these changed the hash because a literal `ExperimentConfig` field was edited, never because underlying data was merely regenerated): **a disclosed, root-caused fix to an upstream data-generation bug does NOT require a new hash, provided no `ExperimentConfig` field is edited** — it restores fidelity to the original frozen plan rather than creating a new one, and forcing a rehash for every such fix would make hash changes noisy and erase the one distinction they exist to preserve (methodology-frozen vs. not). **Real, disclosed gap this exposes**: since `dataset_version` is just a static label, the same hash can silently span two empirically different dataset realizations over time (e.g., `472bf091...` refers to both the pre- and post-2026-09-27 `xgboost_volatility_dataset.db`) with nothing in the config distinguishing which one a given reported result used — worth closing going forward (a generation-date-qualified label or literal content hash for `dataset_version`), not by retroactively rehashing already-reported results.
- **Any per-observation test pooled across a small number of groups with large between-group heterogeneity needs a group-fixed-effects (or group-demeaned) baseline, not just a random per-observation train/test split.** A model can look genuinely predictive purely by recovering group averages instead of anything the features themselves contribute, and a plain random/chronological split does nothing to control for this. **Added 2026-09-28, concrete example: `xgboost_volatility_dataset.db`'s 6-ticker, forward-realized-volatility ML track** (Sections 45/46/48/51/54/56/58). Discovered via the regularized-XGBoost-v2 `shuffled_target_placebo` re-leaking (4/8 seeds) on the clean, post-contamination-fix dataset — root-caused to real per-ticker mean target levels varying ~4x (AAPL 0.24 to SMCI 0.92), which a *global* (non-ticker-blocked) label shuffle doesn't fully destroy, letting a model that can even weakly infer ticker identity from the features exploit the residual chance-driven per-ticker mean under any one permutation. The confirming test: a model using **zero options features** — just "which ticker, predict its own historical average" — scored R²=0.50-0.51 against every one of the four experiments' own real primary test sets, matching or beating every one of their real, fully-tuned 8-feature models. Section 58 has the full retroactive analysis (all four experiments' incremental R² over this baseline came back **negative**). **Practical rule going forward**: any experiment pooling observations across a small, fixed set of groups (tickers, regimes, categories) with real between-group heterogeneity in the target must (a) report a group-fixed-effects or group-only baseline alongside the real result, and (b) block any permutation-based null (placebo, Monte Carlo control) on that same grouping — a day-clustered or pair-clustered permutation (already this project's standing practice elsewhere) is the right idea; the group that actually carries the heterogeneity is what must be blocked, and it isn't always time.

---

## 2. Codebase scale

317 `.py` files in this folder. Most are one-off `fix_*`, `patch_*`, `check_*`, `investigate_*`, `diagnose_*`, `verify_*` scripts from an iterative research history, alongside the live trading engine and a formal research framework (config → gates → verdict → multiple-testing → robustness → orchestrator).

---

## 3. Current best estimates of V1's real economics

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**V1's economics, condensed.** The full parameter table here was an exact duplicate of Section 15 (canonical, kept), and the per-number derivation notes are in the archive.
- Original V1 synthetic backtest: **+$20,427.64 / 251 trades** (frozen baseline).
- IV-only correction (`full_v1_v2_research_experiment.py`): **-$10,072.44 / 237 trades**, verified in `v1_v2_research_results.db` (one row, `V1_vs_V2_corrected_20260914_020211`). The old figure -$1,874.37 is not in any DB: never cite it.
- Spread-only correction (`close_the_loop_real_spreads.py`): -$27,307.36. **UNVERIFIED**: no id-date check.
- Combined real bid/ask (`combined_iv_spread_correction_v2.py`): **-$45,477.00 / 248 trades**. Most trustworthy; reproducible only by rerunning (not saved to any DB). Of this, 71 same-day trades = -$19,010.00 at a mechanically-0% win rate (Section 13).
- Naive combined (`combined_iv_spread_correction.py`): -$11,472.00 / 105. **INVALID** (id-date bug).
- The frozen number is 6 independent $100k single-ticker runs, not one shared portfolio (Section 16).
- **Still UNKNOWN:** whether `portfolio_backtest.py` is the exact original source of the frozen number (no git-history check).

---

## 4. Key validated technical rules (do not relitigate without new evidence)

- **Authoritative record-ID snapshot-date rule:** EODHD records' `id` field has a date suffix (`<contract>-<YYYY-MM-DD>`). This suffix — NOT the `tradetime` field — is the only reliable indicator of which calendar day a record belongs to. `tradetime` can echo the query filter date for illiquid/no-trade contracts rather than reflecting real activity.
- **Safe contract-selection query pattern** (in `v2_iv_pricing_model.py`'s `_select_real_contract()`): query a WIDE exp_date range (`exp_date_from=obs_date, exp_date_to=obs_date+45 days`), then hard-filter returned records to `id_date == obs_date`, require bid/ask/volatility all present, then pick nearest-strike/nearest-DTE. An exact `exp_date_from == exp_date_to` filter is fine for expiration exactness (proven 0% mismatch) but does NOT protect against wrong-day contamination — the id-date filter is what does that.
- **Fixed-contract-identity across entry/exit:** select the contract once at entry; look up the SAME contract symbol at exit (never re-run independent nearest-strike selection at exit), modeled on `get_v2_checkpoint_iv()`.
- **V1's synthetic expiration convention** (`entry_date + 14 calendar days`) frequently does not match any real, discretely-listed exchange expiration (60.9% mismatch rate confirmed). `fix_real_expiration_bug.py` fixed this inside `portfolio_backtest.py`'s `pricing_mode="v2_corrected"` path by parsing the real matched contract's actual expiration from its symbol.
- **JSON:API pagination gotcha** (`gex_data_loader.py`): the `links.next` URL does not carry the API token forward — it must be manually re-appended or every page after the first 401s.
- **`bid_date` is not a reliable day indicator either — confirmed 2026-09-20 spot-check.** Across all raw records checked, `ask_date` matches the record's own `id`-date (~20:00 UTC same day), but `bid_date` is consistently stamped ~04:00 UTC the *next* calendar day. Only the `id` suffix is safe; don't use `bid_date` for day identification any more than `tradetime`.

---

## 5. File inventory highlights (full detail in the claude.ai manifest)

**Pricing/execution correction chain (all VERIFIED by direct read):**
`combined_iv_spread_correction.py` (buggy, superseded) → `combined_iv_spread_correction_v2.py` (corrected, current best estimate) → `v2_iv_pricing_model.py` (the validated core methodology, `_select_real_contract()`) → `gex_data_loader.py` (trading-calendar + pagination helpers) → `fix_real_expiration_bug.py` (expiration-parsing fix already applied to `portfolio_backtest.py`) → `full_v1_v2_research_experiment.py` (official V1 vs V2-corrected comparison, saves to `v1_v2_research_results.db`) → `close_the_loop_real_spreads.py` (spread-only correction, UNVERIFIED, needs id-date fix).

**Gamma/GEX/Greeks/IV pipeline (docstring-level review only as of 2026-09-20 — read full bodies before building on these):**
- 3-phase GEX pipeline: `gex_data_loader.py` → `gex_calculator.py` (Phase 2, computes metrics only) → `gex_lookup.py` (Phase 3, read-only T-1 lookup; documents that "Method A" cumulative-strike-transition construction was NOT found predictive)
- Support: `gex_health_check.py`, `gex_regime_breakdown.py`
- Exposure estimators (all self-caveated as estimates, not verified dealer data): `gamma_gradient.py`, `gamma_landscape.py`, `gamma_regime.py`, `charm_landscape.py`
- Contract selection: `delta_strike_finder.py` (backtest), `pick_contract_by_delta.py` (live, via Alpaca)
- Pricing/quotes: `options_pricing.py` (theoretical BS pricer — relationship to `options_backtest_engine.py`'s pricer unconfirmed), `options_evaluator.py` (live bid/ask via Alpaca)
- IV audits: `iv_hypothesis_test.py` (SMCI/MSTR vs AAPL, "audit only"), `checkpoint_iv_coverage_audit.py`, `checkpoint_iv_coverage_smci_mstr.py` (fixed a naive-weekend-filter bug re: holidays like Juneteenth)
- Regime work: `regime_breakdown_study.py`, `regime_sensitivity_analysis.py` (pre-specified, doesn't touch archived results)
- Prospective: `prospective_gex_pipeline.py` — forward-only data collection for a "call-wall-distance hypothesis," explicitly treated as frozen/unproven. **Unknown whether it has accumulated results yet — check this before assuming nothing is there.**
- `eodhd_spot_check.py` — one-time data validation spot check

**IMPORTANT: none of the GEX/Greeks work above has gone through the formal pre-registered experiment framework (gates/verdict/multiple-testing/robustness) that ML Experiment 1 used.** It's real infrastructure and exploratory/audit work, but no formal verdict exists yet on any GEX or gamma-exposure signal. Don't treat it as either "proven" or "ruled out."

**ML Experiment 1 pipeline:** `features_underlying.py`, `features_options.py`, `features_regime.py` (Feature Factory, 11 features, 10 locked), `ml_experiment1_*.py`, `data_prep_experiment1.py`, `iv_percentile_batch.py`, `preregister_experiment1.py`, `execute_ml_experiment1.py`, `finalize_experiment1.py`. **Result: REJECTED**, robustness-tested.

**Research framework (formal pipeline):** `experiment_config.py`, `gates.py`, `verdict.py`, `multiple_testing.py`, `robustness.py`, `run_experiment.py`, `canonical_hash.py`, `db_interface.py`, `experiment.py`, `create_research_db_schema.py`, and since 2026-10-02 `tiered_verdict.py` (the tiered grading scheme, Section 1).

**EODHD data-capability audits:** `eodhd_field_audit*.py`, `eodhd_audit_term_structure.py`, `eodhd_audit_strike_structure.py`, `eodhd_historical_coverage_audit.py` — confirmed real term-structure + strike-structure depth, 0% null rates on Greeks/IV/bid-ask/OI/volume.

**Closed-out diagnostics (do not relitigate without new evidence):**
- `check_lookahead_bias.py` — no lookahead bias in entry-score/breakout computation.
- `diagnostic_5bar_vs_20bar_v3.py` — 5-bar exploratory finding did not replicate OOS (-0.54% relative MSE reduction).
- V1's raw entry signal shows no predictive edge beyond random chance within its own candidate population (Phase 6).
- V1's apparent historical profitability concentrates in a small number of trades + reversal-guard exits (Phase 7).

**Phase 6/7 forensic attribution (condensed 2026-10-06, archive pass 4; the full verified block is verbatim in `CLAUDE_ARCHIVE.md`, Pass 4; read it before citing a number not repeated here):** Phase 6 day-clustered control T_obs = −0.2569%, p = 0.996/0.997 (579 signals). Phase 7: stop-loss exits −$66,025.67 vs reversal-guard +$86,453.30; the top 5 trades are 97.7% of the frozen $20,427.64; position sizing cost −$5,661.48 vs equal weighting. The underlying back-solve method validated on 251/251 trades. Backfilled rows, not genuine pre-registration.

---

## 6. 16 permanent roadmap areas — status

1. **Options pricing/Greeks** — real progress: combined IV+spread correction at 98.8% coverage (-$45,477.00); IV-only theoretical correction exists (**-$10,072.44/237 trades, DB-verified** — corrected 2026-09-20, see Section 3; -$1,874.37 was a stale/wrong number, do not cite it). **DEFINITE future work queued** — see note below (Greeks sensitivity / Monte Carlo track).
2. **IV/vol structure** — used in Feature Factory (rejected); audit-only work exists (`iv_hypothesis_test.py`, checkpoint-IV coverage audits); no formal experiment yet.
3. **Liquidity/bid-ask/volume/OI** — confirmed constructible; touched via execution-realism correction; no dedicated experiment.
4. **Options term structure** — confirmed constructible; unused.
5. **Strike structure/positioning** — confirmed constructible; `gamma_landscape.py`/`charm_landscape.py` compute per-strike exposure estimates but no formal experiment. **DEFINITE future work queued** — overlaps the Greeks sensitivity / Monte Carlo track below.
6. **Gamma/GEX** — real 3-phase pipeline + exposure estimators + one prospective hypothesis pipeline exist (see Section 5), but no formal pre-registered verdict on any GEX signal yet.
7. **Statistical arbitrage** — untouched. **DEFINITE future work queued** — see note below (Optiver-style RL/stat-arb track).
8. **Cross-sectional/relative-value** — untouched (on the neutral hypothesis list).
9. **Market microstructure/tick-level** — untouched; EODHD is EOD-only, likely infeasible. Relevant to the queued Optiver-style track below — a literal tick-level reproduction is probably not possible with current data; would need a coarser, adapted approach using Alpaca intraday bars.
10. **XGBoost/nonlinear ML** — untouched. **DEFINITE future work queued** — part of the Optiver-style RL/stat-arb track below (closing-price prediction via XGBoost + DNN).
11. **LSTM/sequential models** — untouched. **DEFINITE future work queued** — see note below (LSTM forecasting track).
12. **Monte Carlo pricing/risk** — untouched. **DEFINITE future work queued** — appears in both the Greeks-sensitivity track (volatility-effect Monte Carlo) and the Optiver-style track (backtesting).
13. **Reinforcement learning** — untouched. **DEFINITE future work queued** — see note below (Optiver-style RL/stat-arb track).
14. **Execution optimization** — real progress via the id-date-verified combined correction.
15. **Dynamic position sizing/exits** — untouched by dedicated experiment (Phase 7 flagged concern only).
16. **Alternative strategy architectures** — untouched.

**Three tracks queued as DEFINITE future work (not started, added to roadmap 2026-09-21 per explicit user instruction — "mark everything as a DEFINITE to-do," not optional/maybe):** the user has prior experience with each and wants them added to this project eventually, with this project's own validation standard applied from scratch:
- **LSTM price forecasting** (item 11) — multi-layer LSTM, engineered features (moving averages, RSI, volatility metrics), TensorFlow/Keras. A separate modeling track from the already-rejected ML Experiment 1's feature-based approach — needs its own data/feature pipeline scoping before any model work starts.
- **Options Greeks sensitivity / Monte Carlo pricing** (items 1, 5, 12) — Delta/Gamma/Theta/Vega/Rho sensitivity analysis, automated Black-Scholes calculators, Monte Carlo simulation of volatility effects on pricing, real-vs-theoretical deviation visualization. Lowest-lift of the three — can reuse existing `options_pricing.py` and the validated EODHD Greeks/IV data already confirmed this session (Section 8's "EODHD data-capability audits").
- **Optiver-style RL + statistical-arbitrage execution** (items 7, 9, 10, 13) — reinforcement learning + stat-arb for order-execution optimization, tick-level inefficiency detection, XGBoost/DNN closing-price prediction, Monte Carlo backtesting. Most novel and most constrained by this project's EOD-only data (item 9) — will need a genuinely adapted scope, not a literal port of a tick-level competition approach.

**Important, per this project's own Section 1 philosophy — explicitly flagged when these were queued:** the prior-project metrics associated with these three (a claimed 20% RMSE improvement over ARIMA; a claimed 12% drawdown reduction) came from different data, different market conditions, and an unknown/likely looser validation standard. **They are not evidence for this project and must not be cited as an expectation here** — each track starts from zero and must earn its own result against this project's own data and validation standard (ideally through the same gates/verdict framework that formally rejected ML Experiment 1). Priority order between the three tracks has not yet been decided.

---

## 7. Open issues, in priority order

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Condensed to the items still open.** Resolved items (1, 2, 4, 5, 8e, 10) and their full investigation history are in the archive.
- **1b (optional):** spot-check 2-3 more combined-correction trades from tickers other than AAPL. Only 3 AAPL trades have been checked so far. (Item 1a, the same-day split, was done in Section 13.)
- **3:** rebuild `close_the_loop_real_spreads.py` with the id-date check before trusting -$27,307.36.
- **6 / 7 (superseded):** hypothesis and ML-method selection have since happened (Sections 32, 33, 39, 42, 43, 44-51, 60).
- **8a:** `options_confluence_modifier.py`'s gamma size modifier is computed but never applied in `live_options_trader.py` (`contracts` is not reassigned between lines 299 and 317). Silent no-op. Deferred by user instruction.
- **8b:** V1's options backtest never simulated `risk_manager.py`'s controls (max 3 positions / 3% daily loss / 8% drawdown). See Sections 16 and 27.
- **8c:** the live options path has no trailing stop and no ATR-based stop/target; `options_trailing_stop.py` and `dynamic_options_thresholds.py` are backtest-only.
- **8d:** `spy_gamma_daytrader.py` trades paper capital on an unvalidated gamma chain (hardcoded vol 0.30, live Alpaca chains, cannot be backtested). See Sections 34-36.
- **9 (low-urgency cleanup batch):** uncached bar fetches in `options_evaluator.py` and `main.py`; `data_layer_iv_helper.py` duplicates `v2_iv_pricing_model.py`; 7 separate Anthropic clients; ~30 inline EODHD fetches; `find_gamma_walls()` name collision; `test_run_experiment.py` writes fixtures into production `research_database.db`; `overnight_hold_check.py` has no earnings data.
- **Item 4 (prospective GEX pipeline), resolution only:** the timezone bug in `daily_collection_run.py` was fixed 2026-09-20 (`America/New_York`). The stale GEX cache was fixed by `gex_historical_incremental_update.py` (Section 40). The pipeline now has no consumer (Section 32).

---

## 8. Architecture map: data ingestion layer (Alpaca + EODHD)

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Architecture: data ingestion (Phase 1 audit, 2026-09-20).**
- **Alpaca:**
  - Canonical bars: `backtest_engine.get_historical_bars()` (5-min IEX, in-memory cache, 78 call sites). Uncached duplicate fetches exist in `options_evaluator.py` and `main.py`.
  - Live options chain: `options_data.get_options_chain()` (13 files).
  - Live quotes: `options_evaluator.get_live_premium()` (ask) and `get_live_bid_price()` (bid).
  - Live delta selection: `pick_contract_by_delta.py` (used only by `live_options_trader.py`).
  - Every `TradingClient` hardcodes `paper=True`.
  - `daily_price_audit.py` reconciles `options_trades.db` against real Alpaca fills (`trade_id` = `opt-live-{ticker}-{order_id}`).
- **EODHD:**
  - `gex_data_loader.py` is the mature ingestion module: JSON:API pagination with token re-append, `UNIQUE(ticker, snapshot_date, contract)`, and `get_real_trading_days()`. It writes `gex_data_cache.db` (~646MB).
  - Two independent safe-T-1-IV implementations exist: `data_layer_iv_helper.py` (feeds only the rejected ML Experiment 1) and `v2_iv_pricing_model.py` (the live correction chain).
  - `daily_collection_run.py` runs via the `GEX_Prospective_Daily_Collection` task.

---

## 9. Architecture map: calculator layer (GEX / gamma / charm / IV / Greeks)

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Architecture: calculator layer (Phase 2 audit, 2026-09-20). There are two disconnected GEX systems.**
- **System 1** (EODHD, research-only, lookahead-safe): `gex_calculator.py` computes Net GEX (`model_a` / `flipped`), the gamma flip by Method A (`cumulative_strike_transition`, unstable) and Method B (`true_zero_gamma`, a ±20% repricing sweep), walls, and gradient. It writes `gex_metrics`, which `gex_lookup.py` reads (T-1 only, executable assert, exposes only Method B; `is_regime_testable=True`). Consumers are research-only (`run_phase2_full_scale.py`, `prospective_gex_pipeline.py`, `regime_sensitivity_analysis.py`, `phase3/phase4*` scripts).
- **System 2** (live Alpaca, hardcoded `volatility=0.30`, unvalidated): `gamma_landscape.py`, `gamma_regime.py`, `charm_landscape.py`, `gamma_gradient.py`, `daily_levels.py`. These drive `spy_gamma_daytrader.py`'s entry (via `spy_gamma_shadow_loop.py` and `spy_gamma_execution.py`) and the no-op size modifier (Section 7, item 8a).
- **Shared Greeks:** one implementation, `options_pricing.py`. Call sites differ only in the volatility input.
- **Name collision:** `find_gamma_walls()` exists in both `gex_calculator.py` and `gamma_landscape.py`, with different signatures.

---

## 10. Architecture map: external integrations (cross-cutting)

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Architecture: external integrations (2026-09-20).** `.env` holds `ALPACA_*`, `EODHD_API_TOKEN`, `MASSIVE_API_KEY`, `ANTHROPIC_API_KEY`, `KILL_SERVER_TOKEN`, and `TRADING_LOOP`.
- **Alpaca:** 21 files, live and research.
- **EODHD:** 41 files, research only (zero live overlap); ~30 do inline fetches.
- **Anthropic:** 7 separate clients (`ai_analyst.py` on claude-opus-4-5; `lessons_learned.py`, `spy_gamma_lessons_learned.py`, `account_review.py`, `trade_reviewer.py`, `review_open_position.py`, `pattern_review.py` on claude-sonnet-5). Used for narrative only and never affects a trading decision. The only machine-parsed output is `ai_analyst.diagnose_and_suggest()`, consumed only by `optimizer.py` (which has no Alpaca code).
- **Massive** (Polygon-compatible minute-bar option data): `contract_price_extremes.py`, called from `options_exit_monitor.py` for post-hoc review enrichment only. `implement_hybrid_volatility.py` is a red herring; it doesn't use Massive.
- **`TRADING_LOOP`:** only toggles `main.py`'s loop mode.

---

## 11. Architecture map: pricing, selection, and execution logic

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Architecture: pricing, selection, execution (Phase 3 audit, 2026-09-20).**
- **Headline findings:**
  - V1's options backtest never simulated `risk_manager.py`'s three account controls (see Section 27).
  - The live options path uses a static 0.40 / 0.75 bracket plus `reversal_detector.py`, with no trailing stop or ATR logic.
  - `OPTIONS_SHADOW_MODE=False`: real paper orders.
  - `SPY_GAMMA_SHADOW_MODE=True`: genuinely shadow.
  - Deployment is via NSSM Windows services (Section 26); the Replit deployment was cancelled.
- **Live-wired modules:**
  - `entry_scorer.py` (31 files).
  - `reversal_detector.py`, used by `options_exit_monitor.py`.
  - `ticker_circuit_breaker.py`, used by both options paths.
- **Backtest-only modules:** `delta_strike_finder.py`, `time_decay_exit.py`, `options_trailing_stop.py`, `dynamic_options_thresholds.py`.
- **Position sizing:** `risk_manager.calculate_position_size()` serves stock only. Options and SPY each use their own inline formula.
- **Exits:**
  - `exit_tracker.py` is stock-only (`live-` trade IDs).
  - `options_exit_monitor.py` checks: stop_loss, reversal_guard, take_profit, expiry_safety_net, overnight_risk.
  - `spy_gamma_execution.py` selects by highest open interest (not delta), uses 4 tranches (20/40/75% + RUNNER), and force-closes at 15:45 ET.
- **Backtest structure:** `portfolio_backtest.py` reimplements the event loop and reuses only three helpers from `options_backtest_engine.py`: `calculate_historical_volatility`, `black_scholes_price`, and `_estimated_spread_cost_pct`.

---

## 12. Architecture map: remaining infrastructure, research framework, and audit closure (Phase 4)

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Architecture: remaining infrastructure and research framework (Phase 4 audit, 2026-09-20).**
- **Live import closure (two additions found):**
  - `feature_extraction.py` + `baseline_model.joblib` (a 13-feature logistic regression, separate from ML Experiment 1). Shadow-logging only, to `ml_shadow_predictions.db`; it gates decisions only in backtest-only `time_decay_exit.py`.
  - `forward_test_logger.py`, called hourly by `main.py`; writes `gamma_forward_test.db`.
- **Kill switches:** `options_kill_server.py` (port 8081) and `kill_server.py` (port 8080) share the `STOP_TRADING` file.
- **Known limitation:** `overnight_hold_check.py` has no earnings-calendar data.
- **Research framework:** `experiment_config.py`, `gates.py`, `verdict.py`, `multiple_testing.py` (Bonferroni; Benjamini-Hochberg raises), `robustness.py`, `run_experiment.py`, `canonical_hash.py`, `db_interface.py`. `research_database.db` has 8 rows: 1 real framework verdict (ML Experiment 1, REJECTED), 3 backfilled (Phase 6/7, IV repricing), and 4 test fixtures.
- **Inert scripts:** none of the `fix_*`/`patch_*`/`check_*`/`diagnose_*`/`verify_*`/`audit_*`/`investigate_*` scripts is ever imported.

---

## 13. Root-cause synthesis: does V1 have genuine, repeatable edge? (2026-09-21)

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**V1 verdict (2026-09-21): no genuine edge, for two independent and compounding reasons.**
1. **Genuine signal failure:** Phase 6 gives p=0.996; 97.7% of P&L came from 5 trades.
2. **Destroyed by pricing/execution:** the IV-only correction gives -$10,072.44. Even the multi-day trades in the full correction lose: -$26,467.00 over 177 trades, 33.3% win rate, -$149.53/trade.

The same-day trades (71; -$19,010.00 at 0% win) are a data-limited artifact: entry and exit come from the same EOD snapshot. This finding is about V1 as defined, not about other signal constructions.

---

## 14. Source-of-truth hierarchy

When sources disagree, this is the precedence order, highest first:

1. **Actual current code** — what the file on disk does right now, read directly.
2. **Actual database contents/schema** — queried directly, not remembered.
3. **Executed experiment outputs/artifacts** — a script's actual printed/saved output from an actual run.
4. **Research documentation/reports** — write-ups describing what was found (e.g. old onboarding prompts, docstrings claiming a result).
5. **This file (CLAUDE.md)/project notes.**
6. **Previous conversation/memory** — anything recalled without re-checking.
7. **Interpretation** — inference, synthesis, or judgment calls not directly backed by 1-4.

**Rule: if documentation (including this file) contradicts code, flag the contradiction — never assume the documentation is right.** This has already happened twice this session: a docstring claimed "-$1,874.37" when the database actually held "-$10,072.44" (Section 3), and `options_shadow_loop.py`'s own docstring claimed "no real orders" when the code had been submitting real paper orders for some time (Section 8, corrected). **If a result was generated by code that has since changed, treat that result as potentially stale and say so explicitly** rather than citing it as current — e.g. the frozen V1 number's *exact originating code path* has not been git-history-verified as unchanged since the number was first produced (open question, Section 28).

---

## 15. Frozen V1 — complete specification (canonical)

Single authoritative reference. Every parameter that can affect the frozen +$20,427.64/251-trade result, with exact file:line citation. V1 = `portfolio_backtest.py:run_portfolio_backtest()` called with `pricing_mode="v1"` — verified by reading the actual code path in full (not the differently-configurable `options_backtest_engine.py`, which V1 does not call for its signal/execution loop, only for two specific shared helper functions — see row "Pricing formula" and "Volatility, pricing" below).

| Parameter | Exact value | File:line |
|---|---|---|
| Ticker universe | AAPL, TSLA, NVDA, AMD, SMCI, MSTR | caller (`combined_iv_spread_correction_v2.py:55`) — not hardcoded in the engine itself |
| Data source | Alpaca, via `backtest_engine.get_historical_bars()` (Section 8: the canonical, cached, 78-call-site bar source) | `portfolio_backtest.py:137` |
| Bar frequency | 5-minute bars (IEX feed) | `backtest_engine.py` (Section 8) |
| Date range | 2026-06-11 to 2026-09-09 | caller |
| Regime definition | bullish if SPY daily close > 50-day daily MA, else bearish; "neutral" only as an insufficient-history fallback (<50 days) | `backtest_engine.py:348-379` |
| Regime lookback | 50 days | same |
| Regime cache/refresh | cached, refreshed every 5 calendar days (an explicit, documented fix — recomputing fresh every checkpoint caused a real trade-count discrepancy vs. the validated engine) | `portfolio_backtest.py:117-132` |
| Breakout lookback | 20 bars (call: close > max of prior 20 highs; put: close < min of prior 20 lows) | `backtest_engine.py:131-156`, called at `portfolio_backtest.py:218,220` |
| Entry score | `entry_scorer.py`'s live 7-factor 0-100 score — **confirmed the same scorer the live system uses**, not a separate V1-only mechanism | `entry_scorer.py:32-182`, called at `portfolio_backtest.py:225` |
| Score factors/weights | relative volume (0-25), breakout/breakdown magnitude (0-20), trend vs. 50-bar MA (0-20), momentum/ROC over 12 bars (0-15), volatility-regime percentile over 60-bar lookback (0-10), news sentiment binary (0-5), SPY regime alignment (0-5). Early-exit shortcut: if relvol+breakout <5, returns immediately without computing the rest. | `entry_scorer.py:32-154` (exact per-factor formulas live here — cited, not re-transcribed in this table; read the file directly for the literal arithmetic of any one factor) |
| Score threshold | 20 (`entry_score_threshold=20`, default) | `portfolio_backtest.py:107,226` |
| Direction logic | Engine supports dynamic per-ticker direction (call if daily regime bullish, put if bearish, call if neutral-fallback) via `fixed_direction=None`. **V1's calls-only convention is a caller choice** (`fixed_direction="call"`), not an engine constraint. | `portfolio_backtest.py:109,215` |
| Target DTE | 14 (`dte_target=14`, default) | `portfolio_backtest.py:107` |
| Warm-up (entry) | Effective floor = 20 bars, from the breakout lookback itself — no separate index gate. A prior `index>=60` gate was a real, confirmed bug (blocked ~60 bars of every backtest) and has been removed. | `portfolio_backtest.py:199-206` |
| Warm-up (exit, reversal-guard specifically) | `index >= 6` required before the reversal-guard's 5-bar-MA check can evaluate at all | `portfolio_backtest.py:170` |
| Entry timing | Evaluated and executed at the exact 5-min bar's **close** price, at the checkpoint where breakout+regime+score all pass — not next-bar-open, not intrabar | `portfolio_backtest.py:151-153,218-262` |
| Contract-selection algorithm | Delta-targeted search, scans strikes from -15%/+15% of spot in 0.5% steps, returns nearest to `target_delta` — NOT at-the-money, NOT a fixed % offset | `delta_strike_finder.py:17-52`, called at `portfolio_backtest.py:228` |
| Target delta | 0.30 (default) | `portfolio_backtest.py:107` |
| Volatility, strike selection | Computed ONCE per entry checkpoint via `calculate_historical_volatility()`, used directly as the delta-search input | `portfolio_backtest.py:227-228` |
| Volatility, pricing | **Confirmed identical to the strike-selection volatility for `pricing_mode="v1"`** — same single value, computed once, reused for both (`_pricing_vol = vol` at line 230, only overridden for the separate `v2_entry_iv`/`v2_corrected` modes, not V1). Underlying method: "hybrid" — 20-trading-day realized vol, recomputed daily, EWMA-smoothed day-to-day (λ=0.90). | `portfolio_backtest.py:227,230`; hybrid-vol method in `options_backtest_engine.py:50-139` |
| Pricing formula | Standard Black-Scholes (`options_pricing.py`), `risk_free_rate=0.04`, zero dividend term. Reused directly by `portfolio_backtest.py` via `from options_backtest_engine import ... black_scholes_price` — not reimplemented. | `options_pricing.py:7-33`; imported at `portfolio_backtest.py:54` |
| Spread adjustment | Tiered, applied symmetrically (half the % on each side): entry premium × (1 + spread%/2), exit premium × (1 − spread%/2). Tiers by premium: ≥$5→2%, ≥$2→4%, ≥$1→7%, <$1→12%. **Applied unconditionally — V1 is not frictionless theoretical pricing.** | `options_backtest_engine.py:12-26` (`_estimated_spread_cost_pct`); applied at `portfolio_backtest.py:194,258` |
| Position sizing formula | `contracts = max(int(starting_capital × position_risk_pct / (entry_premium × 100)), 1)`, `position_risk_pct=0.01` (1% of that ticker's own starting capital per trade) | `portfolio_backtest.py:107,260-261` |
| Capital assumptions | `starting_capital=100000.0` per `run_portfolio_backtest()` call. **As actually invoked for the frozen number, this is $100k PER TICKER (6 independent calls), not one shared $100k or $600k pool** — see Section 16 for the full consequence of this. | `portfolio_backtest.py:106`; invocation pattern at `combined_iv_spread_correction_v2.py:60-64` |
| Stop loss | 40% of option value lost (`stop_loss_pct=0.40`) | `portfolio_backtest.py:108,168-169` |
| Reversal guard | Hardcoded into V1's exit chain, not optional. Fires at ≥40% unrealized gain AND both of the last 2 closes are below (call) / above (put) the mean of the preceding 5 closes (bars `index-6` through `index-2`, i.e. excluding the current and immediately-prior bar). | `portfolio_backtest.py:170-177` (exact indices verified by direct read) |
| Take-profit | **Does not exist in V1 at all** — `run_portfolio_backtest()` has no `take_profit_pct` parameter. Without the specific reversal pattern firing, a ≥40%-gain position simply stays open (explicit, deliberate — see the file's own comment). | `portfolio_backtest.py:178-184` |
| Expiry handling | `exit_reason="expired"` if `days_left<=0` at any checkpoint — the third and last of exactly three exit reasons (stop_loss, reversal_guard, expired). | `portfolio_backtest.py:185-186` |
| Mark-to-market frequency | Every 5-min bar checkpoint, for that bar's own ticker's own open position (re-priced fresh via Black-Scholes using that bar's spot + the same-day vol). **Approximation in the engine, moot for V1's actual single-ticker-per-run invocation:** at a checkpoint belonging to a *different* ticker, any other open position is marked at its last known entry cost, not re-priced — this only matters if the engine is ever run with >1 ticker sharing one account, which the frozen number's invocation never did. | `portfolio_backtest.py:286-299` |
| Exit timing | Same granularity as entry — evaluated and executed at the bar's close, every 5-min checkpoint. | `portfolio_backtest.py:151-198` |
| Simultaneous-position restrictions | **At most one open position per ticker at a time** (`ticker_positions[ticker] is None` gates all new entries) — this is a hard rule in the engine itself, not specific to the single-ticker invocation. Across tickers, the engine's own only constraint is `PortfolioAccount.can_afford()` against shared cash — but for the actual frozen number, each ticker got its own fully independent account, so no cross-ticker competition for capital or position slots ever occurred (see Section 16). | `portfolio_backtest.py:148,207,67-68` |

---

## 16. Single-ticker runs vs. true portfolio — critical distinction

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**The frozen +$20,427.64 is NOT a portfolio return.** It is 6 independent single-ticker `run_portfolio_backtest([ticker])` calls with $100k each, implying $600k of notional capital. Cash and cross-ticker limits never bind.

A shared-$100k approximation (realized P&L at exit) gives zero 3%-daily-loss triggers and zero 8%-drawdown triggers. More than 3 positions were open concurrently on 88 of 90 days. That count is date-level and overcounted (max 13 > theoretical 6); a bar-level re-simulation is needed for an exact blocked-trade count. This limitation is inherited by every V1/V2 dollar figure.

---

## 17. V1 result reconciliation table (canonical — eliminates conflicting numbers)

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**The canonical V1 result numbers are now in Section 3 (condensed).** Rows that exist only in the archived table:
- `pricing_mode="v2_entry_iv"`: result **UNKNOWN**, never located. The design mixes vol inputs, so it's methodologically incomplete.
- Phase 6: SUGGESTIVE / backfilled.
- Phase 7: descriptive only.

The rule still applies: don't trust a V1 number that isn't in that table (read the archived table before citing).

---

## 18. Experiment status registry

**From 2026-10-02, new pre-registrations are graded in tiers** (Section 1, `tiered_v1`): REJECTED / HELD / VALIDATED_SMALL_SIZE_MONITOR / VALIDATED_FULL_CONFIDENCE. Rows below that were registered earlier keep the taxonomy they were graded under.

Status taxonomy: **VALIDATED** (formally tested, methodology sound, result trustworthy) / **SUGGESTIVE** (real signal in the data, methodology reasonable, not formally preregistered/gated) / **INCONCLUSIVE** (test ran, no clear answer either way) / **NOT TESTABLE** (insufficient data or a structural blocker) / **INVALIDATED** (a real methodology flaw was found, don't trust the result) / **DESCRIPTIVE ONLY** (forensic/attribution work, not a hypothesis test with a formal verdict).

| ID | Hypothesis | Dataset/range | Methodology | Primary metric | Result | Status | Reason | Affects frozen baseline? |
|---|---|---|---|---|---|---|---|---|
| **V1 (frozen baseline) genuine edge** | V1 as currently defined has real, repeatable predictive/economic edge | 251 trades, 2026-06-11 to 2026-09-09, all 6 tickers | Four-way evidence chain: Phase 6 raw-signal Monte Carlo test, Phase 7 concentration attribution, V2 IV-only real-BS repricing, same-day/multi-day P&L split on the combined real-execution correction | See Section 13 for full numbers | **NO** — no genuine edge demonstrated | **CLOSED: NO DEMONSTRATED EDGE** (2026-09-21, user-confirmed) | Two independent, compounding causes: genuine signal failure (Phase 6, p=0.996; corroborated by Phase 7's 97.7%-from-5-trades concentration) AND destruction by pricing-execution economics (V2 IV-only alone flips +$20,427.64 to -$10,072.44; the "real" multi-day trades in the full correction still average -$149.53/trade, -$26,467.00 total, 33.3% win rate). See Section 13 for the complete reasoning. | **Yes — this is the formal conclusion about the frozen baseline itself.** Per explicit user instruction: **V1's parameters will NOT be tuned in response to this finding** — doing so would violate this project's own no-post-hoc-tuning rule (Section 1). This is a closed, negative result to be preserved as-is (Section 19's spirit), not a bug to fix. Any future work responding to this is a *new* hypothesis (e.g. the three DEFINITE-future-work tracks in Section 6, or a new EODHD/GEX hypothesis, Section 7 item 6), never a retroactive edit to V1 itself. |
| `ml_experiment1_feature_factory_vs_baseline_20260917` | Feature Factory (11 engineered features) adds predictive value over baseline | Same trade population, ML pipeline | Full gates/verdict/multiple-testing/robustness framework, real preregistration | (framework-internal) | **REJECTED** (2 verdict rows, both REJECTED, legitimate rerun) | **VALIDATED-AS-REJECTED** — the only experiment that's gone through the complete formal pipeline; the rejection itself is the trustworthy, validated conclusion | REJECTED, robustness-tested | No — separate ML track, does not touch V1 |
| Phase 6 primary control | Raw V1 entry signal has standalone predictive edge | 579 signals, 60 days, 6 tickers | Monte Carlo, day-clustered, 2 seeds | Day-clustered mean 20-bar forward return | T_obs=-0.2569%, p=0.996/0.997 — no edge found | **SUGGESTIVE** | Rigorous, numerically reproduced exactly this session; but a backfilled DB row, not run through gates/verdict — self-labeled "does NOT constitute genuine preregistration" | No — diagnostic about the signal, doesn't modify V1 |
| GEX regime testability | Is GEX regime classification usable as a feature at all | 372 ticker-days (per `gex_lookup.py`'s current code comment) | Code-level regime-variation check | `is_regime_testable` flag | 331 positive / 41 negative — real variation found | **RESOLVED 2026-09-21, per Section 14's source-of-truth rule (code > prose).** `gex_lookup.py`'s current code hardcodes `is_regime_testable=True`. Section 5's old "NOT TESTABLE... zero variation" line was stale and has been corrected to match. **Still NOT VALIDATED as a predictive feature** — testable ≠ tested; no formal experiment has evaluated whether GEX regime actually predicts anything. | Was a genuine code-vs-doc contradiction; now reconciled | No |
| Call-wall-distance | Distance from nearest call gamma wall predicts forward underlying returns (near-wall suppressed) | Stage 1: 772 joined signals, 68 days, 2026-06-10 to 2026-09-21 | Pre-registered (config_hash `3f0e6b6523f66efa1469ba590d7b56750051defaf1fd474cc515981a55f0d6cf`), day-clustered median-split permutation test, 4 horizons, Bonferroni-corrected, 5 robustness checks | 20-bar primary: T_obs=-0.1747pp, p=0.77 | **REJECTED — CLOSED, no Stage 2** (Section 32) | Not significant, effect size below threshold, direction reversed from hypothesis, confirmed by leave-one-ticker-out (all 6 exclusions reversed). **Failure classification: genuine signal failure** — wrong direction throughout, a clean read. | No — separate GEX hypothesis, does not touch V1 |
| Net gamma regime | Negative T-1 net dealer gamma exposure predicts higher forward realized volatility (dealer-hedging amplification) | Stage 1: 252 joined (ticker,day) obs, 42 days (18 negative-regime), 2026-06-10 to 2026-08-11 | Pre-registered (config_hash `8dc7b1cd1b1b0f5e5590109106866d4039ef6d9d02f33163465b7cc892bc5f2e`), day-clustered categorical permutation test, 4 horizons, Bonferroni-corrected, 5 robustness checks, day-level population (not V1-gated, Section 42) | 20-bar primary: T_obs=+0.00079, ratio=1.167×, p=0.044/0.052 | **REJECTED — CLOSED, no Stage 2** (Section 42) | Not significant, effect ratio below 1.20× threshold, direction reversed under sign_convention:flipped (a near-mirror relabeling, not independent evidence). **Failure classification: primarily insufficient evidence, genuine signal failure equally plausible** — direction was correct everywhere tested, 50-bar horizon came within striking distance of the corrected bar (p=0.018), only 18 distinct negative-regime days available — a genuinely ambiguous result, not a clean rejection. | No — separate GEX hypothesis, does not touch V1 |
| 5-bar vs. 20-bar horizon | A 5-bar exploratory finding on signal timing | — | Out-of-sample replication attempt | Relative MSE reduction | -0.54% (did not replicate) | **INVALIDATED** | Did not hold OOS | No |
| Lookahead-bias check | Entry-score/breakout computation uses no future information | — | Direct code audit | Pass/fail | No lookahead found | **VALIDATED** | Directly checked, confirmed | Confirms V1's construction is sound on this specific axis |
| `iv_term_structure_slope_v2_20261001` (Section 33) — supersedes v1 `iv_term_structure_slope_v1_20260921` (hash `bfa05fe9…`; Stage 1 carried over, registry `status=SUPERSEDED`) | Steeper (contango) IV term-structure slope predicts LOWER 20-day forward realized vol | 6 tickers. Stage 1: 2026-01-15..06-10. Stage 2: rolling from 2026-09-10 | Pre-registered, day-clustered Monte Carlo correlation, 3 horizons; **v2 registered 2026-10-01** (hash `14261999…`) | 20-day correlation; α = 0.0167 one-sided; \|r\| ≥ 0.15 | Stage 1: r = −0.28 (p = 0.001–0.002), 4 of 5 robustness checks clean, 1 ambiguous | **SUGGESTIVE** (Stage 2 pending, N = 0) | Stage 1 threshold `min_n_per_stage` = 100 (passed); Stage 2 threshold `min_n_stage2` = **139** distinct pooled days (v2; was 100). Locked test runs once, at the earliest the night of **2027-06-10**; earlier looks are exploratory only. Framework α **fixed 2026-10-01** (`multiple_testing.py`, commit `11a2c8b`): it now returns 0.0167 automatically. | No |
| `spy_gex_callwall_volatility_v3_20261001` (Section 43) — supersedes v2 `spy_gex_callwall_volatility_v2_20261001` (hash `ce0c2c0c…`) and v1 `spy_gex_callwall_volatility_v1_20260924` (hash `c2629dc1…`); neither ever run, both registry `status=SUPERSEDED` | SIGNED SPY call-wall distance is negatively correlated with forward realized vol, **beyond the general volatility level** | SPY only, rolling from 2026-06-10 (window bug fixed 2026-10-01) | Pre-registered, day-clustered correlation + permutation, 3 horizons, plus a mandatory **volatility_control_gate** (partial correlation controlling for SPY trailing 20d realized vol at T-1); **v3 registered 2026-10-01** (hash `afdf29dc…`) | 20-day correlation; α = 0.0167 one-sided; \|r\| ≥ 0.15; partial r negative and significant | Not run. N = 59 of 139 as of 2026-10-01 | **NOT YET RUN** (waiting for N ≥ 139) | v3 raised N 100 → 139 for power (80% at r = 0.25). Expected to reach N ≥ 139 on the night of **2027-01-27**; lock and run once. Framework α **fixed 2026-10-01** (`multiple_testing.py`, commit `11a2c8b`): it now returns 0.0167 automatically. | No |
| Cross-sectional straddle, Goyal–Saretto HV − IV gap (Section 62; trial #12; never pre-registered) | Long straddles on the highest HV − IV names and iron flies on the lowest earn a positive spread after costs | 59 tickers; DEV = 23 cycles, 2023-10 → 2025-09 (EODHD snapshots); BLIND unexamined | Phase 1 pipeline validation: straddle-basis spread at three cost levels, implementable book, delta-hedged variant, shuffled-rank placebo, two-way fixed effects, power | Per-cycle spread return (delta-hedged spread = planned primary) | Published sign but noise-level; delta-hedged −1.5% / −0.9%; MDE at 80% ≈ 10–13% per cycle vs plausible 0–3% | **INCONCLUSIVE — HELD / parked 2026-10-02** | Data limitation: underpowered on current data. ORATS ($599) declined; even with it the MDE is only ~1.5–4.4%. Not rejected. No further spend. | No |
| `vix_termstructure_vrp_index_timing_v1_20261002` (Section 63; trial #13) | ln(VIX3M/VIX) at the close before each monthly SPX roll positively predicts the next cycle's CNDR excess return, beyond the VIX level and the VRP proxy | Free Cboe daily CSVs + Treasury 4-week bill; 203 monthly cycles, 2009-10-15 → 2026-09-17 | Spearman + permutation, one horizon, mandatory vrp_control_gate, 13 sign-only checks (≤ 1 may fail; post-2014 must pass), OOS R² vs historical mean; Stage 2 informative only | Spearman ρ; α = 0.05 one-sided; ρ ≥ 0.15 | ρ = −0.020 (p 0.61); gate partial ρ +0.056 (p 0.21); 10/13 sign checks failed incl. post-2014 | **REJECTED — CLOSED** (2026-10-02, hash `188828a6…`) | Genuine signal failure, well powered (87% at ρ = 0.20). Always-on CNDR earned −1.1%/yr vs T-bills 2012–2026; timing didn't help. | No |

*(Registry is not exhaustive of every script in Section 5's file inventory — it covers the experiments with an actual test/verdict/status, not every audit or diagnostic. Expand as needed rather than treating this as closed.)*

---

## 19. Invalidated research registry (do not reuse these results or methodologies)

| What was done | Why it's invalid | What conclusion must NOT be drawn | Replaced by | Corrected methodology |
|---|---|---|---|---|
| `combined_iv_spread_correction.py` (naive combined correction, -$11,472.00/105 trades) | No id-date check; 17/105 "matched" trades actually used a wrong-day (future) quote — a lookahead-relevant forward-fill artifact | Do NOT cite -$11,472.00 as a real execution estimate | `combined_iv_spread_correction_v2.py` (-$45,477.00/248 trades) | Hard-filter every returned record on `id_date == obs_date`, never trust `tradetime` |
| The "-$1,874.37" IV-only-correction figure | Does not appear anywhere in `v1_v2_research_results.db`; the only saved run for this methodology produced -$10,072.44 | Do NOT cite -$1,874.37 as this project's IV-only correction number | -$10,072.44/237 trades (DB-verified) | N/A — provenance of the old number itself is unresolved (Section 28) |
| `close_the_loop_real_spreads.py` (-$27,307.36) | No id-date check (same vulnerability class as above), different/looser contract-matching convention | Do NOT treat -$27,307.36 as a trustworthy spread-only estimate | Not yet rebuilt | Needs the same id-date fix applied elsewhere before it's trustworthy |
| GEX gamma-flip "Method A" (`cumulative_strike_transition`) | Found unstable — Section 5/`gex_lookup.py` docstring: "22/30 ticker-days >50% from spot" | Do NOT use Method A as a gamma-flip feature | Method B (`true_zero_gamma`) — the standard industry methodology, recomputes real BS gamma at swept hypothetical spot prices | `gex_lookup.py` exposes only Method B |
| ML Experiment 1's Feature Factory (11 engineered features) | Formally REJECTED through the real gates/verdict/multiple-testing/robustness framework | Do NOT reuse these features as if they add value; do NOT reuse the rejection as evidence about any *other* feature set | N/A — closed | N/A |
| Options-live position-size modifier (`options_confluence_modifier.py` in `live_options_trader.py`) | Computed but never applied before order submission — a silent no-op (Section 9, still open, not yet fixed) | Do NOT assume live position sizing has ever actually reflected the gamma-based modifier, despite trade logs recording a `gamma_modifier` value | Not yet fixed — Tier-1 item, deliberately deferred | N/A |
| `options_shadow_loop.py`'s pre-2026-09-20 docstring/console claims ("places NO real orders") | Stale — `live_options_trader.py` had `OPTIONS_SHADOW_MODE=False` ("LIVE as of first supervised test") for some unknown period before this was caught | Do NOT trust any historical log/description that assumed this loop was shadow-only without checking the actual flag for the period in question | Docstring/console output corrected 2026-09-20 to read the live flag dynamically | N/A |
| Prospective GEX collection, 2026-09-14 through 2026-09-19 | Timezone bug (`daily_collection_run.py` computed "today" in UTC while the job fires at 20:00 ET, always landing one day ahead of the real trading day) — every run in this window silently found zero candidates despite real qualifying signals existing | Do NOT interpret the 2026-09-09-to-2026-09-19 gap in `prospective_gex_validation.db` as "no qualifying signals occurred" — they did, they were never checked | Fixed 2026-09-20 (`daily_collection_run.py` now uses `America/New_York` local date) | N/A |

---

## 20. Data lineage

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Data lineage, condensed.**
- **Affect live decisions:** only Alpaca bars and System-2 live gamma (SPY gamma bot).
- **Never affect decisions:** EODHD (pricing corrections, System-1 GEX, prospective GEX), Massive (post-hoc review), and Claude (narrative; plus `optimizer.py`, which is research-only).

---

## 21. Lookahead-bias audit

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Lookahead audit, condensed.**
- Entries and exits use bars only up to the current checkpoint (`check_lookahead_bias.py`: clean).
- V2/EODHD data uses the id-date rule (Section 4).
- GEX is T-1 only, enforced by an executable assert in `gex_lookup.py`.
- Forward returns are allowed only as retrospective labels or controls, never in signal or entry/exit logic.
- Every violation found was a data-identification bug (id-date, timezone), not deliberate future-data use.

---

## 22. Statistical methodology map

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Statistical conventions, condensed.**
- **Phase 6:** unit = signal occurrence; day-clustered Monte Carlo, 1000 replicates × seeds 42/43; one-sided empirical p.
- **Multiple testing:** Bonferroni via `multiple_testing.py`. ML Experiment 1's specific alpha is UNKNOWN.
- **Splits:** chronological, not random.
- **Not defined:** no project-wide minimum-N or ties/missing-data policy. Each experiment pins its own.

---

## 23. P&L accounting map

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**V1 P&L chain:** BS premium (hybrid vol) → tiered spread, half on each side → contracts → re-mark every 5-min bar → exit premium minus half the spread → P&L. No commissions, slippage, fees, or assignment/settlement are modeled anywhere in the V1→V2 chain.

---

## 24. Synthetic vs. real historical vs. paper/live execution — do not use "realistic" and "real" interchangeably

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Three distinct tiers of pricing realism:**
1. **Synthetic:** V1's BS pricing and tiered spread estimate.
2. **Historical observed:** EODHD end-of-day quotes. Real, but NOT proof of intraday fills; -$45,477.00 is an estimate, not a reconstruction.
3. **Paper:** real Alpaca paper fills.

Don't use "realistic" and "real" interchangeably.

---

## 25. Live/paper system vs. research system — explicit boundary

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Research/paper boundary:** no paper-trading data flows into research. The overlap is shared library code only: `entry_scorer.py`, `get_historical_bars()`, `options_pricing.py`, `risk_manager.py`. A change to any of these affects both sides.

---

## 26. Live paper system audit (complete, per-system)

**Critical distinction, spelled out precisely because it's exactly what caused the earlier confusion: "paper account" and "shadow mode" are two separate, independent layers.** `paper=True` on Alpaca's `TradingClient` means the *account itself* can never touch real money, regardless of anything else — confirmed absolute across every instantiation found (Section 8). A `SHADOW_MODE` flag is a separate, application-level decision about whether the code calls `submit_order()` at all, or just logs what it would have done. A system can be `paper=True` and still genuinely submit real (paper) orders — that's exactly what the options bot does and has been doing.

| | Stock bot | Options bot | SPY gamma bot |
|---|---|---|---|
| **Entry files** | `main.py`/`live_trader.py` | `options_shadow_loop.py`→`live_options_trader.py` | `spy_gamma_shadow_loop.py`→`spy_gamma_daytrader.py` |
| **Entry trigger** | Breakout+regime+entry_score (shared signal family, Section 25) — exact live threshold not independently re-diffed against V1's 20 this session | `entry_scorer.py` score (confirmed live-wired, 31 files, Section 11) — exact live threshold value not independently re-confirmed | Gamma/charm signal chain: negative net-gamma + price near gamma wall + steep gradient, optional charm/level confluence (System 2, hardcoded `volatility=0.30`, Section 9) |
| **Exit trigger** | Native Alpaca bracket order (`OrderClass.BRACKET`) — Alpaca manages it | 5 reasons in order: stop_loss, reversal_guard, take_profit, expiry_safety_net, overnight_risk (Section 11-12) | 4-way scale-out tranching (A/B/C at 20/40/75% take-profit + uncapped RUNNER via stricter ≥50%-gain reversal guard), force-close all at 15:45 ET |
| **Sizing** | `risk_manager.calculate_position_size()` (equity-risk-based share count) | Own inline formula (`max(int(max_risk_dollars/(premium×100)),1)`) — NOT the shared `risk_manager` function | Own separate inline flat formula (`equity×POSITION_RISK_PCT/(premium×100)`) — a third, independent implementation |
| **Risk controls** | `risk_manager`'s 3 checks (max positions/daily loss/drawdown) | Same 3 checks, plus `ticker_circuit_breaker.py` (3 consecutive losses, manual-clear) | Same 3 checks |
| **API** | Alpaca `TradingClient` + a separate uncached `StockHistoricalDataClient` call (Section 8 inconsistency) | Alpaca (`options_evaluator.py` quotes, `options_data.py` chains, `pick_contract_by_delta.py` selection) | Alpaca (`options_data.py`'s basic chain filter + highest-OI pick — NOT delta-targeted, unlike the options bot) |
| **Account/paper status** | `paper=True` hardcoded, confirmed absolute | `paper=True` hardcoded, confirmed absolute | `paper=True` hardcoded, confirmed absolute |
| **Shadow-mode flag** | N/A (no separate flag found — always submits real bracket orders to the paper account) | `OPTIONS_SHADOW_MODE=False` — **submits real (paper) orders**, has for some unknown period before this was caught. Docstring/console output corrected 2026-09-20 to reflect this dynamically. | `SPY_GAMMA_SHADOW_MODE=True` — **verified current and accurate**, genuinely returns early before `submit_order()` on both entry and exit |
| **Deployment mechanism** | **Local Windows Service only** (NSSM, below). The `.replit` `[deployment]` block (cloud VM) was a second deployment, but **the user confirmed on 2026-09-21 that it is cancelled and no longer running** (Section 28, closed). *(Corrected 2026-10-01: this cell previously said "Two found, unreconciled … unresolved", which Section 28 had already superseded.)* | Local Windows Service only — not in `.replit`'s config | Local Windows Service only — not in `.replit`'s config |
| **Process startup mechanism — RESOLVED this session, was the explicit open question** | **NSSM-wrapped Windows Service** `StockTradingBot`, `StartMode=Auto` (boot-persistent), `Application=python.exe`, `AppParameters=main.py`, confirmed via direct registry query (`HKLM:\SYSTEM\CurrentControlSet\Services\StockTradingBot\Parameters`) | **NSSM-wrapped Windows Service** `OptionsShadowLoop`, `StartMode=Auto`, `AppParameters=options_shadow_loop.py`, same verification method | **NSSM-wrapped Windows Service** `SpyGammaLoop`, `StartMode=Auto`, `AppParameters=spy_gamma_shadow_loop.py`, same verification method |
| **Logging** | `trade_log.py` (includes a process-review layer: `outcome_class`, `root_cause`, `was_process_correct` — Section 12) | `options_trade_log.py` (`gamma_modifier`/`gamma_context` fields) | **Not independently confirmed this session** — UNKNOWN which DB/schema this system's own trades are logged to, distinct from `gamma_forward_test.db` (which is the *stock* bot's passive gamma-modifier snapshot log, Section 12, not this system's trade log) |
| **Failure behavior** | Not independently characterized this session (e.g. behavior on an unhandled mid-loop exception) — UNKNOWN | Confirmed resilient: `options_shadow_loop.py`'s loop wraps each sub-step (pattern review, daily audit, account review, exit-check) in its own try/except, printing an error and continuing rather than crashing the whole loop | Not independently characterized this session — UNKNOWN |
| **Kill switch** | `kill_server.py`, port 8080, gated by `KILL_SERVER_TOKEN`, writes/reads the shared `STOP_TRADING` file | `options_kill_server.py`, port 8081, same shared `STOP_TRADING` file — its status page was already dynamically accurate about shadow-vs-live mode (positive finding, Section 12) | **ADDED 2026-09-21 — the flagged gap was real (confirmed: this loop never checked `STOP_TRADING` at all before this fix).** New `spy_gamma_kill_server.py`, port 8099 (confirms the previously-"unexplained" `.replit` port's purpose), modeled directly on `options_kill_server.py`, same shared `STOP_TRADING` file. `spy_gamma_shadow_loop.py` updated to call `spy_gamma_kill_server.start()` and check `STOP_FILE.exists()` every cycle, matching `options_shadow_loop.py`'s exact pattern. Both files compile cleanly. **Not yet live** — the running `SpyGammaLoop` Windows Service has the old code loaded in memory; this takes effect only after the service is restarted (not done automatically — a live, if paper-only, service restart needs explicit go-ahead). |
| **Can it ever reach a live account?** | No — `paper=True` hardcoded and confirmed absolute | No — same | No — same |

### Bots' purpose and operations (condensed 2026-10-05, pass 3; full history archived)

- **Purpose (user decision 2026-10-01):** StockTradingBot and OptionsShadowLoop keep running (not paused) as an **execution-cost measurement instrument**, not to validate V1. Design: `execution_cost_measurement_design_v1.md`. Options only; the stock bot is out of scope.
- **Primary cost source: EODHD end-of-day spreads.** `execution_cost_eod.py` → `execution_cost_log.db:eod_spreads`, task `ExecutionCost_EOD_Spreads` (21:05 ET). Zero extra EODHD calls: it reads the chains the GEX task already stores. Panel: 6 tickers + SPY; near (7–16 DTE) and far (30–45 DTE); ATM and ~0.30-delta; calls and puts.
- **Secondary: the Alpaca intraday sampler** (`execution_cost_logger.py`, once per 60 s cycle from `options_shadow_loop.py`, no orders). The account has only Alpaca's **indicative** options feed (OPRA not signed), so its spreads are not real market cost; it serves only to estimate the time-of-day shape. Stream A (fill-log hooks in the order code) was not built.
- **Median full spread** (% of mid, 2026-06-10..09-29, ATM / 0.30-delta):
  - far: SPY 0.6/0.7, TSLA 2.2/2.7, NVDA 2.8/3.9, AAPL 5.8/9.3, AMD 7.1/12.3, MSTR 10.2/16.2, SMCI 11.9/20.4.
  - near: SPY 0.8/1.2, TSLA 2.2/2.8, NVDA 3.4/3.4, MSTR 5.5/8.4, SMCI 6.0/8.5, AMD 6.8/10.4, AAPL 8.3/12.1.
  - Day-to-day noise is large, so use medians. Backtest convention: base = EODHD median by ticker/bucket/role, sensitivity 0.5× (patient limits) and 1.5× (open / market orders). End-of-day quotes can't measure open or intraday costs.
- **Restart-churn fix (2026-10-01):** at 16:05 ET the bots now idle until the next ET day instead of exiting (1 NSSM restart per evening instead of ~450), and `main.py` retries `get_account()` at startup (waits 5/10/20/40/60 s) before exiting with code 1.
- **PENDING (user, admin shell):** NSSM stdout/stderr capture: `nssm set <svc> AppStdout|AppStderr <project>\service_logs\<svc>_stdout.log|_stderr.log` for both services, then restart them outside market hours.

---

## 27. Risk-control disconnect — a research question, not a code change

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Risk-control disconnect (open research question, V1 unchanged):** `risk_manager.py`'s three checks are absent from the options backtest. Max-3-positions would likely have blocked many V1 trades (date-level estimate). 3% daily loss and 8% drawdown: zero triggers (realized-P&L approximation). Candidate follow-up: a bar-level re-simulation.

---

## 28. Master open-questions registry

**Methodological**
| Question | Why it matters | Evidence so far | What would answer it | Priority | Requires changing V1? |
|---|---|---|---|---|---|
| Is `portfolio_backtest.py`'s current code the exact original source of the frozen $20,427.64/251-trade number, or has it changed since that number was first frozen? | If the code has changed, the "frozen" number may not be reproducible by the code that currently claims to reproduce it | This session's rerun DOES reproduce $20,427.64/251 exactly, every time — strong practical evidence the current code is at least *consistent* | ~~A git-history check of `portfolio_backtest.py`~~ **ANSWERED 2026-10-01: git cannot verify it.** The repo's last commit before 2026-10-01 is `d950e2e` (2026-08-12). `portfolio_backtest.py`, `options_backtest_engine.py`, `entry_scorer.py`, `delta_strike_finder.py` and `options_pricing.py` are in **no** commit before `3d1b45c` (2026-10-01). `backtest_engine.py` gained V1's `get_daily_regime()`/`check_breakdown()` after 2026-08-12 (+121/−14 lines, ignoring line endings). The frozen number came from code that was never committed; exact reproduction by today's code remains the only evidence. Git guards this from now on. | Closed | No |
| Bonferroni alpha used in ML Experiment 1's formal run | Needed to fully audit that experiment's statistical rigor | Framework confirmed to implement real Bonferroni correction (Section 22); specific alpha value not extracted | Read `experiment_config.py`'s actual stored config for that run | Low | No |

**Data**
| Question | Why it matters | Evidence so far | What would answer it | Priority | Requires changing V1? |
|---|---|---|---|---|---|
| `volatility_forward_test.db` and `iv_correction_diagnostic.db`'s exact roles | Two DBs confirmed to exist, never read | File listing only | Read the schema/contents directly | Low | No |
| The `pricing_mode="v2_entry_iv"` mode — was it ever actually run, and if so what number did it produce? | Section 17's reconciliation table has a genuine gap here | Only the code definition confirmed, no executed output found | Search more thoroughly for saved output, or rerun it deliberately | Low-Medium | No |

**Implementation**
| Question | Why it matters | Evidence so far | What would answer it | Priority | Requires changing V1? |
|---|---|---|---|---|---|
| ~~Is the stock bot deployed in two places at once~~ — **CLOSED 2026-09-21.** Git history (same-day investigation) established a Replit deployment was genuinely published around 2026-08-12 then went completely git-silent for 5+ weeks. **User then checked the Replit dashboard directly and confirmed that deployment has been cancelled — it is no longer running.** The dual-deployment risk is fully resolved: only the local Windows Service (`StockTradingBot`, NSSM) is live now. No further action needed. | Git history evidence + direct user confirmation from the Replit dashboard | Answered | Resolved | No |
| ~~Does the SPY gamma bot have its own kill switch at all?~~ | If not, the only way to stop it may be stopping the whole Windows Service | **FIXED 2026-09-21** — `spy_gamma_kill_server.py` added (port 8099), `spy_gamma_shadow_loop.py` now checks `STOP_TRADING` every cycle (Section 26). Code-complete, compiles clean, but not yet live in the running service (needs a restart — not done without explicit approval) | Restart the `SpyGammaLoop` service and confirm `:8099/status?token=...` responds | Low (fix written, awaiting deploy) | No |
| Stock bot and SPY gamma bot's failure behavior on an unhandled exception | Determines whether a bug silently kills live trading with no alert, or degrades gracefully like the options loop does | Options bot confirmed resilient (try/except per sub-step); other two not characterized | Read the full loop bodies of `main.py`'s loop and `spy_gamma_shadow_loop.py` | Medium | No |
| Live entry-score threshold — does the live options/stock path actually use 20 (V1's default), or a different value? | If it diverged from V1's threshold, the live system is no longer testing the same signal V1 was frozen with | Not independently re-diffed this session | Read the actual call sites' passed threshold argument (or confirm the default is used) | Medium | No |

**Statistical**
| Question | Why it matters | Evidence so far | What would answer it | Priority | Requires changing V1? |
|---|---|---|---|---|---|
| Minimum sample size policy, treatment of ties/missing observations, general seed-handling convention | Needed for a complete statistical methodology audit | No project-wide policy found documented anywhere; only specific instances confirmed (Section 22) | Would need to check each experiment script individually — no single canonical source found | Low | No |

**Operational**
| Question | Why it matters | Evidence so far | What would answer it | Priority | Requires changing V1? |
|---|---|---|---|---|---|
| How are the NSSM services actually installed/managed (a setup script? manual `nssm install` commands run once?) | Understanding whether redeploying this project elsewhere would require manually recreating these 3 services | Confirmed they exist and are configured correctly; not confirmed how they got that way | Ask the user, or search for an nssm-install script (none found by name this session) | Low | No |

**Research**
| Question | Why it matters | Evidence so far | What would answer it | Priority | Requires changing V1? |
|---|---|---|---|---|---|
| Does the exit structure (asymmetric stop_loss vs. reversal_guard) survive realistic historical IV, shared-capital constraints, and execution costs simultaneously? | This is the actual next research question (Section 30) | Phase 7's individual attributions exist; nothing yet combines all three stress-tests at once | Phase 7 Analyses 4/8/9 (pending, Section 13/30) | High | No — diagnostic only |
| Precise (bar-level, not date-level) count of how many V1 trades the max-3-positions rule would have blocked | Section 16/27's current figure has a known overcounting artifact | Directionally strong (88/90 days affected) but not exact | A proper bar-level re-simulation | Medium | No |
| Which EODHD hypothesis and which ML method to pursue next | Explicitly deferred by the user (Section 7 items 6-7) | Options laid out, none chosen | User decision | Awaiting user | No |

---

## 29. Phase 7 interpretation — what's known vs. not yet proven

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Phase 7 — known vs. not proven.**
- **Known:** the exit-reason win-rate split is near-definitional, 97.7% concentration, Phase 6 shows no edge, and the IV correction flips the sign.
- **NOT proven:** that convexity or asymmetric exits caused V1's synthetic profit, that the exit structure holds out-of-sample or survives all frictions jointly, or that the top 5 trades are repeatable.

Treat "convexity + asymmetric exits" as a hypothesis.

---

## 30. Research decision tree

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Decision tree:**
- V1 fails realistic pricing (IV-only) and realistic execution (combined correction).
- Shared-capital and walk-forward/out-of-sample testing were never completed.
- Don't layer new features, GEX, or ML onto this mechanism.

---

## 31. Canonical documentation — why CLAUDE.md stays the single source

The user's own instruction (item 18) is to build a permanent onboarding document and explicitly **not duplicate conflicting information across many documents if one canonical source can be maintained.** CLAUDE.md already is that document — its own header states it's "the persistent memory for this research project," read at the start of every session. Creating a separate `RESEARCH_CONTEXT.md` alongside it would immediately violate the no-duplication instruction (two files claiming to be canonical, guaranteed to drift). *(2026-10-01: `CLAUDE_ARCHIVE.md` doesn't break the single-source rule. It holds closed sections verbatim and never duplicates them, and each archived section leaves only a stub here, so no content lives in both files.)* **Decision: everything requested in this pass (Sections 14-30) lives in CLAUDE.md, not a new file.** The one exception already noted in CLAUDE.md's own header: a parallel copy exists in the claude.ai project (`research-manifest.md`) for cloud-session continuity, not automatically synced — if this pass's additions are significant (they are), that parallel copy should be updated too, by the user or in a future session, per CLAUDE.md's own existing instructions.

---

## 32. GEX call-wall-distance — CLOSED: REJECTED at Stage 1 (2026-09-22)

*(Archived 2026-10-01, pass 1. The full text is verbatim in `CLAUDE_ARCHIVE.md`. **This stub is a locator, not a substitute:** read the archived section before citing anything from it.)*

**GEX call-wall-distance — CLOSED, REJECTED at Stage 1 (2026-09-22).** Final hash `3f0e6b65...`. N=772, 20-bar primary T_obs=-0.1747pp, p=0.77, direction reversed (incl. all 6 leave-one-ticker-out). Classification: genuine signal failure. Still-live operational facts: `GEX_Prospective_Daily_Collection` was found re-enabled 2026-09-26 (origin unknown) and the user decided to leave it running as free optionality with no current consumer; `gex_calculator.py:find_gamma_walls()` ignores `sign_convention`, so that robustness check is a no-op for any wall-strike feature.

---

## 33. Second parallel experiment: IV term-structure slope — pre-registration drafted (2026-09-21, NOT YET SUBMITTED)

*(Condensed 2026-10-05, archive pass 3. The full prior text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number (Pass 3). **This is a current-state summary, not a substitute:** read the archived text before citing any detail not repeated here.)*

**Current experiment: `iv_term_structure_slope_v2_20261001`**, hash `1426199993aea7e934c8c15be8e0d8eb4cea7437fe8b6ea170c2afb784509647`, file `preregister_iv_termstructure_v2_experiment.py`, `state=PREREGISTERED` (registered 2026-10-01T21:15:38Z). It supersedes v1 `iv_term_structure_slope_v1_20260921` (hash `bfa05fe93667de8d199cb2d9034a3bab51d307c4f546be7dac62f860ebf43bcc`, `status=SUPERSEDED`). It is graded under its own locked legacy rules, **not** `tiered_v1` (user decision 2026-10-05).

- **Hypothesis:** a steeper (contango) IV term-structure slope predicts LOWER 20-day forward realized vol. 6 tickers.
- **Construction (pinned):** near = soonest expiration in 7–16 DTE; far = latest in 30–45 DTE; matched strike = `sorted(common)[len(common)//2]`; realized vol = annualized stdev of daily log returns (adjusted closes). The id-date rule applies throughout.
- **Test:** `monte_carlo_day_clustered_one_sided`, 1000 replicates, seeds [42, 43]; horizons 10/20/50 days, primary 20; α = 0.05/3 = 0.0167 one-sided (the framework returns 0.0167 since commit `11a2c8b`); |r| ≥ 0.15; all 5 robustness checks in the same direction.
- **Stage 1 (2026-01-15..06-10, run 2026-09-21/22): SUGGESTIVE.** 536 rows / 101 distinct days. 20-day r = −0.2820 (p = 0.0020/0.0010); 10-day r = −0.4532 (p 0.0000); 50-day r = −0.0934 (p 0.164/0.173).
  - Clear robustness passes: leave-one-ticker-out (all 6 negative, −0.19 to −0.37), the 10-day horizon, far bucket 31–60 DTE (r −0.2884), nearest-strike fallback (r −0.3096; needed for 4 of 540 observations).
  - **50-day horizon: AMBIGUOUS.** Right sign but not significant, and the rule never said whether sign alone counts. Recorded as unresolved.
- **Stage 2 (rolling from 2026-09-10) is the locked confirmatory test.**
  - N = distinct trading days with at least one valid slope-computable observation, pooled across tickers. `min_n_stage2 = 139`; Stage 1 stays governed by `min_n_per_stage = 100`.
  - It runs ONCE, on the night N first reaches 139: **at the earliest the night of 2027-06-10** (observation #139 = 2027-03-31; every observation needs 50 forward sessions). Later if a day yields nothing.
  - **First possible row: the night of 2026-11-19.** As of 2026-10-05 it has 0 rows and 0 days, as expected.
  - Earlier looks are EXPLORATORY ONLY: no formal test, no verdict, not reported as a result, labeled "EXPLORATORY — NOT THE PRE-REGISTERED TEST".
  - Power at N = 139 (α 0.0167): 35.7% at r = 0.15, 59.3% at 0.20, 80.2% at 0.25, 89.0% at 0.28; MDE 0.249. A REJECTED would mean "no effect ≥ ~0.25", not "no effect".
- **Collector:** `generate_iv_termstructure_stage2_dataset.py` → `iv_termstructure_stage2_dataset.db`, task `IVTermStructure_Stage2_Nightly_Update` (20:45 ET).
  - Incomplete-day bars are dropped (`latest_usable_day()`, 2026-10-01). Early-close days conservatively wait until 16:00.
  - A failed Alpaca daily-bar fetch skips that ticker and ends `=== RUN INCOMPLETE (NETWORK)` instead of crashing (2026-10-05, commit `76851ba`).
  - No N-based stop; the lock is applied at analysis time.
- **Economic sanity check (2026-10-01; exploratory, not a verdict; `iv_stage1_economic_sanity_check_report.md`):**
  - A straddle pays RV − IV. The slope's correlation with the straddle payoff is only −0.07/−0.10 (vs −0.25/−0.30 with RV). Its partial correlation with RV20, given far IV and trailing RV, is +0.09.
  - The slope-quintile trade nets −1.1% per round trip (95% CI −11% to +7%). Round-trip ~30-DTE straddle cost: 4.8% pooled median.
  - Before Stage 1 (2023-10-30→2026-01-14) slope→RV20 Spearman was −0.002, and the trade netted −8.8%.
  - **Read: r ≈ −0.28 mostly reflects the already-priced IV level. A VALIDATED Stage 2 would not by itself make this tradeable.**
- **LITERATURE CAUTION (research-review item 6, added 2026-10-05 at the user's request; no change to the registered experiment).**
  - Published studies of term-structure slope predicting realized vol report **modest, time-varying** effects, per the user's literature review. **Don't over-interpret Stage 1's r = −0.28** as a stable effect size.
  - Two pieces of this project's own evidence point the same way:
    - Over 2023-10-30→2026-01-14, before Stage 1's window, the same slope's Spearman correlation with RV20 was −0.002 (economic check above).
    - The closely related VIX-term-structure result (Johnson 2017) did not carry over to Cboe strategy indices after 2009 (trial #13, Section 63).
  - **Practical reading:** expect a smaller Stage 2 effect than Stage 1's, possibly below what N = 139 can detect (80% power only from r ≈ 0.25). A Stage 2 failure would be consistent with a real but weaker or regime-dependent effect, not just with "no effect".

---

## 34. SpyGammaLoop trading-logic audit (2026-09-21) — the only currently-live system, never previously documented in plain terms

*(Condensed 2026-10-05, archive pass 3. The full prior text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number (Pass 3). **This is a current-state summary, not a substitute:** read the archived text before citing any detail not repeated here.)*

- **All three bots are running.** An earlier version of this section said the stock and options bots were paused; that was wrong (corrected 2026-10-01).
- **SpyGammaLoop's rules (SPY only):**
  - **Entry:** the live net-gamma regime is negative (System 2, `gamma_regime.py`: hardcoded vol 0.30, no dollar scaling), price is within 1% of a top-5 gamma wall, and that wall sits in a top-5 steepest-gradient zone. Call if price is above the wall, put if below.
  - **Guards:** a 3-loss circuit breaker, a 90-minute cooldown, account-wide daily-loss/drawdown checks, and a max-open-positions cap counting ALL option positions on the account.
  - **Sizing and exits:** 1% of equity in 4 tranches (A/B/C take profit at +20/40/75%; a RUNNER with a reversal guard after ≥50% gain), −45% stop, force-close at 15:45 ET, no overnight holds.
- **Lookahead: clean** on entry and exit (traced to source).
- **Evidentiary status: tier 1 (engineering / data collection). No formal experiment has ever tested it.** Section 42's REJECTED verdict does NOT transfer (different module, data source and method). Its paper P&L is not evidence.
- **Safety (re-audited 2026-09-24):**
  - `SPY_GAMMA_SHADOW_MODE=True`, with no override path; `paper=True`.
  - Zero `spy-gamma-` trades ever in `options_trades.db`.
  - Kill switch `spy_gamma_kill_server.py` (port 8099, shared `STOP_TRADING` file) is checked every cycle. It is independent of shadow mode.

---

## 35. SpyGammaLoop vs. GEX Method A — formula comparison (2026-09-21 follow-up)

*(Condensed 2026-10-05, archive pass 3. The full prior text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number (Pass 3). **This is a current-state summary, not a substitute:** read the archived text before citing any detail not repeated here.)*

- **Not a copy of Method A.** SpyGammaLoop's live gamma tools use a hardcoded vol of 0.30 and raw `gamma × OI × 100` without the `spot²×0.01` scaling, and they output an aggregate sign or unsigned per-strike concentration, not a zero-crossing price.
- **But they share Method A's architecture:** gamma is computed at one static spot with no hypothetical-price repricing sweep, the same vulnerability class Method B fixes.
- Flagged, not fixed. It sharpens Section 7 item 8d.

---

## 36. Method A/B follow-up: mechanics, validation status, root cause, and portability (2026-09-21)

*(Condensed 2026-10-05, archive pass 3. The full prior text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number (Pass 3). **This is a current-state summary, not a substitute:** read the archived text before citing any detail not repeated here.)*

- **The two methods:** Method A walks cumulative signed gamma across strikes without recomputing gamma. Method B sweeps ~200 hypothetical spots (±20%) and recomputes Black–Scholes gamma at each.
- **Method B was never validated as predictive.** It became "primary" only because it doesn't show Method A's implausible-distance symptom. Method A's root cause was never isolated; the static-spot explanation is inference.
- **Porting Method B into SpyGammaLoop isn't the applicable fix**, because `gamma_regime.py` only checks the sign at the real spot. The real gaps are the hardcoded vol 0.30 (needs a live IV source) and the missing `spot²×0.01` scaling (one line).
- None of these fixes would be validation. Any live signal needs its own pre-registered test.

---

## 37. Strike structure/positioning — candidate signal defined + feasibility confirmed (2026-09-22)

*(Archived 2026-10-01, pass 1. The full text is verbatim in `CLAUDE_ARCHIVE.md`. **This stub is a locator, not a substitute:** read the archived section before citing anything from it.)*

**Strike-positioning OI-skew candidate signal + feasibility (2026-09-22).** Defined `oi_skew = log(put_OI/call_OI)`, ±10% moneyness, 7-45 DTE, raw OI only; 18/18 feasibility. Formalized and then CLOSED in Section 39.

---

## 38. Feasibility survey: remaining untouched roadmap areas (2026-09-22)

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Feasibility survey of the untouched roadmap areas (2026-09-22).**
- **Data constraints as of that date:** no TensorFlow/PyTorch/RL libraries; no fundamentals data.
- **Low-lift:** XGBoost/nonlinear ML (since done: Sections 44-51) and Monte Carlo pricing (since done: Section 50).
- **Realistic:** statistical arbitrage (6 tickers is thin).
- **Partial:** cross-sectional (momentum only, no valuation data) and RL (5-min bars limit it).
- **From scratch:** LSTM.
- **Infeasible:** true tick-level microstructure.
- **Undefined:** area 16 (alternative architectures).

---

## 39. Third parallel experiment: strike-structure/positioning (OI skew) — pre-registration drafted (2026-09-22, NOT YET SUBMITTED, NOT RUN)

*(Archived 2026-10-01, pass 1. The full text is verbatim in `CLAUDE_ARCHIVE.md`. **This stub is a locator, not a substitute:** read the archived section before citing anything from it.)*

**Strike-positioning (OI skew) — CLOSED, REJECTED at Stage 1 (2026-09-27).** Hash `ae3b3a7d...`. N=605, 20-day r=+0.0248, p=0.08/0.11, far below |r|≥0.15; reverses under leave-SMCI-out and the 10-day horizon. 50-day horizon showed r=+0.236 (p<0.001) — disclosed, NOT a vindication; would need its own fresh pre-registration. Dataset: `strike_positioning_oi_skew_dataset.db`.

---

## 40. Historical GEX cache gap — root cause, backfill, and ongoing incremental pipeline (2026-09-22)

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Operational facts:**
- `gex_data_loader.py`'s 2026-06-10 → 2026-09-08 window was an intentional fixed research window. **Never edit `gex_data_loader.py`, `gex_calculator.py`, or the `TRAIN_START`/`TRAIN_END`/`HOLDOUT_END` constants.**
- Ongoing updates come from `gex_historical_incremental_update.py`: per-(ticker, date) completeness (both `sign_convention` rows), retries around network calls. It runs via the `GEX_Historical_Incremental_Update` task (19:45 ET, `run_gex_historical_update.bat`, log `gex_historical_update_log.txt`).
- SPY was added to its `TICKERS` 2026-09-24.
- Current `gex_metrics` state: see Section 60.

---

## 42. Fourth parallel experiment: GEX net gamma regime — pre-registration drafted (2026-09-22, NOT YET SUBMITTED, NOT RUN)

*(Archived 2026-10-01, pass 1. The full text is verbatim in `CLAUDE_ARCHIVE.md`. **This stub is a locator, not a substitute:** read the archived section before citing anything from it.)*

**GEX net gamma regime — CLOSED, REJECTED at Stage 1 (2026-09-22).** Hash `8dc7b1cd...`. Day-level population (not V1-gated). N=252 (33 negative-regime, 18 distinct negative days), 20-bar ratio 1.167× (<1.20×), p=0.044/0.052. Correct direction throughout; classification: insufficient evidence, genuine signal failure equally plausible. `sign_convention:flipped` is a near-mirror relabeling for regime-sign features, not independent evidence. Does NOT transfer to SpyGammaLoop's live gate (different module/data — Section 34).

---

## 43. SPY expansion: scheduling fix, historical backfill, and fifth pre-registration (2026-09-23/24)

*(Condensed 2026-10-05, archive pass 3. The full prior text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number (Pass 3). **This is a current-state summary, not a substitute:** read the archived text before citing any detail not repeated here.)*

**Current experiment: `spy_gex_callwall_volatility_v3_20261001`**, hash `afdf29dc28c9cdc2eff657171e65cf0a5af8dcfe553823dd129500dd18b3c41e`, file `preregister_spy_gex_volatility_v3_experiment.py`, `state=PREREGISTERED` (2026-10-01T21:15:38Z). It supersedes v2 (`ce0c2c0cee7571ddb08a66f24f3eb1a55525002403ec0170d9f317383a8b6c1b`, which added the volatility control) and v1 (`c2629dc1e8aff9f3037a16894622e96c8681899b28ad4fd7d037ae3e004256c2`). Neither was ever run; both are `status=SUPERSEDED`. It is graded under its own legacy rules, **not** `tiered_v1` (user decision 2026-10-05).

- **Hypothesis:** for SPY, the SIGNED T-1 call-wall distance (`call_wall_distance_pct`; positive = wall above spot) is NEGATIVELY correlated with forward realized vol, beyond the general vol level.
  - The mechanism is reasoned inference, not a literature citation.
  - It's distinct from the rejected GEX experiments: a signed continuous signal, a realized-vol target, SPY only.
- **Test:** day-level and unconditional; day-clustered Pearson + permutation (1000, seeds 42/43), one-sided; horizons 10/20/50, primary 20; α 0.0167; |r| ≥ 0.15.
- **Mandatory `volatility_control_gate`:** partial correlation controlling for SPY's trailing 20-day realized vol at T-1. It must be negative and significant, or the experiment is REJECTED. VIX wasn't used because the project had no VIX source when this was designed.
- **Robustness (5):**
  - Near vs far OPEX, by a pure calendar rule (±5 calendar days of the third Friday). The original live-chain mechanic was a structural no-op, fixed 2026-09-24.
  - Alternate horizons 10 and 50.
  - `net_gex_normalized`.
  - `put_wall_distance_pct`. On ~9 of 73 days the call and put walls share a strike, making it the exact negation there.
- **Window:** rolling from 2026-06-10, with the end re-derived at execution from data existence only. N = SPY days with a call-wall row and 20 closed forward sessions. **Stop and lock on the first night N ≥ 139; run once.**
- **Status 2026-10-05 (from `gex_metrics` and the NYSE calendar):** SPY dates 2026-06-10→10-02 (80, no gaps). **N = 61 of 139.** Lock on **the night of 2027-01-27** (observation #139 = 2026-12-28), assuming SPY GEX covers every session.
- **Power at N = 139:** 35.7% / 59.3% / 80.2% / 89.0% at r = 0.15 / 0.20 / 0.25 / 0.28; MDE 0.249.
- **Operational facts still live:**
  - SPY is in `gex_historical_incremental_update.py`'s `TICKERS` (since 2026-09-24). The one-time backfill `gex_spy_historical_backfill.py` is not scheduled.
  - The GEX task needs `DisallowStartIfOnBatteries=False` and `StopIfGoingOnBatteries=False` on this laptop.

---

## 44. Sixth formal experiment: XGBoost feature-interaction hypothesis — pre-registration drafted (2026-09-24, NOT YET SUBMITTED, NOT RUN)

*(Archived 2026-10-01, pass 1. The full text is verbatim in `CLAUDE_ARCHIVE.md`. **This stub is a locator, not a substitute:** read the archived section before citing anything from it.)*

**XGBoost feature-interaction hypothesis (win/loss target) — CLOSED, REJECTED (2026-09-25).** Hash `35b5e9b7...`. Dataset `ml_xgboost_interaction_data.db` (2,599 rows, real-IV Greeks, 99.3% match). Primary N=182, AUC delta +0.008/-0.004, not significant; RF does not corroborate; placebo clean. `exit_reason_stratified` check is structurally broken for this population (100% win/loss per exit reason). Classification: genuine signal failure.

---

## 45. Seventh formal experiment: XGBoost vs. Ridge on forward realized volatility — pre-registration drafted (2026-09-25, NOT YET SUBMITTED, NOT RUN)

*(Archived 2026-10-01, pass 1. The full text is verbatim in `CLAUDE_ARCHIVE.md`. **This stub is a locator, not a substitute:** read the archived section before citing anything from it.)*

**XGBoost vs. Ridge, forward realized vol, v1 — CLOSED, REJECTED (2026-09-25).** Hash `76f200b9...`. Dataset `xgboost_volatility_dataset.db`. Original result was on split-contaminated data (Section 56); clean rerun: delta +0.095, p=0.018 (narrow miss), still REJECTED. Superseded by Section 58's ticker-fixed-effects finding (no real feature signal).

---

## 46. Eighth formal experiment: Random Forest vs. Ridge on forward realized volatility — CLOSED: REJECTED at Stage 1 (2026-09-25)

*(Archived 2026-10-01, pass 1. The full text is verbatim in `CLAUDE_ARCHIVE.md`. **This stub is a locator, not a substitute:** read the archived section before citing anything from it.)*

**Random Forest vs. Ridge, forward realized vol, v1 — CLOSED, REJECTED (2026-09-25).** Hash `0655c4a2...`. Original sole trigger (`alternate_model:xgboost` reversal) was a contamination artifact (Section 56); clean rerun fails on primary non-significance instead. Superseded by Section 58.

---

## 47. Diagnostic investigation: why did Random Forest and XGBoost disagree on the forward-realized-volatility dataset? (2026-09-25)

*(Archived 2026-10-01, pass 1. The full text is verbatim in `CLAUDE_ARCHIVE.md`. **This stub is a locator, not a substitute:** read the archived section before citing anything from it.)*

**Diagnostic: RF vs. XGBoost disagreement (2026-09-25).** Concluded XGBoost overfit (train-test gap 1.589 vs RF 0.326; harmful vega/theta reliance; AMD-concentrated). Later shown (Section 56) to be driven by split-price contamination — on clean data the disagreement disappears.

---

## 48. Ninth formal experiment: Random Forest vs. Ridge on forward realized volatility, v2 — pre-registration drafted (2026-09-25, NOT YET SUBMITTED, NOT RUN)

*(Archived 2026-10-01, pass 1. The full text is verbatim in `CLAUDE_ARCHIVE.md`. **This stub is a locator, not a substitute:** read the archived section before citing anything from it.)*

**Random Forest vs. Ridge, forward realized vol, v2 — originally Stage-1-VALIDATED (2026-09-25), REJECTED on clean data (2026-09-27, Section 56).** Current hash `7fd2a1e9...` (was `472bf091...`). Clean rerun delta +0.071, p=0.69/0.77; LOTO reverses (SMCI); overfitting-gap check fails. Section 58 shows no feature signal beyond ticker means. `RF_v2_Stage2_Nightly_Update` (Section 52) was **DISABLED 2026-10-01**, so Stage 2 data no longer accumulates.

---

## 49. Diagnostic investigation: European vs. American option pricing — is this project's pricing chain missing a real early-exercise adjustment? (2026-09-25)

*(Archived 2026-10-01, pass 1. The full text is verbatim in `CLAUDE_ARCHIVE.md`. **This stub is a locator, not a substitute:** read the archived section before citing anything from it.)*

**Diagnostic: European vs. American pricing (2026-09-25).** `options_pricing.py` is plain European BS, no dividends. For this calls-only, near-non-dividend population the early-exercise premium is theoretically ~0 (AAPL ≈0.017% of spot over 14 days); LSM simulation residuals were pricer noise. No downstream results affected; no fix needed.

---

## 50. Risk infrastructure build: Monte Carlo VaR/CVaR framework, validated against V1's real trade history (2026-09-25)

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Monte Carlo VaR/CVaR framework (2026-09-25, `build_var_cvar_framework.py`; infrastructure, not live).**
- **Method:** bootstrapped joint-block historical returns (no lookahead); per-trade results on V1's 251 trades, plus a weekly portfolio view.
- **Results:** VaR95 breach rate 2.8%; VaR99 breach rate 0.4%; 0 of 13 weekly breaches. It erred conservative and never missed real risk.
- **Caveats:** a single 90-day episode, and vol is held fixed within each simulation.
- **Intended use:** sizing for any future validated strategy.

---

## 51. Tenth formal experiment: heavily-regularized XGBoost vs. Ridge on forward realized volatility — pre-registration drafted (2026-09-25, NOT YET SUBMITTED, NOT RUN)

*(Archived 2026-10-01, pass 1. The full text is verbatim in `CLAUDE_ARCHIVE.md`. **This stub is a locator, not a substitute:** read the archived section before citing anything from it.)*

**Heavily-regularized XGBoost vs. Ridge, forward realized vol, v2 — CLOSED, REJECTED (2026-09-26).** Current hash `54f79867...` (history `0276337c` → `1bccd0ba` → `e9f7aae1`). Clean-data rerun (Section 56) showed strong primary delta +0.195/+0.199 but placebo re-leaked 4/8 — root-caused in Section 58 to ticker-mean structure; incremental R² over ticker-only baseline is negative. Verdict stays REJECTED; gap-closure comparator question deferred (Section 58).

---

## 52. RF v2 Stage 2 automation: `RF_v2_Stage2_Nightly_Update` scheduled task added (2026-09-25/26)

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Operational facts:** the `RF_v2_Stage2_Nightly_Update` task (20:15 ET) runs `run_rf_v2_stage2_update.bat`, which runs `generate_xgboost_volatility_dataset.py` and writes `xgboost_volatility_dataset.db`.
- **Idempotency:** `UNIQUE(ticker, obs_date)` + `INSERT OR IGNORE`, a seen-set, and the lockfile `xgboost_volatility_generation.lock`. The script uses the RAW/ADJUSTED dual price series (Section 56).
- **DISABLED 2026-10-01, at the user's explicit instruction.** `Disable-ScheduledTask` was used; the task was not deleted. Verified: `State: Disabled`, `Settings.Enabled=False`, `schtasks` shows `Next Run Time: N/A`. (`Get-ScheduledTaskInfo` still printed a 20:15 `NextRunTime`; that is only the stored trigger time, not a pending run.)
  - **Why:** RF v2 is REJECTED on clean data with no path forward. Section 58's ticker-fixed-effects analysis found no options-feature signal beyond per-ticker means, so Stage 2 data can't rescue it. Each nightly run still spent the shared UnicornBay quota (Section 60), which the broader-universe backfill needs.
  - **Data:** `xgboost_volatility_dataset.db` stays exactly as is, at 4,051 rows (MAX `obs_date` 2026-07-21). It is still a reusable dataset.
  - **Reversal:** `Enable-ScheduledTask -TaskName RF_v2_Stage2_Nightly_Update`, only for a genuinely new, separately pre-registered hypothesis that needs this exact dataset to grow.

---

## 54. Diagnostic investigation: early-stopping placebo leakage in the regularized XGBoost v2 pipeline (2026-09-26)

*(Archived 2026-10-01, pass 1. The full text is verbatim in `CLAUDE_ARCHIVE.md`. **This stub is a locator, not a substitute:** read the archived section before citing anything from it.)*

**Diagnostic: early-stopping placebo leakage (2026-09-26).** XGBoost early stopping re-picks round count per fit (Ridge has no analog), leaking into `shuffled_target_placebo` (6/8 seeds significant). Fix: freeze rounds at real-data `best_iteration` for placebo fits only (→1/8). **Standing rule:** any future per-fit adaptive selection step must be frozen for placebo fits, or the placebo's limit disclosed.

---

## 56. Data-integrity remediation: raw/unadjusted split prices confirmed contaminating `xgboost_volatility_dataset.db` — fixed, dataset regenerated, all four affected experiments rerun (2026-09-27/28)

*(Archived 2026-10-01, pass 1. The full text is verbatim in `CLAUDE_ARCHIVE.md`. **This stub is a locator, not a substitute:** read the archived section before citing anything from it.)*

**Data-integrity remediation: raw/unadjusted split prices (2026-09-27/28).** Alpaca fetches default to RAW prices; split discontinuities (AAPL/NVDA/SMCI/TSLA) contaminated `xgboost_volatility_dataset.db`. **Standing technical rule:** use RAW closes only for EODHD strike/chain matching (spot, moneyness, Greeks) and ADJUSTED (`Adjustment.ALL`) closes for all returns/realized-vol — as implemented in `generate_xgboost_volatility_dataset.py:fetch_daily_closes()` and reused by the broader-universe script. Dataset regenerated (max vol 8.34→2.40); contaminated copies kept as `.bak`. All four affected experiments rerun (45/46/48/51); `dataset_version` bumped with content SHA-256 `51ecca69...`. Both open follow-ups are subsumed by Section 58. Fact-check: `factcheck_rf_v2_xgboost_v2_20260928.md`.

---

## 58. Ticker-fixed-effects analysis — decisive finding: none of RF v1/v2, XGBoost v1, or regularized XGBoost v2 ever showed real options-feature signal beyond a ticker-level average (2026-09-28)

*(Condensed 2026-10-05, archive pass 3. The full prior text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number (Pass 3). **This is a current-state summary, not a substitute:** read the archived text before citing any detail not repeated here.)* The standing rule it produced is in Section 1 (group fixed effects).

- **Finding (2026-09-28):** per-ticker mean forward realized vol varies ~4× (AAPL 0.24 … SMCI 0.92). A model with **no options features** ("predict each ticker's own average") scores R² = 0.50–0.51 on the real test sets, matching or beating every tuned 8-feature model.
- Adding the 8 options features on top of ticker dummies made every model **worse** than the ticker-only baseline: incremental R² from −0.019 to −0.076 across RF v1/v2, XGBoost v1 and regularized XGBoost v2 (`analyze_ticker_fixed_effects.py`).
- **Read:** none of those four experiments ever showed options-feature signal beyond ticker means. The verdicts are unchanged (each was decided under its own rules); regularized XGBoost v2 stays REJECTED.

---

## 60. Eleventh formal experiment: broader-universe (59-ticker) forward realized volatility, Target C — pre-registration drafted (2026-09-29, NOT YET SUBMITTED, NOT RUN)

*(Condensed 2026-10-05, archive pass 3. The full prior text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number (Pass 3). **This is a current-state summary, not a substitute:** read the archived text before citing any detail not repeated here.)*

**⛔ Target C RETIRED 2026-10-01 (user decision); never registered.** Hash `10f10a1364cd6034bc578c6807b9582a5fbe5f5912648cc71d2525f624e699cc`, file `preregister_broader_universe_volatility_c_experiment.py`.
- **Why:** it predicted relative realized vol, which mostly recovers the already-priced IV level (Section 33's economic check), so even a clean pass wouldn't have been tradeable. Its slot went to Section 62.
- **What remains:** `broader_universe_volatility_dataset.db` is kept as is (34/59 tickers complete), and task `BroaderUniverse_Volatility_Nightly_Update` is disabled.
- **Reusable pieces:** the 59-ticker universe and IPO checks, the RAW/ADJUSTED price rule (Section 56), the quota-safe fetch pattern, and the walk-forward purge rule (now part of Section 1's CPCV note).

**EODHD quota (planning facts):**
- **The quota:** the UnicornBay Options add-on dashboard says 100,000/day, on a rolling 24 h from the first request, **shared by every EODHD task**.
  - Measured twice: ~10,000 successful requests before a 429. Best guess: each options request bills as 10 calls.
  - **Plan on ~10,000 requests/day.**
- **The $25 extra-calls purchase** landed on the base account (`extraLimit`), not the options add-on. Ask EODHD support to move or refund it.
- **Checking the quota:** `single_quota_test.py` is authoritative. Don't trust `check_eodhd_quota.py`: it tests the base API and gives a false "QUOTA OK".
- **On a 429:** every collector stops the whole run at the first one (`QuotaExhaustedError`, logging `RUN STOPPED EARLY (QUOTA)`). A failed Alpaca daily-bar fetch skips that ticker instead of crashing.

**Scheduled tasks** (all `InteractiveToken`, windowless `pythonw.exe run_logged.py <script> <log>`; `WakeToRun` on except for the probe):

| ET | Task | Notes |
|---|---|---|
| every 2h at :23 | `EODHD_Quota_Probe_And_Resume` | `quota_probe_and_resume.py` → `quota_probe_log.db`. On quota success it runs GEX catch-up (`gex_gap_check.py`, then the GEX task if anything is missing) and the straddle snapshot step (a no-op now). Never reads CLAUDE.md. **Run only if a network is available** (since 2026-10-05). |
| 19:40 Mon–Fri | `CollectionWindow_KeepAwake` | **Added 2026-10-05.** `keep_awake_collection_window.py` holds `ES_SYSTEM_REQUIRED\|ES_DISPLAY_REQUIRED` until 21:20 ET (wall clock), heartbeat every minute to `keep_awake_log.txt`. WakeToRun, StartWhenAvailable, runs on battery, 2 h limit. |
| 19:44 | ~~`PreventSleep_DuringCollectionWindow`~~ | **Retired (disabled) 2026-10-05**: it never held the display, so it couldn't stop Modern Standby. Rollback XML `task_backup_PreventSleep_DuringCollectionWindow.before_sleepfix_20261005.xml`. |
| 19:45 | `GEX_Historical_Incremental_Update` | `gex_historical_incremental_update.py` → `gex_metrics` (Section 40). **Run only if a network is available** (since 2026-10-05). |
| 20:00 | `GEX_Prospective_Daily_Collection` | `daily_collection_run.py`; zero EODHD calls, uses Alpaca bars. Already had the network condition. `RestartOnFailure` removed 2026-09-29. |
| 20:15 | ~~`RF_v2_Stage2_Nightly_Update`~~ | **Disabled 2026-10-01** (Section 52). |
| 20:30 | ~~`BroaderUniverse_Volatility_Nightly_Update`~~ | **Disabled** (Target C retired). |
| 20:45 | `IVTermStructure_Stage2_Nightly_Update` | Section 33. **Run only if a network is available** (since 2026-10-05). |
| 21:05 | `ExecutionCost_EOD_Spreads` | Section 26; zero EODHD calls. |
| 21:15 | `EODHD_Daily_Health_Check` | `health_check.py`, below. |

Rollback XML for the pythonw conversions: `task_backup_<task>.before_pythonw_20261001.xml`.

**OPEN: collection-window failures.**
- On 2026-09-30 tasks were killed seconds after launch with `0xC000013A`; that root cause is still unknown.
- On 2026-10-04 tasks ran inside Modern Standby with no network: the event logs show the machine re-entering standby a second after its wake timer.
- `PreventSleep` didn't help: it held no display request, and its process ran ~20 h while suspended.
- On this machine sleep is already set to "never"; **Modern Standby starts when the display turns off** (5 min on AC, 3 min on battery).
- **Fixes applied 2026-10-05 (user-approved). Backups: `task_backup_<task>.before_sleepfix_20261005.xml` and `power_backup_scheme_sub_*.before_sleepfix_20261005.txt`.**
  1. **Network wait:** `RunOnlyIfNetworkAvailable` + `StartWhenAvailable` on `GEX_Historical_Incremental_Update`, `IVTermStructure_Stage2_Nightly_Update` and `EODHD_Quota_Probe_And_Resume`; `GEX_Prospective_Daily_Collection` already had it. Each task's XML differs from its backup only in that element.
  2. **Keep awake:** new weekday task `CollectionWindow_KeepAwake`, 19:40–21:20 ET. The health check now checks it: OK while running; FAIL on a missed weekday window, a missing END, or heartbeat gaps over 3 min (meaning the machine slept anyway).
  3. **PreventSleep retired:** task disabled, script kept.
  4. **Wi-Fi in standby: APPLIED 2026-10-05 via group policy** (the user ran the commands in an administrator shell).
     - **Policy:** `HKLM\SOFTWARE\Policies\Microsoft\Power\PowerSettings\F15576E8-98B7-4186-B944-EAFA664402D9`, `ACSettingIndex = 1` and `DCSettingIndex = 1` (read back).
     - **Effective setting:** `powercfg /qh SCHEME_CURRENT SUB_NONE F15576E8-98B7-4186-B944-EAFA664402D9` shows "Networking connectivity in Standby" (`CONNECTIVITYINSTANDBY`) at **AC index 1 and DC index 1 = Enable**.
     - **Correction to the earlier note:** the setting IS defined on this machine; it's just hidden, so `powercfg /q` (which I used before) doesn't list it, and only `/qh` does. My earlier non-admin `powercfg /setacvalueindex` attempt was never confirmed to have done anything. The per-scheme registry key is still absent, so the effective value comes from the policy.
     - **Still to prove in practice:** that the network is actually up while the laptop is in standby. Check tonight's task runs and the Task Scheduler Operational log.
- **Still unverified:**
  - Whether the 19:40 wake + display request actually keeps the machine out of standby when it was already asleep. The keep-awake heartbeat log will show it from the first night.
  - Whether a task whose network condition isn't met starts later, once the network returns. Check the Task Scheduler Operational log.
  - The 2-hourly probe's GEX catch-up remains the backstop either way.
- Until confirmed, verify scheduled runs against the databases, not their exit codes.

**Daily health check** (`health_check.py`, 21:15 ET):
- **(a) Data freshness**, **(b) tasks:** each ran on schedule with result 0 and its own log shows a completion marker, and **(c) bots:** running, with fresh heartbeats.
- On any FAIL it emails if SMTP is configured in `.env` (it isn't yet); otherwise it writes `HEALTH_ALERT.txt` and shows a toast. Status goes to `health_check_status.json`.

**Probe log:** since 2026-10-01, probe results go to `quota_probe_log.db` (table `probe_log`); the frozen 2026-09-29→10-02 table is archived.

---

## 62. Twelfth hypothesis: cross-sectional straddle (volatility-premium) strategy — HELD / INCONCLUSIVE (data-limited), parked 2026-10-02 (NOT pre-registered)

Takes Target C's slot (Sections 1, 60). Trial #12 in the program tally (Section 1).

**⏸ HELD / INCONCLUSIVE (data-limited), parked 2026-10-02 (user decision). NOT rejected.**
- **Why not rejected:** the test couldn't resolve the question either way. On DEV the Goyal–Saretto spread had the published sign but was noise-level and vanished once delta-hedged (−1.5% / −0.9% per cycle). With the current EODHD data (59 tickers, ~3 years), the minimum detectable effect at 80% power is ~10–13% per cycle (hedged spread, 23–36 cycles), against a plausible true effect of ~0–3%. A null at that power says nothing about effects in the plausible range. Failure classification: **data limitation**.
- **The $599 ORATS purchase is declined.** The user won't spend it before any promising result, and even with ORATS the detectable floor only improves to ~1.5–4.4% per cycle (~1.5% with a ~500-name universe, 4.4% with the current ~50 names over 2007–2023; `straddle_phase1_report.md`), so it wouldn't guarantee an answer either.
- **Parked, no further spend.** No new collection, purchases, or analysis. The DEV snapshots (`option_snapshots.db`), the pipeline, and the code stay as they are. **BLIND stays unexamined**, so it remains usable if this is ever reopened. `quota_probe_and_resume.py`'s `[SNAPSHOTS]` step is a no-op now (DEV complete, it never collects BLIND), so this hypothesis spends no EODHD quota.
- **Reopening** needs new data that brings the detectable effect to ≤ ~2% per cycle on the delta-hedged spread (the Phase 1 GO bar), by a new user decision.
- **Still trial #12 in the tally.** Its outcome was examined against data, so it counts once.
- **Slot:** reallocated 2026-10-02 by user decision to trial #13 (Section 63), a deliberate one-off, not a general rule. Reopening this hypothesis later would need a slot again.

**Phase 0/1 summary (condensed 2026-10-05, pass 3; full detail is verbatim in `CLAUDE_ARCHIVE.md`):**
- **Design, fixed before any data existed:**
  - Monthly cycles, from the first trading day after a monthly expiration to the next one.
  - Primary signal: the Goyal–Saretto gap HV(252 d) − ATM IV. Long ATM straddles at the high end; iron butterflies (|delta| 0.10 wings, capped loss) at the low end.
  - Costs at bid/ask, with 0.5× and 1× half-spread variants.
  - Liquidity rule: ATM straddle spread ≤ 5% of mid (median of the current and up to 5 previous entries); leg OI ≥ 100 and expiration OI ≥ 1,000, with missing OI treated as unknown.
  - Split windows excluded; an earnings flag from SEC EDGAR (`earnings_dates_edgar.py`).
  - Windows: DEV = 23 cycles through 2025-09 (examined). BLIND = later cycles, **unexamined**.
- **Code:**
  - `straddle_schedule.py` and `daily_prices.py` (consolidated SIP closes).
  - `option_snapshot_collector.py` → `option_snapshots.db`: 2 requests per ticker-cycle; DEV 2,714 snapshots from 2,758 requests.
  - `straddle_backtester.py` with tests, and `straddle_dev_analysis.py`. Report: `straddle_phase1_report.md`.
- **DEV result:**
  - Goyal–Saretto spread +6.5% / +10.0% per cycle at mid (t 0.6 / 0.9); **delta-hedged −1.5% / −0.9%**; trade-level correlation ≈ 0.
  - Minimum detectable effect (80% power): hedged spread 13% at 23 cycles, 10% at 36, 4.4% at 192. Breadth is the binding constraint.
  - EODHD reports false null or 0 open interest on liquid legs, so both rule versions are reported.

## 63. Thirteenth hypothesis: VIX term-structure timing of index volatility selling — CLOSED: REJECTED at Stage 1 (2026-10-02)

*(Condensed 2026-10-05, archive pass 3. The full prior text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number (Pass 3). **This is a current-state summary, not a substitute:** read the archived text before citing any detail not repeated here.)*

- **Experiment** `vix_termstructure_vrp_index_timing_v1_20261002`, hash `188828a66ad359c28692d923a8c7c57d8d91cdd507b1932f6427acb38e488d09`, registered 2026-10-02T18:36:18Z. Registry: `status=REJECTED` (state PREREGISTERED, like every script-run experiment).
- **Hypothesis:** ln(VIX3M/VIX) at the close before each monthly SPX roll positively predicts the next cycle's CNDR excess return over T-bills, beyond ln VIX and the VRP proxy (Johnson 2017).
- **Result (203 cycles, 2009-10-15→2026-09-17): REJECTED. Genuine signal failure, and well powered (87% at ρ = 0.20).**
  - Spearman ρ = −0.020 (p 0.61).
  - `vrp_control_gate` partial ρ = +0.056 (p 0.21): failed.
  - 10 of 13 sign checks failed, including the must-pass post-2014 subsample.
  - PUT and BXM went strongly the other way (ρ −0.27 / −0.36). Spotted after the fact, so not a finding.
- **Economic check (2012-10→2026-09):** always-on CNDR returned −1.08%/yr vs T-bills (Sharpe −0.17, max drawdown 18.4%), and timing didn't help. Costs aren't the problem (~0.01% of account value per roll).
- **Files:** `preregister_vix_termstructure_vrp_experiment.py`, `build_vrp_timing_dataset.py`, `data_snapshots/vrp_timing_20261002/` (SHA-256 manifest), `vrp_timing_stage1_execution.py`, `vrp_timing_stage1_results.json`.

## 64. Candidate #14, earnings implied-vs-historical move (F1) — HELD before registration, data-limited (2026-10-06)

**Not registered, hashed or run; it does not use the open slot and is not a ledger trial** (no outcome was examined, like Target C).
- **Approvals (user, 2026-10-06):** F1 from the study doc "Final Hypothesis Slot: Options Research Study"; α = 0.05/14; point-in-time S&P 500 + Nasdaq-100 as of 2023-10-01 plus the 59 project names; hard gates, soft checks and `tiered_v1` as in the study; ~12k EODHD requests; Phase 1 data only.
- **Collected:** `earnings_event_pipeline.py` → `earnings_event_dataset.db` (gitignored, unfrozen).
  - 535 tickers; 11,431 EDGAR Item 2.02 8-Ks; 6,504 EODHD requests.
  - Events Nov 2023 → Sep 2026: 6,183, minus 847 with an intraday 8-K (ambiguous timing) and 41 with too little history or no price (renamed tickers) = 5,295 candidates.
- **Screens:**
  - No expiry within 7 days after the reaction session: 2,383. ~170 names have only monthly expiries.
  - Straddle spread over 10% of mid: 1,556.
  - Mid under $1: 121.
  - Close under $10: 36.
  - **Survivors: 1,199** (3,000 needed). Exit quotes missing for 155 of them (12.9%; the soft-check limit is 5%).
- **Power at 1,199** (design effect 1.6): **20% at ρ = 0.07**; detectable effect at 80% power ρ ≈ 0.13. A test would almost surely have graded HELD.
- **Cause:** no weekly expirations for about a third of the universe, plus wide single-name spreads.
- **Lesson:** check weekly-expiry availability, and spreads on a sample, **before** estimating event counts or power. The study's 3,500–4,500 estimate skipped this.
- **Standing rule:** any revisit needs a new pre-design (universe, expiry rule, screens, power) approved before any data collection, and a hypothesis slot.
- **2026-10-06: one-time exploratory peek, user-approved exception.** Exploratory only, no trial; results in `exploratory_f1_peek_2026-10-06.md`. **These 1,199 events are no longer blind.**

## 65. Candidate: 1-day SPY iron butterfly (study "Options Hypothesis Study v2", Finalist A) — HELD before registration, data-limited (2026-10-06)

**Not registered, hashed or run; not a ledger trial; does not use the slot** (no outcome examined). Stage 0 coverage check: `stage0_spy_ironfly_2026-10-06.md` (272 EODHD requests, no returns computed).
- **Reason:** the specified exit (close the in-the-money legs at the next session's closing quote) can't be priced from EODHD. EODHD returns SPY contracts on their own expiration day only up to 2025-06-05, and even then all 4 legs were quoted on only 30 of 120 testable sessions; after that date, none.
- **Counts:** 752 entry sessions 2023-10-02→2026-09-30; next-day expiry never found missing; entry quotes clean on ~97% of observed sessions (structure spread median ~3% of net credit). Usable N ≈ 100 with the specified exit (power 1.3% at the 3% floor); ≈ 728 with an intrinsic-settlement exit, but still only 7.4% power (MDE 8.5% of premium), so nothing beyond HELD is reachable.
- **Account:** live ~$500 IBKR Pro (§62). Options level, 4-leg spread permission and XSP permission are **unverified**. Multi-leg credit spreads usually need a margin account ($2,000 FINRA minimum); check with IBKR.

**Descriptive risk study, 2026-10-06 (not a trial; no verdict):** `risk_profile_option_selling_indexes_2026-10-06.md` (`risk_profile_study.py`, commit `e80e233`): two-week losses and drawdowns of BXM/PUT/CNDR/BFLY vs SPX price.

## 66. Paper put-spread trial (2026-10-06): PAPER-ONLY forward trial, NOT a hypothesis test

Operations, risk and fill-realism track record on the Alpaca paper account: SPY ~0.15-delta $5 put credit spreads, one per week. **Not a hypothesis test; uses no slot**, and gets no ledger row, hash or verdict. Rules fixed 2026-10-06 (`paper_putspread_trial/README.md`). **Phase 1 = dry run only; no orders.** Phase 2 needs separate user approval.
- Script `paper_putspread_trial.py`, tests `test_paper_putspread_trial.py`. Open Phase 2 issue: the paper account is shared with the bots, and the options bot counts every option leg against its 3-position cap.

## 61. How to use this file

- Read this file first, every session, in this folder.
- When an experiment or diagnostic formally closes and nothing live depends on it, move its section verbatim to `CLAUDE_ARCHIVE.md` and leave a stub here with the same number and title, plus the verdict, the hash, and any rule or operational fact that still applies.
- Update it in place whenever something material changes — a bug fixed, an experiment closed out, a number confirmed against the DB, a roadmap area's status changing.
- Don't trust a number that isn't backed by a DB query or a file you've actually read this session.
- If you're not sure whether prior work exists on something, grep/search the codebase before assuming "untouched."
- **Git (from 2026-10-01): commit after every pre-registration hash change, registration, or structural fix**, at the same granularity as CLAUDE.md updates.
  - Portable MinGit 2.56 + git-lfs 3.8 live in `%LOCALAPPDATA%\Programs\MinGit\cmd` (on the user PATH; open a new terminal, or prepend it).
  - Repo settings: `core.autocrlf=false` (byte-exact files); commits authored as fmkris05 <fmkris05@gmail.com>.
  - `.gitignore` excludes `.env`, every `*.db`, logs, backups and binaries; **databases are not in git**, so back them up separately.
  - The remotes are old, unreachable Replit addresses; **nothing is pushed anywhere**.
  - Commits so far: `3d1b45c` (full snapshot, the first since 2026-08-12), `11a2c8b` (threshold fix). Commit messages via `git commit -F <file>`; PowerShell passes a here-string as a path, not a message.
- **Scripts must never parse CLAUDE.md.** It's for humans; automation logs to its own files or databases (probe → `quota_probe_log.db`, health check → `health_check_log.txt`/`.json`).
- **STANDING RULE: read the archive before relying on an archived section.** Whenever a topic with a stub here becomes relevant again (someone asks about it, a new hypothesis touches the same area, or a number from it needs citing), open `CLAUDE_ARCHIVE.md` and read the actual archived section first. A stub is a locator, not a substitute. This applies equally to condensed active sections (3, 7, 40, 52, 60): their archived text holds the full history behind the summary.
- **Search both files.** When looking for a hash, file name, DB, task, or number, grep `CLAUDE.md` AND `CLAUDE_ARCHIVE.md`. The index below covers identifiers that appear only in the archive.
- **When archiving more:** run a byte-for-byte round-trip check, keep a hashed `.bak`, never renumber, re-run the identifier cross-check, and log the change in the header's reorganization history.

### Archived-identifier index (identifiers that appear only in `CLAUDE_ARCHIVE.md`, as of pass 3)

**Config hashes (full):**
- `9820ed6e18c11f7fa069a931490823398081e469ee5c01c95cec7009b3745fde`: GEX call-wall, superseded (§32)
- `3c0cd574b84b758395aa23ab68b008b3bace4d382d0c69154a1dde9fea930d13`: net gamma regime, superseded (§42)
- `ae3b3a7df686159c0e3dcad1556f6433c64bee2828a1d2c4bee5cd3b71cded33`: OI skew (§39)
- `026e5f997f423e38cfc788f736cee4e3e1082e634f7f49e1d2578caccd14d364`: XGBoost interactions, superseded (§44)
- `35b5e9b722d3f87928819a29dd0c72584c3d9d0d9b696e135a34f555409fd31f`: XGBoost interactions, final (§44)
- `76f200b96fdabb10bb0af2edfc12e4a098abf664108e4349711ed70f0b3ea04b`: XGBoost vol v1 (§45)
- `0655c4a23b41024954b07f29fb5d813b873fd14d9dd145f17640a3549af4557e`: RF v1 (§46)
- `472bf091313098dadbb89b28a6ff039503f7232c1e34e7b7cfee497d563b1fc5`: RF v2, pre-bump (§48)
- `7fd2a1e91f946579397da8da50c317ca93b3983f7f589c19ec1a5f8c2f20e07f`: RF v2, current (§48)
- `0276337ca56cced3fa58fe92cb2cbc4b312b1186b39d42493e5530ea382ba1d2`: regularized XGBoost v2, hash 1 of 4 (§51)
- `1bccd0ba4b8b6f9350bde3f1c7dba97b93a48db9cfa679afecb2b3605ffdab97`: regularized XGBoost v2, hash 2 of 4 (§51)
- `e9f7aae1458346cdc5484c138cc562b8bc01017f0317de5303e6fb0da9c57be2`: regularized XGBoost v2, hash 3 of 4 (§51)
- `54f7986788cfa1d52b4dc695930754e09fbf7c7b6ebe32d96ab50ed815c4bbdd`: regularized XGBoost v2, current (§51)
- `51ecca695bff10a37cd0c597c39562c267b94507affb512f138a799f1e102950`: SHA-256 of the clean `xgboost_volatility_dataset.db` (§56)

**Scripts and files, by archived section:**
- §8: `audit_positions_vs_alpaca.py`, `automated_uptime_monitor.py`, `uptime_log.py`, `signal_log.db`, `options_signal_log.db`, `uptime_log.db`
- §9: `test_gex_calculator.py`, `phase3_revalidation.py`, `phase4_experiment.py`, `phase4_stage1_data_collection.py`
- §10: `test_massive_data.py`, `check_contract_peak.py`, `check_today_peak.py`, `check_morning_peak.py`, `update_check_contract_peak.py`, `trade_reviews.db`, `pattern_reviews.db`, `account_reviews.db`, `lessons_learned.db`, `spy_gamma_lessons.db`
- §11: `refine_reversal_detector.py`, `final_fix_reversal_detector.py`, `apply_reversal_guard_fix.py`
- §12: `train_baseline_model.py`, `save_trained_model.py`, `test_features_options.py`
- §7: `performance_metrics.py`, `test_puts_vs_calls_backtest.py`, `run_gex_collection.bat`, `gex_collection_log.txt`
- §38: `requirements.txt`
- §32: `preregister_gex_callwall_experiment.py`
- §42: `preregister_gex_netgammaregime_experiment.py`
- §39: `preregister_strike_positioning_experiment.py`, `generate_strike_positioning_dataset.py`, `fetch_oi_skew_variants.py`
- §44: `preregister_xgboost_interaction_experiment.py`, `generate_xgboost_interaction_dataset.py`, `generate_training_data.py`, `ml_training_data.db`, `ml_experiment1_executor.py`, `ml_experiment1_final_executor.py`
- §45: `preregister_xgboost_volatility_experiment.py`
- §46: `preregister_randomforest_volatility_experiment.py`, `randomforest_volatility_stage1_execution.py`
- §47: `investigate_rf_xgboost_disagreement.py`
- §48: `preregister_randomforest_volatility_v2_experiment.py`, `randomforest_volatility_v2_stage1_execution.py`
- §49: `investigate_american_vs_european_pricing.py`
- §51 and §56: `preregister_xgboost_volatility_v2_experiment.py`, `xgboost_volatility_v2_stage1_execution.py` (constant `RF_V2_R2_DELTA` holds stale contaminated references), `xgboost_volatility_dataset.CONTAMINATED_20260927.db`, `xgboost_volatility_dataset.WRONG_ADJUSTED_SPOT_20260927.db`
- §60: `eodhd_quota_probe_log.jsonl`, `run_iv_termstructure_stage2_update.bat`

**Added by pass 3 (2026-10-05; identifiers now only in the archive's "Pass 3" block):**
- Superseded hashes:
  - §33 IV v1 drafts: `98e16643b9082db085f8d461b06edf5be7c13e223a95b348c241d84f7cf62a87`, `4e720d094afb417b7480433f7dbff27efbf172999cd9c62c856c783f5dd8bfa4`, `09bc383803cbbabe4141752c3ba66d023e91923e6a4f6975b7805a946ee653e4`.
  - §43 SPY v1 drafts: `13db39e23b43e3585ef997183c9ed794b6e8f37969b711b3f92326a853691c01`, `39c8a075ccba1d872500c214e26081e1f3bf7b4679948e1b9c2d33d95c5aea41`, `1e84831a1e3daf2d77e7f7ce0d5889e1a02be9b7f502aaaaea50953cd3a38e99`.
- Pass 1/2 backup SHA-256s (archive "Header" block): `6AD81931…` (`CLAUDE.md.pre_archive_20261001.bak`), `89DD1106…` (`CLAUDE.md.pre_archive_pass2_20261001.bak`), `9508C110…` (`CLAUDE_ARCHIVE.md.pre_pass2_20261001.bak`).
- Files:
  - §33: `preregister_iv_termstructure_experiment.py` (v1), `iv_stage1_economic_sanity_check.py`.
  - §43: `preregister_spy_gex_volatility_experiment.py` (v1), `preregister_spy_gex_volatility_v2_experiment.py`.
  - §26: `execution_cost_eod_log.txt`.
  - §34: `trades.db`.
  - §58: `ticker_fixed_effects_analysis_20260928.log`.
  - §60: `generate_broader_universe_volatility_dataset.py`, `broader_universe_feasibility_report.md`, `target_design_comparison_v1.md`, `target_c_baseline_and_walkforward_design_v1.md`, `preregistration_prep_resolution_v1.md`, `eodhd_quota_safe.py`, `health_check_state.json`, `quota_probe_and_resume_log.txt`, `iv_termstructure_stage2_update_stdout_log.txt`, `broader_universe_volatility_generation.lock`, and `task_backup_<task>.before_pythonw_20261001.xml` for GEX_Historical / GEX_Prospective / IVTermStructure.
  - §62: `daily_prices.db`, `earnings_dates.db`, `straddle_dev_analysis_results.json`, `test_straddle_backtester.py`.
  - §63: `vrp_feasibility_check.py`, `research_database.db.pre_trial13_20261002.bak`, `research_database.db.pre_trial13_result_20261002.bak`.
- **Pass 4 (2026-10-06):** `phase6_primary_control.py`, `phase7_steps1to3.py`, and the backfilled `research_database.db` rows `phase6_signal_random_control_20260914`, `phase7_pnl_concentration_20260914`, `full_population_iv_repricing_20260914` (§5).
- Constants and environment variables: `EXECUTION_COST_OPTIONS_FEED`, `STARTUP_RETRY_DELAYS_SEC` (§26); `OPEN_END_AT_EXECUTION` (§43); `HEALTH_SMTP_HOST`, `HEALTH_ALERT_TO`, `TARGET_C_RETIRED` (§60).

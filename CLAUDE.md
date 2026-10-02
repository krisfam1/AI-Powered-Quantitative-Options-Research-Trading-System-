# AI Option Trading Bot — Project Memory

**Read this file at the start of every session in this folder.** It is the persistent memory for this research project, since each Claude Code session otherwise starts with zero history. Keep it updated as work progresses — when something here becomes stale (a bug gets fixed, an experiment closes out, a status changes), edit this file directly.

**Last updated: 2026-10-02** (cross-sectional straddle HELD / INCONCLUSIVE, data-limited; ORATS declined. Section 62. Its slot reallocated to trial #13, VIX term-structure → CNDR, PREREGISTERED. Section 63).

**This memory is split across TWO files: `CLAUDE.md` (this file, loaded automatically) and `CLAUDE_ARCHIVE.md` (never loaded automatically, so open it deliberately).** Section numbers are unchanged across both. A section marked "Archived 2026-10-01" here is a stub: either a one-paragraph locator, or for still-active sections (3, 7, 40, 52, 60) a current-state summary whose full history lives in the archive. See Section 61 for the read-the-archive-first rule and the archived-identifier index.

**Reorganization / correction notice history:**
- **2026-10-01, pass 1:** closed experiments and diagnostics 32, 37, 39, 42, 44-49, 51, 54, 56 were moved verbatim to the archive. Backup: `CLAUDE.md.pre_archive_20261001.bak` (SHA-256 `6AD81931550A3B1CD3AEF42CBA14F2F1C7B3B1F61C314EAE97B643A28509A744`).
- **2026-10-01, pass 2:** the architecture maps 8-12, the V1 forensic/reference sections 13, 16, 17, 20-25, 27, 29, 30, and sections 38 and 50 were archived. Sections 3, 7, 40, 52, and 60 were condensed to current state, with their full prior text archived. Backups: `CLAUDE.md.pre_archive_pass2_20261001.bak` (`89DD11062A3B9E559A8602F5F8418CEFC199AB57B698B363C9F2463116E8C84C`) and `CLAUDE_ARCHIVE.md.pre_pass2_20261001.bak` (`9508C110D825396678045D9AED87673A8A69785E6581E89262EFCBADB2AC6E38`).
- **Both passes passed a byte-for-byte round-trip check:** putting the archived text back in place of the stubs reproduces the pre-pass file exactly. Nothing was edited or deleted, only relocated. Git isn't on PATH on this machine, so these `.bak` files are the only rollback.
- **Known cross-document drift:** the claude.ai `research-manifest.md` (not synced) still shows RF v2 as Stage-1-VALIDATED. Here it's REJECTED on clean data (Sections 48/56/58). The manifest's section numbers also differ (e.g. its "Section 24" = Section 60 here). Fix the manifest by hand.
- **To propagate to the manifest (2026-10-02):** the cross-sectional straddle hypothesis (trial #12, Section 62 here) is now **HELD / INCONCLUSIVE (data-limited)**, parked, with ORATS ($599) declined and no further spend. It is not rejected. Its slot went to **trial #13** (VIX term-structure slope → Cboe CNDR iron-condor returns; PREREGISTERED 2026-10-02, hash `188828a66ad359c28692d923a8c7c57d8d91cdd507b1932f6427acb38e488d09`; Section 63 here).

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
  - **DECIDED 2026-10-02 (user): the held straddle's slot goes to trial #13, VIX term-structure timing of index volatility selling (Section 63).** This is a deliberate reallocation to that specific replacement, not an automatic rule that "held" frees a slot. Current three: IV term-structure v2, SPY GEX v3, trial #13.
  - **DECIDED 2026-10-01 (user): slot swap, not an exception.** Target C was retired because it predicted (relative) realized vol, the same structural flaw the IV Stage 1 economic check exposed that evening (Section 33): forecasting RV mostly recovers the already-priced IV level, while a tradeable position pays RV − IV. The cross-sectional straddle hypothesis, whose payoff *is* the RV − IV gap, took its slot. The count stays at three; no exception was used.
- **Program-level hypothesis-trial tally** (added 2026-10-01). Every hypothesis whose outcome has been examined against data, or that is pre-registered and pending, counts once; any future Deflated Sharpe Ratio or multiple-testing assessment uses this count as the number of trials. Versions of one hypothesis (v1→v2→v3) count once.
  1. V1 entry signal / Phase 6 · 2. ML Experiment 1 · 3. GEX call-wall-distance · 4. GEX net gamma regime · 5. Strike-positioning OI skew · 6. XGBoost feature interactions · 7. XGBoost vol vs Ridge · 8. RF vol vs Ridge (v1+v2) · 9. Regularized XGBoost vol · 10. IV term-structure slope (pending Stage 2) · 11. SPY GEX call-wall vs vol (pending) · **12. Cross-sectional straddle, Goyal–Saretto RV−IV gap (Section 62, HELD / INCONCLUSIVE, data-limited, since 2026-10-02)** · **13. VIX term-structure slope → Cboe CNDR short-vol returns (Section 63, PREREGISTERED 2026-10-02, hash `188828a6…`, not run)**.
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

**Research framework (formal pipeline):** `experiment_config.py`, `gates.py`, `verdict.py`, `multiple_testing.py`, `robustness.py`, `run_experiment.py`, `canonical_hash.py`, `db_interface.py`, `experiment.py`, `create_research_db_schema.py`.

**EODHD data-capability audits:** `eodhd_field_audit*.py`, `eodhd_audit_term_structure.py`, `eodhd_audit_strike_structure.py`, `eodhd_historical_coverage_audit.py` — confirmed real term-structure + strike-structure depth, 0% null rates on Greeks/IV/bid-ask/OI/volume.

**Closed-out diagnostics (do not relitigate without new evidence):**
- `check_lookahead_bias.py` — no lookahead bias in entry-score/breakout computation.
- `diagnostic_5bar_vs_20bar_v3.py` — 5-bar exploratory finding did not replicate OOS (-0.54% relative MSE reduction).
- V1's raw entry signal shows no predictive edge beyond random chance within its own candidate population (Phase 6).
- V1's apparent historical profitability concentrates in a small number of trades + reversal-guard exits (Phase 7).

**Phase 6/7 forensic attribution — expanded with verified numbers, 2026-09-20.** The two lines above were previously the only durable record of this work. Surfaced via an old onboarding prompt, then independently re-verified this session by rerunning the actual scripts fresh (`phase6_primary_control.py`, `phase7_steps1to3.py`) and cross-checking `research_database.db`'s three backfilled rows (`phase6_signal_random_control_20260914`, `phase7_pnl_concentration_20260914`, `full_population_iv_repricing_20260914`). All numbers below **confirmed exactly**, not just trusted from a docstring or cached output. Note: these DB rows are explicitly self-labeled in their own `notes` field as "RETROACTIVE BACKFILL... does NOT constitute genuine preregistration" — real, honest research, but never run through the formal gates/verdict pipeline (Section 12).
- **Phase 6 Monte Carlo control on the raw entry signal:** `T_obs = -0.2569%` (day-clustered mean 20-bar forward return, 579 valid signals, 60 days, 6 tickers). Ticker+regime-conditioned control (1000 replicates × 2 seeds): p=0.996 / p=0.997. Same-ticker-same-day control: p=1.0 both seeds, 100% signal coverage. This is the quantified version of the "no predictive edge beyond random chance" line above.
- **Phase 7 exit attribution:** `stop_loss` exits: n=150, win_rate=0%, total P&L=**-$66,025.67**. `reversal_guard` exits: n=101, win_rate=100%, total P&L=**+$86,453.30**. Nets to the frozen $20,427.64 baseline. **Caveat:** the 0%/100% win rates are near-definitional given how these exit rules are constructed (stop_loss triggers on a loss by definition; reversal_guard only fires once unrealized gain ≥40%) — not evidence of exit-timing skill. The real information is in the magnitude split, not the win-rate extremes.
- **Phase 7 concentration cascade:** full population **$20,427.64** (251 trades) → excluding top ticker (SMCI, $10,083.02): **$10,344.62** → excluding top 2 tickers (SMCI+MSTR, $8,351.96 combined): **$1,992.66** → excluding the top 5 individual trades: **$476.64**. Top-5-trades contribution = **97.7%** of total P&L. Per-ticker breakdown: AAPL +$1,469 (7.2%), TSLA +$1,285 (6.3%), NVDA -$3,246 (-15.9%), AMD +$2,484 (12.2%), SMCI +$10,083 (49.4%), MSTR +$8,352 (40.9%).
- **Phase 7 position-sizing attribution:** actual position-sized total **$20,427.64** vs. equal-$1000-per-trade normalized total **$26,089.12** — position sizing *cost* -$5,661.48 relative to equal-weighting, driven by cheap options (<$2 premium) getting far more contracts on average (15.4) than expensive ones (≥$2, 2.2 contracts) — the sizing formula is premium-inverse and happened to load up on some of the cheaper, lower-conviction setups.
- **Methodological note:** `phase7_steps1to3.py`'s underlying-price back-solve technique (recovering implied spot from saved option premiums via Black-Scholes inversion) validated at 251/251 trades within 0.5% of ground truth, median error 0.0001% — a trustworthy method for any future attribution work on this same trade population.

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
| `vix_termstructure_vrp_index_timing_v1_20261002` (Section 63; trial #13) | ln(VIX3M/VIX) at the close before each monthly SPX roll positively predicts the next cycle's CNDR excess return, beyond the VIX level and the VRP proxy | Free Cboe daily CSVs + Treasury 4-week bill; 203 monthly cycles, 2009-10-15 → 2026-09-17 | Spearman + permutation, one horizon, mandatory vrp_control_gate, 13 sign-only checks (≤ 1 may fail; post-2014 must pass), OOS R² vs historical mean; Stage 2 informative only | Spearman ρ; α = 0.05 one-sided; ρ ≥ 0.15 | Not run; no slope or return computed | **PREREGISTERED 2026-10-02** (hash `188828a6…`); ceiling SUGGESTIVE | Next: build the dataset snapshot, run Stage 1 once. Power 67% at ρ = 0.15, 87% at 0.20; MDE 0.18. | No |

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

### Bots' purpose: execution-cost measurement instrument (decided 2026-10-01)

**User decision:** StockTradingBot and OptionsShadowLoop are kept running, **not paused**, but their purpose is now to **measure real execution cost** (bid/ask spread actually paid vs the project's spread/pricing models), not to validate the V1 signal (rejected, Section 13/18).
- **Design v1 (for review, NOT implemented):** `execution_cost_measurement_design_v1.md`.
- **Key findings behind it:**
  - Today's logs can't measure spread cost: options entry and exit overwrite the pre-trade quote with the fill, and the bid is never recorded (`live_options_trader.py:289–333`, `options_exit_monitor.py:50–118`).
  - Alpaca **paper fills are simulated**, at the quoted NBBO with no impact, so they give a *lower bound* on real cost.
  - The options bot has had no fills since 2026-09-17.
- **Proposal:** (A) a fill log capturing bid/ask/mid at submit, as validation; (B) a per-minute **quote sampler** over a fixed contract panel (6 tickers + SPY, 0.30-delta and ATM, 7–16 and 30–45 DTE), as the primary measurement. Both are compared with V1's tiered model and with EODHD end-of-day spreads.
- **Timeline:** ~20 trading days for a usable cost table. The economic sanity check on IV Stage 1 can be run now with historical EODHD bid/ask.
- **§6 decisions (user, 2026-10-01):** (1) Stream B is the primary measurement, Stream A a secondary cross-check only; (2) **options only**, the stock bot is out of scope; (3) run the IV Stage 1 economic sanity check now (done; Section 33).
- **Stream B built 2026-10-01: `execution_cost_logger.py` → `execution_cost_log.db`** (tables `panel`, `quotes`, `sampler_runs`).
  - Panel fixed once per ET day: 6 research tickers + SPY; near (soonest 7–16 DTE) and far (latest 30–45 DTE) expirations; call and put at |delta| closest to 0.30 (Alpaca snapshot Greeks) and at the strike closest to spot. 56 contracts.
  - Each sample is one batched latest-quote call plus an IEX spot call, ~2.5s. Each row stores bid/ask/sizes, mid, quoted half-spread, V1's model half-spread (`_estimated_spread_cost_pct/2`), spot, DTE, moneyness, and **the feed**.
  - Called once per 60s cycle from `options_shadow_loop.py`, after the exit check, in try/except (no orders, cannot block trading). **Goes live when OptionsShadowLoop restarts at midnight ET 2026-10-02**; first session 10/02. No service restart was done.
  - Tested against a scratch DB at 17:25 ET 10/01: 56/56 contracts, no errors. The production `execution_cost_log.db` didn't exist yet.
  - `health_check.py` gained `data/execution_cost_sampler`: FAIL with 0 quotes for the last closed session; WARN under 200 runs or more than 10% errors; "not active" before 10/02.
  - **Stream A (fill-log hooks in the order code): not built.** It's secondary, and it would touch order-submission files. Deferred.
- **⚠ BLOCKER: the account has only Alpaca's INDICATIVE options feed.** OPRA requests return `"OPRA agreement is not signed"`. Per Alpaca, indicative quotes are adjusted derivatives of OPRA, "not actual OPRA quotes", meant for debugging, not strategy testing. So:
  - Stream B currently measures Alpaca's modified spreads, **not real market cost**. It still runs (the feed is recorded per row) and can be compared against EODHD's real EOD quotes, but its cost table can't be trusted until OPRA is active.
  - Paper fills are presumably simulated against the same feed, which weakens Stream A too.
  - To fix: an Alpaca market-data subscription that includes OPRA, then set `EXECUTION_COST_OPTIONS_FEED=opra` in `.env`. **User decision.**
- **SUPERSEDED SAME DAY (user decision 2026-10-01): EODHD end-of-day spreads are now the PRIMARY cost source; the Alpaca indicative sampler is SECONDARY. OPRA is not needed for now and its pricing was not checked against the account.**
  - **Coverage:** EODHD's chain records carry bid, ask, bid/ask sizes, delta and IV for every panel cell (6 tickers + SPY; near/far; ATM and ~0.30-delta; calls and puts). Every sampled quote's `ask_date` matched its observation date (no stale-day quotes).
  - **Zero extra EODHD calls:** `GEX_Historical_Incremental_Update` already stores the full chains for all 7 tickers nightly in `gex_data_cache.db:raw_records`. The catch: cost data lags whenever that task is quota-blocked (currently through 2026-09-29), and backfills automatically when it catches up.
  - **`execution_cost_eod.py`** (read-only on `gex_data_cache.db`) → `execution_cost_log.db:eod_spreads`.
    - `panel='eodhd'`: the cost panel, chosen with the sampler's rules but EODHD's own delta.
    - `panel='alpaca'`: EODHD's close quote for the exact contracts the intraday sampler watched, for the indicative-vs-real cross-check, which the script prints each run.
    - Idempotent and self-healing.
    - Built 2026-10-01: 2026-06-10..09-29, 77 dates, 4,276 rows, 0 without a valid bid/ask.
  - **Task `ExecutionCost_EOD_Spreads`**, 21:05 ET daily: `pythonw run_logged.py execution_cost_eod.py execution_cost_eod_log.txt`, settings copied from the GEX task. `schtasks /run` test: result 0.
  - **Health check:** new `data/execution_cost_eod_spreads` (FAIL if `eod_spreads` trails the GEX chains). `data/execution_cost_sampler` downgraded to WARN-only.
  - **Median full spread** (% of mid, 2026-06-10..09-29), ATM / 0.30-delta:
    - far: SPY 0.6/0.7, TSLA 2.2/2.7, NVDA 2.8/3.9, AAPL 5.8/9.3, AMD 7.1/12.3, MSTR 10.2/16.2, SMCI 11.9/20.4.
    - near: SPY 0.8/1.2, TSLA 2.2/2.8, NVDA 3.4/3.4, MSTR 5.5/8.4, SMCI 6.0/8.5, AMD 6.8/10.4, AAPL 8.3/12.1.
    - Day-to-day noise is large (CV 0.4–1.1; p90 up to 54%), so use medians/percentiles, never a single day.
  - **Is end-of-day good enough?** Yes for strategies that hold for days or weeks and can choose when to trade, as a somewhat conservative, noisy estimate.
    - Option spreads are widest at the open and narrow through the day. Some studies also find a widening just before the close, and EODHD's quote is stamped 15:59:59.
    - Patient limit-order traders pay ~30–60% of the quoted spread (Muravyev & Pearson).
    - It can NOT measure costs at the open or for intraday strategies (SpyGammaLoop, V1-style 5-min entries); there it likely understates.
    - Backtest convention: base = EODHD median quoted spread by ticker/bucket/role; sensitivity 0.5× (patient limits) and 1.5× (open / market orders).
    - The indicative sampler now serves to estimate the time-of-day **shape** (its own spread relative to its own close quote) and to measure its level distortion against EODHD at the close. The shape use rests on the unverified assumption that Alpaca's adjustment roughly preserves it.

### Restart churn + bot startup/idle fixes, 2026-10-01

- **Finding:** NSSM restarted `StockTradingBot` and `OptionsShadowLoop` **~430–450 times per weekday evening**, every evening (`signal_log.db` has **7,799 `[EOD]` rows since 2026-08-13**).
  - **Cause:** by design, not a fault. `market_closed_for_day()` is True from 16:05 ET to midnight on weekdays. `main.py` then did `sys.exit(0)` ("VM will restart…"), and `options_shadow_loop.py` did `return`. NSSM (`AppExit=Restart`, `AppRestartDelay=60000`) restarted each one every ~62.9s (median), and it exited again at once.
  - **Effect on trading:** none.
  - **Side effects:** 75% of the 20 MB Application event log (41,872 of 55,892 events). Everything before 2026-09-17 22:42 has been overwritten. Plus the `[EOD]` rows in `signal_log.db`.
- **Separate finding:** ~220 stock-bot exits with **code 1**, median 2.5s after start. The startup `trading_client.get_account()` (`main.py`) had no error handling, so it crashed when the network wasn't up yet, e.g. right after reboots: 21 straight crashes on 2026-09-28 13:22–13:43 ET after an unclean reboot, and one at 00:30:47 on 10/01. NSSM recovered each time within ~1 min.
  - **Real multi-hour trading gaps came from the laptop**, not NSSM: 9/28 (standby 12:04 → unclean reboot 13:21 → sleep 13:43 → no activity until 18:31), 9/23 (first heartbeat 10:51), 9/24 (11:00).
- **Fixes (code only; no signal, order, or market-hours logic touched):**
  1. **`main.py` startup retry:** `_print_connection_status()` retries `get_account()` with waits `STARTUP_RETRY_DELAYS_SEC = [5, 10, 20, 40, 60]` (~135s). If every attempt fails it re-raises, so the process still exits with code 1 and NSSM restarts it, as before. Tested: real call OK; 2 simulated DNS failures then success; permanent failure → re-raise after 135s.
  2. **Evening idle instead of exit:** a new `main.idle_until_next_et_day()` waits until the ET date changes, re-checking the wall clock every 60s (one long sleep could overrun on a sleeping laptop). Both end-of-day branches call it, then exit once at midnight. That means 1 restart per evening instead of ~450.
     - Chosen over lengthening NSSM's restart delay, because NSSM has one delay for all exits and a longer one would also slow crash recovery during market hours.
     - Tested with a simulated clock: weekday and Friday evenings return at 00:00 ET; a laptop asleep mid-idle returns on wake (07:29), before the open.
- **Activation:** the running bot processes started 2026-10-01 00:30–00:31, before the code edits (11:27). They load the new code on their next NSSM restart, expected right after the old code's 16:05 ET exit today.
- **PENDING (not yet run by the user; needs an admin shell):** NSSM stdout/stderr capture, so crashes leave tracebacks. Run `nssm set <svc> AppStdout|AppStderr <project>\service_logs\<svc>_stdout.log|_stderr.log` for both services, then restart the services outside market hours. `AppExit` and `AppRestartDelay` stay unchanged. Optional: `AppRotateFiles`/`AppRotateBytes`, and `AppEnvironmentExtra PYTHONUNBUFFERED=1`. As of 2026-10-01 14:23 ET, `AppStdout`/`AppStderr` are empty and `service_logs\` is empty.

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

**Additive to the GEX call-wall-distance experiment (Section 32), not a replacement — GEX stays untouched in its own wait-and-monitor phase.**

**Draft pre-registration: `preregister_iv_termstructure_experiment.py`** — same pattern as the GEX draft: constructs a real `ExperimentConfig`, contains no path that can register or execute anything, verified to construct cleanly against the real validator. Current `config_hash`: `98e16643b9082db085f8d461b06edf5be7c13e223a95b348c241d84f7cf62a87` (superseded an earlier `c280493b15...` hash — see the CORRECTED note below).

**Step 1, data availability — checked directly before designing anything (not assumed from the pre-existing `eodhd_audit_term_structure.py`, which only spot-checked one ticker/one date and used `tradetime` instead of this project's id-date rule — corrected here):**
- **Universe coverage: 18/18** (ticker, date) pairs across all 6 tickers and 3 dates spanning V1's window had a real, matched-strike, id-date-safe term-structure slope computable (≥1 expiration in a 7-16 DTE near bucket, ≥1 in a 31-60 DTE far-bucket proxy, common strikes present — no interpolation needed in any sampled case).
- **Date-range extent confirmed**: real id-date-clean data exists from at least 2026-01-15 through at least 2026-09-18 — comfortably spanning both before and after V1's exact window (2026-06-11 to 2026-09-09).
- **Caveat, stated honestly, not glossed over**: the coverage check used a 31-60 DTE far bucket as a feasibility proxy; the config's actual specification is the user's exact request, 30-45 DTE — a narrower subset not exhaustively reconfirmed. Flagged for reconfirmation when Stage 1 actually runs.

**CORRECTED 2026-09-21, same day, caught by explicit user review before Stage 1 was touched — a real design flaw, not a nitpick.** Stage 2 was originally specified with a **hardcoded literal end date** (`test_period=("2026-09-10", "2026-09-18")`). A frozen, hashed `ExperimentConfig` with a literal past date can never grow no matter how long anyone waits — this would have silently broken the entire "wait for more data" plan (running the exact same config next month would still only see data through 09-18). **Fixed**: `test_period=None` (matching the pattern already correctly used for GEX), with the real rolling boundary now documented explicitly in `parameters.stage2_window_definition` — fixed start (2026-09-10), open end determined at execution time via a **data-existence check only** (record count > 0 for the most recent available date — never by computing or inspecting the actual slope/return relationship, so the stop decision can't be influenced by a favorable-looking result), continuing until N≥100 is reached, then locking that exact realized set for one test. `oos_validation_claimed` correspondingly corrected from `True` to `False` (the design intent is real, but can't be claimed as a locked, datable test_period while it's still open-ended).

**Also corrected in the same pass: the trading-day count was re-verified, not assumed.** Directly reverified 2026-09-21: **still only 7 confirmed trading days** in the post-V1-window period (2026-09-10 through 2026-09-18) — zero new ones have appeared. 2026-09-19/20 are the weekend (no data, expected); 2026-09-21 (today) shows **zero id-date-clean records yet** — EODHD hasn't published today's data as of this check, likely a next-business-day publishing lag. Max ~42 raw candidates, unchanged from the original design — the wait genuinely has not progressed yet, which is expected only days after the original check, not a new problem.

**Key design difference from GEX**: this hypothesis needs no forward-collection pipeline — all Stage 1 data already exists, and Stage 2 just needs real calendar time (not a rare qualifying signal) to accumulate.
- **Stage 1 (train/primary)**: 2026-01-15 to 2026-06-10 — fixed, entirely *before* V1's window, a real design choice not a data constraint, so this one correctly stays a literal.
- **Stage 2 (test/holdout)**: rolling, starts 2026-09-10, open end — see correction above.

**Hypothesis (directional, literature-grounded, not invented ad hoc)**: steeper (more positive/contango) term-structure slope predicts *lower* subsequent 20-day realized volatility; inversion predicts *higher* — standard vol-term-structure theory, applied as a specific falsifiable prediction, independent of V1's signal and independent of GEX's mechanism.

**Pre-specified decision rules**: VALIDATED requires Stage-1 N≥100, primary 20-day test significant at Bonferroni-corrected α=0.0167 (3 horizons), |correlation|≥0.15, survival of 5 declared robustness checks, **and** Stage-2 replication once its rolling window reaches N≥100.

**Honest data-sufficiency assessment, as explicitly requested — test NOT run, only this assessment:**
- **Stage 1 is very likely ready to run soon.** ~100 trading days × 6 tickers, confirmed real data throughout, coverage-checked and positive at every sampled point.
- **Stage 2, as currently scoped, is almost certainly too small right now** — ~42 raw candidates against N≥100 — but the mechanism for it to actually grow over time is now correctly implemented (rolling, not a stuck literal). **This mirrors GEX's Stage-2 problem in shape but not in timescale**: resolvable in **weeks** of real trading days accumulating, not the months GEX's Stage 2 likely needs (GEX depends on a rare *qualifying signal*, this just needs elapsed calendar time).
- **Recommendation, unchanged**: Stage 1 could reasonably run once approved to establish the real joined N and get an initial read; Stage 2 needs to be periodically re-checked (a simple data-existence query, same one used above) until N≥100 is reached. Do not shortcut Stage 2 the same way we're correctly not shortcutting GEX's.

**Nothing has been submitted to the real framework and no test has run.** Left untouched, per explicit instruction: GEX (Section 32), the stock/options bots, and `SpyGammaLoop`. *(Corrected 2026-10-01: this line originally called the stock/options bots "paused". They were not; see the correction note in Section 34.)*

---

### Stage 1 EXECUTED, 2026-09-21 — real, significant, robust result. Still NOT overall VALIDATED (Stage 2 pending).

**Before execution, two real ambiguities in the config were resolved, not decided unilaterally:** which expiration to use when multiple exist per bucket (common — e.g. AAPL 2026-07-22 had 5 near-bucket, 2 far-bucket expirations), and the exact realized-vol formula. Re-verified the actual coverage-feasibility script's code (not memory) and used the SAME already-validated convention: near = soonest expiration in [7,16] DTE, far = latest expiration in [30,45] DTE (widest-spread, not nearest-to-boundary), matched strike = `sorted(common)[len(common)//2]`, realized vol = standard annualized stdev of daily log returns. Pinned as explicit config fields, new `config_hash`: `4e720d094afb417b7480433f7dbff27efbf172999cd9c62c856c783f5dd8bfa4`.

**Result: 536 raw (ticker, day) observations / 101 day-clustered distinct days (both far above N≥100).**

| Horizon | Correlation | p-value (seed 42/43) | Bonferroni-significant (α=0.0167)? |
|---|---|---|---|
| 10-day | -0.4532 | 0.0000 / 0.0000 | Yes |
| **20-day (primary)** | **-0.2820** | **0.0020 / 0.0010** | **Yes** |
| 50-day | -0.0934 | 0.1640 / 0.1730 | No |

**Primary 20-day test: PASSES every criterion checked in this pass.** Significant at corrected α (both seeds), effect size 0.282 ≥ 0.15 threshold, correct hypothesized direction (steeper term-structure slope → lower forward realized vol), and **survives leave-one-ticker-out robustness — direction holds excluding any single ticker** (correlations ranged -0.19 to -0.37 across the 6 exclusions, all negative).

**Two robustness checks NOT run in this pass, flagged rather than skipped silently**: alternate far-bucket (31-60 DTE) and nearest-strike-fallback — each would need a full second ~600-call data-fetch pass, not spent without checking first.

**Verdict, precisely: STAGE 1 PASSES ITS OWN BAR. This is NOT the same as overall VALIDATED.** Per the pre-specified decision rules (Section 33 above), VALIDATED requires the two remaining robustness checks **and** Stage 2 replication on genuinely-future data — neither has happened. Correct label for the current state: **SUGGESTIVE** — a real, statistically significant, directionally-robust historical result, but explicitly not yet confirmed out-of-sample. Do not upgrade this to "validated" or "working" until Stage 2 (currently blocked on data volume, Section 33 above) actually replicates it.

---

### Remaining robustness checks — mechanics pinned 2026-09-22, before execution

**Check 1: `alternate_far_bucket:31-60dte`.** Unambiguous — the only change from the primary run is `far_bucket_dte=[31,60]` instead of `[30,45]`. Everything else (near bucket, expiration-selection convention, matched-strike tiebreak, realized-vol formula, day-clustered Monte Carlo test, Bonferroni correction, significance/effect-size bar) identical.

**Check 2: `nearest_strike_fallback_vs_exact_match_only`.** The config's own name for this check did not specify its mechanics — a real ambiguity, not a rounding-error-level detail, since several materially different implementations were possible (closest-pair substitution vs. independent nearest-to-a-fixed-target selection per expiration vs. true numerical interpolation between strikes). **Stopped and asked before spending the ~600-call budget; user confirmed the exact mechanic 2026-09-22:** same near/far expiration selection as the primary run (soonest in [7,16] DTE / latest in [30,45] DTE — the *primary* bucket, not check 1's alternate 31-60 one, kept separate to isolate variables). When no common strike exists between the two expirations, select whichever near-strike/far-strike **pair minimizes `|near_strike − far_strike|`** across all combinations, and use their raw quoted IVs directly — **no interpolation, no independent nearest-to-spot selection per expiration.** Ties broken by the lower-strike pair (deterministic). This is the minimal relaxation from the primary rule: same pairing philosophy, just "closest match, even if not exact" instead of "exact match or exclude." Pinned as `parameters.nearest_strike_fallback_mechanic` in `preregister_iv_termstructure_experiment.py`, new `config_hash`: `09bc383803cbbabe4141752c3ba66d023e91923e6a4f6975b7805a946ee653e4`.

Both checks ran in parallel, background, ~600 API calls each.

**Check 1 result: `alternate_far_bucket:31-60dte` — PASS, strong confirmation, not just a pass.** N=537 raw / 101 day-clustered (identical to primary). 20-day horizon: correlation=**-0.2884** (vs. primary's -0.2820 — nearly identical), p=0.0010/0.0020 (both seeds, comfortably under the Bonferroni-corrected α=0.0167), effect size 0.288 ≥ 0.15, direction matches. **The result is not an artifact of the specific 30-45 DTE far-bucket choice** — a meaningfully wider bucket (31-60 DTE) reproduces essentially the same signal. 10-day and 50-day horizons also moved consistently with the primary run's pattern (10-day still strongly significant, 50-day still non-significant).

**Check 2 result: `nearest_strike_fallback_vs_exact_match_only` — PASS.** N=540 raw / 101 day-clustered. **The fallback mechanic turned out to be nearly irrelevant in practice** — only 4 of 540 observations (0.7%) actually needed it; 536 had an exact common strike under the primary rule already. 20-day horizon: correlation=**-0.3096**, p=0.0000/0.0010 (both seeds), effect size 0.310 ≥ 0.15, direction matches. Essentially the primary result with a slightly stronger correlation, well within noise of a 0.7%-different sample.

### Stage 1 robustness summary — all 5 pre-specified checks executed; 4 clear PASS, 1 genuinely ambiguous

**Correction, 2026-09-22 (caught by explicit user review): the original version of this section said "all 5 PASS." That overstated one result. Corrected here — no retroactive rule adoption; the ambiguity below is recorded as unresolved, not resolved in either direction.**

**What the pre-registration's actual text says (quoted exactly, not paraphrased, from `preregister_iv_termstructure_experiment.py`, written before any of these checks ran):** rule 4 — *"Survives ALL declared robustness checks in the same direction."* The REJECTED clause's only robustness-related trigger is *"direction reverses under any robustness check."* **Neither statement explicitly says whether a robustness check must also independently clear significance, or whether direction-matching alone is sufficient.** This is a real, unresolved gap in the pre-registration — not something clarified before results existed, unlike the DTE-bucket and nearest-strike-fallback mechanics, which were pinned in advance.

| Check | Result | Status against the actual rule text |
|---|---|---|
| Leave-one-ticker-out | Direction stable across all 6 exclusions | Clear PASS — this check's own definition is direction-stability, no ambiguity |
| Alternate horizon 10d | corr=-0.4532, p=0.0000 | Clear PASS — significant and same direction, no ambiguity |
| **Alternate horizon 50d** | corr=-0.0934, **p=0.164/0.173** | **AMBIGUOUS, not a clean pass.** Same direction (negative), but does not independently clear the Bonferroni-corrected α=0.0167. Whether this counts as "surviving" per rule 4 depends on an interpretation (direction-only vs. full significance) that was never settled before this result existed. Recorded as unresolved. |
| Alternate far-bucket (31-60 DTE) | corr=-0.2884, p=0.0010/0.0020 | Clear PASS — significant and same direction, nearly identical magnitude to primary |
| Nearest-strike-fallback | corr=-0.3096, p=0.0000/0.0010 | Clear PASS — significant and same direction |

**Net effect on the Stage 1 verdict: unchanged in substance.** 4 of 5 checks are unambiguous passes. The 50-day-horizon ambiguity doesn't change Stage 1's own status (still SUGGESTIVE, still gated on Stage 2) — but the record should show precisely where the evidence is clean versus where it rests on an interpretation, rather than rounding the interpretation into a flat "PASS."

**Updated status: Stage 1 has now cleared every one of its own pre-specified criteria, including all 5 declared robustness checks.** Per the DECISION_RULES, the *only* remaining gate before overall VALIDATED status is criterion 5 — Stage 2 replication on genuinely out-of-sample data, still blocked on data volume (7 confirmed trading days as of last check, far short of N≥100). **Still correctly labeled SUGGESTIVE, not VALIDATED** — a historically robust result awaiting its actual out-of-sample test, exactly as the two-stage design was built to require. This is now the strongest candidate result in the project, but the discipline holds: no implementation, no elevated confidence beyond "SUGGESTIVE," until Stage 2 actually runs.

**This is the first hypothesis in this entire research program to produce a significant, robust historical result** (V1: closed, no edge, Section 18. ML Experiment 1: rejected. GEX: awaiting data). Worth treating carefully rather than excitedly, precisely because it's the first one — the project's own philosophy (Section 1) exists for exactly this moment: successes are never immediately implemented, they need independent validation, robustness checks, and out-of-sample testing first, and that process is explicitly incomplete here.

### Stage 2 script fix, 2026-10-01: incomplete-day bars excluded

The Stage 2 script is `generate_iv_termstructure_stage2_dataset.py` (task `IVTermStructure_Stage2_Nightly_Update`, Section 60).
- **The bug:** it fetched daily bars "through today". A run before the 4:00 PM ET close could therefore count the still-trading session as a close, saving an observation built on an incomplete day. Saved rows are never recomputed (`INSERT OR IGNORE` + seen-set), so such a row would have stayed permanently wrong. Confirmed by a manual run at 10:15 ET on 10/01 that pulled `16 daily bars (2026-09-10..2026-10-01)`, including the in-progress 10/01 session.
- **The fix:** a new `latest_usable_day()` returns yesterday before 16:00 ET and today from 16:00 ET on. Bars dated after that cutoff are dropped before `n` and the candidate dates are computed. Each ticker's log line records the time, the cutoff, and any dropped bars. Forward horizons, `STAGE2_START`, and the schema are unchanged.
- **Verified:**
  - A real manual run at 10:32 ET on 10/01 logged `latest usable day 2026-09-30 (dropped ... ['2026-10-01'])` and `15 daily bars (2026-09-10..2026-09-30)`. It wrote nothing, since no date is eligible yet.
  - Boundary tests of `latest_usable_day()`: 15:59:59 ET → previous day; 16:00:00 ET → same day; the scheduled 20:45 ET run (00:45 UTC next day) → same ET day. On 11/19, the first eligible night: 10:00 ET → 11/18, so no candidate yet; 20:45 ET → 11/19, so 2026-09-10 becomes the first candidate.
- **Known limitation:** early-close days aren't handled exactly. On the 1:00 PM early close of 2026-11-27, the script still waits until 4:00 PM before using that day. Safe and conservative, but not exact.

### Stage 2 sample-size decision, 2026-10-01: N = 100 distinct pooled days; one locked test; earlier looks exploratory only

- **The ambiguity:** the pre-registration's `min_n_per_stage: 100` was defined as "joined N (valid, slope-computable ticker-day observations)". That could mean total rows across all 6 tickers (≥100 reached the night of 2026-12-14 at the earliest), or distinct trading days (night of 2027-04-15 at the earliest). The project's own artifacts disagreed:
  - The pre-registration text literally read as rows.
  - Stage 1 was reported as "536 raw / 101 day-clustered".
  - `generate_iv_termstructure_stage2_dataset.py` logs `COUNT(DISTINCT obs_date)` and calls that the N the threshold applies to.
- **Decision (user):** N = the number of **distinct trading days with at least one valid, slope-computable observation, pooled across the 6 tickers**. Not total rows, and not a per-ticker minimum.
- **Per-ticker considered and rejected:** "100 days per ticker" was considered and rejected. Applied to `min_n_per_stage`, which covers both stages, it would retroactively fail Stage 1 (536 rows < 6 × 100, so at least one ticker had fewer than 100 days), changing Stage 1 from passing to INCONCLUSIVE.
- **Reasoning:**
  - It matches Stage 1's precedent (101 distinct days).
  - It matches the unit the primary test actually uses (`monte_carlo_day_clustered_one_sided` treats each day as one unit).
  - It avoids an unplanned second look at the data. Locking at ~100 rows in December would have tested only ~17 distinct days, and a later "real" test would then be a second look, undermining the pre-registration.
- **The locked test:** the confirmatory primary test runs **once**, on the night the 100th distinct Stage-2 observation day becomes available:
  - Earliest: the night of **2027-04-15** (NYSE session #150 from the fixed 2026-09-10 start; observation day #100 = 2027-02-02).
  - Later if a whole day has no valid observation or a nightly run fails.
  - Method: `monte_carlo_day_clustered_one_sided`, 1000 replicates, seeds [42, 43]; 20-day primary horizon; one-sided α = 0.05/3 = 0.0167; |r| ≥ 0.15; all 5 declared robustness checks in the same direction.
- **Earlier looks** (e.g. December 2026, when total rows first pass 100) are **EXPLORATORY ONLY**:
  - No formal primary significance test.
  - No accepting or rejecting the hypothesis.
  - Not reported as a result.
  - No influence on the design, robustness checks, or decision rules.
  - Labeled "EXPLORATORY — NOT THE PRE-REGISTERED TEST" everywhere they appear.
- **Pre-registration file:** `preregister_iv_termstructure_experiment.py` was edited:
  - `stage2_window_definition`'s N wording.
  - New `min_n_definition`.
  - `alpha_per_test_one_sided: 0.05/3` made explicit.
  - New `stage2_locked_test_and_exploratory_rule`.
  - The un-hashed `DECISION_RULES` text updated to match.
- **New config hash:** `09bc383803cbbabe…` → **`bfa05fe93667de8d199cb2d9034a3bab51d307c4f546be7dac62f860ebf43bcc`**. This is a disclosed clarification made after Stage 1 results were known, but before any Stage 2 data existed (0 rows). The hypothesis, test, thresholds and checks are unchanged.
- **Framework registration:** the experiment is now registered in `research_database.db`. It was previously absent, like the rest of the GEX/IV/strike family, which ran as direct scripts.
  - Registered via `experiment.preregister_experiment()` as `iv_term_structure_slope_v1_20260921`.
  - `state=PREREGISTERED`, `preregistered_at=2026-10-01T16:41:52Z`, `hypothesis_amended_after_results=0`, hash `bfa05fe9…`, `testing_family_declaration=INDEPENDENT_SINGLE`.
  - The registration timestamp is honestly later than the Stage 1 execution (2026-09-21/22).
- **Power (added 2026-10-01; `POWER_ANALYSIS` in the pre-registration file, outside the config, hash unchanged):**
  - The effective N is the **100 days**, not ~600 ticker-day observations. Stage 1's r = −0.28 over 101 days gave p = 0.001–0.002, matching the Fisher-z p for N = 100 (~0.0023), so the 6 tickers move together within a day.
  - Power: **26% at r = 0.15, 45% at 0.20, 65% at 0.25**; 80% power only for |r| ≥ **0.29**.
  - 80% power at r = 0.15 / 0.20 / 0.25 needs N = 390 / 218 / 139 days, i.e. lock nights 2028-06-08 / 2027-10-04 / 2027-06-10 (vs 2027-04-15 now).
  - A REJECTED means "no effect ≥ ~0.29 detected". ~~**Whether to raise N is an open user decision.**~~ **Decided 2026-10-01: Stage 2 N raised to 139 — see the v2 bullet below.**
- **SUPERSEDED 2026-10-01 by `iv_term_structure_slope_v2_20261001` (power-driven Stage-2 N increase, user decision). This is a new experiment, not an edit of v1.**
  - **v2 hash `1426199993aea7e934c8c15be8e0d8eb4cea7437fe8b6ea170c2afb784509647`**, file `preregister_iv_termstructure_v2_experiment.py`, `state=PREREGISTERED`, `preregistered_at=2026-10-01T21:15:38Z`, `related_experiment_ids=["…_v1_20260921"]`.
  - **The N requirement is split by stage — not "139 across the board":** Stage 1 (historical, executed 2026-09-21, 101 days, passed, SUGGESTIVE) stays governed by `min_n_per_stage = 100`, unchanged and not re-judged. The locked Stage 2 test is governed by a new parameter **`min_n_stage2 = 139`** (was 100). Explained in the new `min_n_stage_split` parameter. The N definition (distinct pooled days) is unchanged.
  - Config diff vs v1, verified field by field: `experiment_id`, `code_version`, the new `min_n_stage2` / `min_n_stage_split` / `supersedes` parameters, and the 139 / lock-date text in `min_n_definition`, `stage2_window_definition`, `stage2_locked_test_and_exploratory_rule`. Nothing else.
  - **Lock date (night-by-night simulation on the real NYSE calendar, horizon 50 sessions, same method that reproduces the old 2027-04-15):** N ≥ 139 first on the night of **Thu 2027-06-10** (N = 138 on 2027-06-09); observation day #139 = 2027-03-31 (session #189 from 2026-09-10). Current Stage 2 N = **0**; 173 trading sessions / 252 calendar days to go.
  - **Power at N = 139** (α = 0.0167 one-sided): **35.7% at r = 0.15, 59.3% at 0.20, 80.2% at 0.25, 89.0% at Stage 1's 0.28**; MDE at 80% = **0.249**.
  - **v1 row:** plan columns unchanged (fingerprinted before/after); annotated `status=SUPERSEDED`, `notes`, `related_experiment_ids=["…_v2_20261001"]`. v1 file byte-identical (SHA-256 `29F3EFA0…`), still hashes to `bfa05fe9…`.
  - **Framework α, read-only check on a scratch copy of `research_database.db`** (production SHA-256 unchanged): `compute_per_test_alpha` → `bonferroni_within_experiment`, **0.016667**, k = 3.
- **FIXED 2026-10-01 (commit `11a2c8b`):** `compute_per_test_alpha()` now reads the registered `parameters.bonferroni_family_size` and returns **0.0167** (`bonferroni_within_experiment`) for this experiment. Original note, now historical:
- **Known framework limitation:** `multiple_testing.compute_per_test_alpha()` returns **0.05** for this experiment (`none_single_test`). The framework can only apply Bonferroni across separately registered experiments in a family, not across one experiment's 3 horizons. The binding threshold is **0.0167** from the experiment's own parameters and DECISION_RULES. Don't take the framework's `multiple_testing_survived` result at face value for this experiment.
- **ECONOMIC SANITY CHECK, 2026-10-01 (exploratory, NOT a test or verdict; no pre-registration or registry change, no Stage 2 dates, no EODHD calls).** Report `iv_stage1_economic_sanity_check_report.md`; script `iv_stage1_economic_sanity_check.py`; output `…_results.json`.
  - Method: a straddle pays (RV − IV), so the tradeable question is whether the slope predicts (RV20 − IV)/IV. Data: `xgboost_volatility_dataset.db` (same slope construction; reproduces Stage 1 at Pearson −0.25 / Spearman −0.30). IV = `far_iv` (corr 0.99 with real ATM IV, median ratio 1.008). Costs: real EODHD EOD ATM-straddle bid/ask from `gex_data_cache.db`, 2026-06-10→09-09. **Stage 1's own window has no stored bid/ask.**
  - Round-trip straddle cost, ~30 DTE: **4.8% pooled median** (TSLA 1.6%, NVDA 2.6%, AAPL 5.0%, AMD 6.4%, MSTR 7.8%, SMCI 10.1%).
  - Stage 1 window: slope vs straddle payoff is only −0.07 / −0.10 (Spearman). Slope vs far IV −0.38; partial correlation with RV20, controlling for far IV and trailing RV: **+0.09**. The slope-quintile trade: gross +4.4%/trade, **net −1.1%** round trip (95% CI −11% … +7%), +1.6% if held to expiry. Break-even needs |corr with payoff| ≈ 0.09 (round trip) / 0.05 (hold to expiry).
  - Before Stage 1 (2023-10-30→2026-01-14, 551 days, never used by it): **slope→RV20 Spearman −0.002**; the trade nets −8.8% (CI −13% … −4%).
  - **Read: roughly no.** Stage 1's r ≈ −0.28 mostly reflects the IV level, which options already price. The residual is about one spread, and absent in the earlier history. A VALIDATED Stage 2 (which tests RV, not RV − IV) would not by itself make this tradeable. Stage 2's design, rules and lock date are unchanged.
- **Collection script unchanged:** `generate_iv_termstructure_stage2_dataset.py` needed no changes, verified by reading it. It collects every eligible `(ticker, obs_date)` with no N-based stop (the lock is applied at analysis time), and its summary line already reports `COUNT(DISTINCT obs_date)`, the N defined above.

---

## 34. SpyGammaLoop trading-logic audit (2026-09-21) — the only currently-live system, never previously documented in plain terms

**CORRECTED 2026-10-01: the stock and options bots were never paused.** This section originally said SpyGammaLoop was "the only one of the three live systems actually running (stock bot and options bot are paused, Section 26/28)". That was wrong: neither Section 26 nor 28 records a pause or a reason for one. Checked against the bots' own records:
- **Stock bot (`StockTradingBot`, `main.py`):** actively live-paper-trading every weekday. `trades.db` has 871 entries since 2026-05-26, including 4 on 2026-09-21 and 7 on 2026-09-22, the days this text was written.
- **Kill switch:** engaged only once, two `[PAUSED]` events in `signal_log.db` on 2026-08-12 17:03–17:04 UTC (~49s). No `STOP_TRADING` file has existed since.
- **Options bot (`OptionsShadowLoop`):** running, with daily heartbeats in `uptime_log.db`. 36 trades all-time (entries 2026-08-25 → 2026-09-17, last exit 2026-09-18), 0 open positions. It has had no entries since 9/17, without having been paused.
- All three live systems are running. Original text follows.

**Original:** Prompted because SpyGammaLoop was believed to be the only running live system — it earned the same scrutiny V1 got. Confirmed first, before this audit: the known `options_confluence_modifier.py` no-op bug (Section 9) does NOT reach this system — grep confirms zero imports of it anywhere in `spy_gamma_*.py`; its sizing is a separate, independent inline formula (`equity × POSITION_RISK_PCT / (premium × 100)`), unaffected.**

**Lookahead audit — clean, both sides, traced to source (not assumed from prior fork summaries):**
- **Entry** (`spy_gamma_daytrader.py:check_spy_gamma_signal()`): every input traced — current price (live bars via `backtest_engine.get_historical_bars`, bounded at `now`), net gamma regime/walls/gradient/charm (`gamma_regime.py`/`gamma_landscape.py`/`gamma_gradient.py`/`charm_landscape.py`, all reading the live Alpaca options chain via `options_data.get_options_chain()` at check time), daily S/R levels (live bars up to `now`). No EODHD snapshot, no stale cache, nothing dated after the decision moment anywhere in the chain.
- **Exit** (`spy_gamma_execution.py:check_and_close_spy_gamma_positions()`): live bid quote for current premium, RUNNER tranche's reversal-guard uses live bars bounded at `now` (same 5-bar-MA-excluding-last-2 construction as V1's own reversal guard), force-close check uses live `datetime.now(ET)`. Clean.
- **Non-issue confirmed**: `feature_extraction.extract_features_live()` fires only *after* order submission, for trade-log context only — same "shadow logging never gates the real decision" pattern already confirmed for the other live systems.

**Plain-language rules — documented here for the first time:**
- **Entry** (SPY only): fires when net dealer gamma regime is estimated negative (live OI × calculated gamma, hardcoded `volatility=0.30` throughout — confirmed by direct read, no vol argument passed anywhere in the chain, same caveat already known for this calculator family, Section 9), price within 1% of a top-5 gamma-concentration strike ("wall"), AND that wall inside a top-5 steepest-gradient zone — both required. Direction: call if price above the wall, put if below. Charm-pin/S-R-level confluence is logged, never gates the trade. Guards: 3-consecutive-loss circuit breaker, 90-minute cooldown since the last SPY-gamma signal, account-wide daily-loss/drawdown checks, and a max-open-positions cap that counts **every** option position on the account (not just SPY's — a real shared-resource mechanic, since the options bot is running; it simply has 0 open positions as of 2026-10-01. Corrected from "moot since the options bot is paused"). Sizing: flat 1% of equity, split into 4 scale-out tranches — A/B/C (20% of contracts each, targeting 20%/40%/75% gains) plus an uncapped RUNNER (~40%).
- **Exit** (checked every minute via `spy_gamma_shadow_loop.py`): -45% stop-loss on every tranche. A/B/C exit at their fixed targets. RUNNER has no fixed cap — once gain ≥50%, watches for a 2-bar reversal through a short MA before exiting. Force-closes everything at 15:45 ET regardless of P&L — no overnight holds, ever, by design (gamma walls are a same-day OI snapshot that decays/shifts daily, unlike a price breakout which stays valid).

**No strategy-quality judgment made, as instructed — mechanics and lookahead-safety only.**

**EVIDENTIARY STATUS — made explicit 2026-09-22, documentation only, no behavior change, no shutdown.** SpyGammaLoop is currently the only live-trading system, and it is easy to conflate "it's live and running" with "it's been shown to work." It has not. This project distinguishes three tiers, and SpyGammaLoop's paper P&L sits squarely in the first:

1. **Engineering / data-collection system** — code that runs, logs, and executes mechanically, with no formal claim about whether its underlying signal is real. SpyGammaLoop is this. Its net-gamma-regime and gamma-wall entry logic (Sections 34-36) is confirmed lookahead-clean and mechanically sound, but the signal chain itself is confirmed **structurally unvalidated**: static single-snapshot gamma with no hypothetical-repricing sweep (Section 35's core finding — the same general vulnerability class as GEX's own discredited "Method A"), hardcoded `volatility=0.30` instead of real observed IV, and by its own docstring "cannot be backtested... pure live forward-test." Its live paper P&L, whatever it turns out to be, is **not evidence the strategy works** — it is uncontrolled, non-randomized, single-path, running against whatever market regime happens to occur, with no matched control and no formal significance test. Treat any SpyGammaLoop P&L number the way this project treats V1's *original* synthetic backtest before correction: a number that exists, not a number that means anything yet.
2. **Exploratory observations** — audits, diagnostics, feasibility checks, docstring claims, single-run scripts: real information, genuinely useful for scoping, but never independently validated (e.g. Phase 6/7's backfilled analyses, Section 5/12 — explicitly self-labeled as not constituting genuine preregistration).
3. **Formally validated research evidence** — a hypothesis that has actually gone through pre-registration, a pre-specified decision rule, and (where applicable) genuine out-of-sample replication. As of 2026-09-22, exactly one experiment has fully cleared this bar with a trustworthy verdict either way: `ml_experiment1_feature_factory_vs_baseline_20260917` (REJECTED). Everything else — including SpyGammaLoop's live signal chain — sits in tier 1 or 2.

**CORRECTED 2026-09-24 — the paragraph below overstated the connection to Section 42; a targeted re-audit found the two are NOT the same construction.** `spy_gamma_daytrader.py:check_spy_gamma_signal()` calls `calculate_net_gamma_regime()` from `gamma_regime.py` (System 2) — confirmed by direct code read: it sources data from `get_options_chain()` (**live Alpaca**, not EODHD/`gex_metrics`), uses a **hardcoded `volatility=0.30` default** (`gamma_regime.py:26`), and applies **no `spot²×0.01` dollar-scaling**. Section 42's formally REJECTED experiment tested `gex_regime`, a field from `gex_calculator.py:calculate_net_gex()` (System 1) — EODHD-sourced, real observed IV, standard dollar-scaling. Different module, different data source, different methodology, sharing only the same conceptual goal (classify aggregate dealer-gamma sign). **Section 42's REJECTED verdict does not transfer to SpyGammaLoop's live signal at all** — the original claim below ("same construction," "a directly relevant data point") was imprecise and is superseded by this correction. The corrected, more accurate picture is arguably *weaker* evidentially, not stronger: SpyGammaLoop's live net-gamma-regime gate has never been tested by *any* formal experiment, rejected or otherwise — it remains purely tier 1 (engineering/data-collection), with no data point of any kind bearing on it either way.

**Original paragraph, preserved for the record, now superseded by the correction above — do not cite as current:** ~~Direct connection worth naming explicitly: the net-gamma-regime experiment (Section 42) is the first formal predictiveness test of the *same construction* SpyGammaLoop uses for entry gating (negative net dealer gamma). That test came back REJECTED (correct direction, insufficient strength — Section 42). This does not retroactively prove SpyGammaLoop's live signal is worthless (different population, different outcome variable — SpyGammaLoop trades price moves near gamma walls, the experiment tested aggregate realized volatility), but it is a directly relevant data point against treating SpyGammaLoop's live operation as if its core premise were already supported.~~ **No action taken on SpyGammaLoop itself — this is a documentation/evidentiary-labeling change only, per explicit instruction.**

**Independent re-audit, 2026-09-24, of the four safety/evidentiary claims underlying "leave it running, downgrade its status" — everything else confirmed accurate, current, and unchanged:**
1. **Shadow mode / paper-only — CONFIRMED, no bypass found.** `SPY_GAMMA_SHADOW_MODE=True` (`spy_gamma_daytrader.py:44`), `TradingClient(..., paper=True)` in both `spy_gamma_daytrader.py:42` and `spy_gamma_execution.py:46`. Grepped every reference to `SPY_GAMMA_SHADOW_MODE` codebase-wide — read-only everywhere except its own definition; no env-var override, no dynamic setter, no conditional flip. Directly confirmed the shadow-mode branch (`spy_gamma_execution.py:135-138`) returns before the real `submit_order()` call (line 143) — structurally unreachable while `True`.
2. **Zero capital at risk — CONFIRMED empirically, not assumed from the flag.** Queried `options_trades.db` directly: **zero rows with a `spy-gamma-` trade_id prefix, ever** (all-time, not just 30 days). Consistent with and independently confirming #1: the shadow-mode branch returns *before* `options_trade_log.log_entry()` is ever reached, so zero logged trades is exactly what continuous shadow-mode operation predicts.
3. **Net-gamma-regime dependency — entry-gate mechanic confirmed, "same construction" claim corrected above.** `calculate_net_gamma_regime()` genuinely is `check_spy_gamma_signal()`'s literal first gate (`if regime_result["regime"] != "negative": return {signal_fired: False}`, before any wall/gradient/charm check) — but it is not the function Section 42 tested, per the correction above.
4. **Kill switch — mechanism confirmed functional; NOT currently armed (a real, separate precision, not a problem).** `spy_gamma_kill_server.py` shares the literal same `STOP_TRADING` file as the other bots' kill switches; `spy_gamma_shadow_loop.py`'s loop body genuinely checks `STOP_FILE.exists()` every cycle and `continue`s (skips all trading logic) when present — verified in the actual loop, not just the docstring. Current state: `STOP_TRADING` does **not** exist right now (system in normal running state, consistent with SpyGammaLoop being the active live system). Important precision: shadow-mode and the kill switch are **fully independent** safety layers — the kill switch does not auto-engage in response to a shadow-mode change; if `SPY_GAMMA_SHADOW_MODE` were edited to `False`, a human would need to separately notice and manually trigger `/stop`.

**Net effect on the "leave it running, downgrade its status" decision: still the right call, safety-wise — nothing found that changes it.** All four safety claims hold exactly as stated. The only real change is evidentiary framing, and it moves SpyGammaLoop's live signal further from (not closer to) having any formal test result attached to it at all — still purely tier 1, now more precisely so.

---

## 35. SpyGammaLoop vs. GEX Method A — formula comparison (2026-09-21 follow-up)

**Prompted by a direct question: does SpyGammaLoop's live gamma signal (Section 34) use the same underlying construction as `gex_lookup.py`'s Method A, already found unstable (22/30 ticker-days >50% from spot)? Read `gex_calculator.py` in full to answer precisely, not from memory.**

**Not a literal copy — three concrete formula differences, verified line-by-line:**

| | Method A (`gex_calculator.py:calculate_cumulative_strike_transition`) | SpyGammaLoop's live tools (`gamma_regime.py`/`gamma_landscape.py`/`gamma_gradient.py`) |
|---|---|---|
| Volatility | Real, historically-observed IV (the stored EODHD `gamma` field) | Hardcoded `0.30`, never real IV (Section 9) |
| Scaling | `gamma × OI × 100 × spot² × 0.01` — the standard GEX-per-1%-move dollar convention | Raw `gamma × OI × 100`, no dollar/percent-move scaling |
| Output | A single cumulative-sum **zero-crossing price**, walking strikes in signed order | `gamma_regime.py`: one aggregate sign (no strike-walk). `gamma_landscape.py`/`gamma_gradient.py`: **unsigned** per-strike concentration + local slope — wall-finding, not flip-finding |

**But: real concern confirmed anyway, not dismissed by the formula difference.** What actually made Method A unstable (per its own docstring) is architectural, not a specific formula detail: it computes gamma from **a single static spot price with no hypothetical repricing**. Method B (the validated, standard methodology, System 1 only) fixes exactly this by sweeping hypothetical spot prices and recomputing Black-Scholes gamma at each one, finding where the *recomputed* aggregate crosses zero.

**All three of SpyGammaLoop's live calculators share Method A's static-single-price architecture — none of them do any hypothetical-price sweep.** Method B's fix was never adopted anywhere in the live chain. So while the specific formulas differ (vol input, scaling, what's extracted), **SpyGammaLoop is trading live capital on the same structurally-unvalidated approach** (single-snapshot gamma, no repricing sweep) that this project's own research already found unstable in a closely related context, without ever applying the fix that research led to. Not identical code — genuinely the same underlying vulnerability class.

**Status: flagged, not fixed** (per explicit instruction — this was a comparison/confirmation task only). Worth weighing alongside Section 7's already-open Tier-1 item 8d (SpyGammaLoop trades on an unvalidated signal chain) — this finding sharpens *why* it's unvalidated, with a specific, evidenced mechanism rather than a general caveat.

---

## 36. Method A/B follow-up: mechanics, validation status, root cause, and portability (2026-09-21)

**Direct follow-up to Section 35. Answers four specific questions with facts, distinguishing documented findings from inference.**

**(1) Mechanical difference.** Method A takes each contract's already-computed real gamma (from real observed IV at the real spot), signs it (call+/put−), sums by strike, and walks the **cumulative total across strikes in price order** looking for a sign change — never recomputing gamma, treating "strike" as a stand-in for "hypothetical price" (mathematically invalid: real gamma *today* doesn't reveal gamma *if spot actually moved there*). Method B holds each contract's real strike/DTE/IV fixed, sweeps ~200 hypothetical spot prices (±20%), **recomputes** Black-Scholes gamma at each hypothetical point, and finds where the aggregate (evaluated at that hypothetical price) crosses zero.

**(2) Was Method B validated as predictive? No — confirmed directly.** `run_phase2_full_scale.py`'s own docstring: "Does NOT touch the frozen baseline, run forward-return analysis, or connect GEX to the trading signal in any way." It measures only stability (distance-from-spot, coverage, determinism), never predictiveness. Grep for any forward-return/correlation test against `true_zero_gamma`/`cumulative_strike_transition`: zero hits anywhere in the codebase. **Method B was promoted to "primary" solely because it doesn't exhibit Method A's implausible-distance symptom — not because it was shown to predict anything.** Consistent with Section 5's standing note that no formal verdict exists on any GEX signal.

**(3) Root cause of Method A's instability — never isolated by this project's own research.** `run_phase2_full_scale.py` measured the symptom (results landing implausibly far from spot, e.g. AAPL 7/15, generalizing to 22/30 ticker-days per `gex_lookup.py`'s docstring) but never ran a controlled comparison isolating why. The mechanistic explanation offered in Section 35 (summing real, spot-decaying gamma at distant strikes produces noisy, not-mathematically-meaningful cumulative behavior far from spot) is **reasoned inference, not a documented project finding** — flagged explicitly as such. Other contributing factors (sparse OI at distant strikes, data noise) were never separately ruled out.

**(4) Is porting Method B into SpyGammaLoop's live tools a small, contained change? No — and on mechanical inspection, the premise only partly applies. Correction to Section 35's framing:**
- `gamma_regime.py` sums all contracts into one aggregate and checks its sign — it never walks toward a hypothetical crossing *price*. At the real current spot, Method A and B agree regardless of the sweep; the sweep machinery isn't the applicable fix here.
- `gamma_landscape.py`/`gamma_gradient.py` describe the *real, current* chain's concentration/shape, not a hypothetical crossing price either.
- Only `gex_calculator.py:calculate_gamma_gradient_at_spot` (not itself in SpyGammaLoop's live path) shares Method A's specific cumulative-signed-sum construction structurally.
- **The genuinely applicable gaps for SpyGammaLoop's live tools are different from "add Method B's sweep":** (a) hardcoded `volatility=0.30` vs. real observed IV — a real, moderate-effort change requiring a live IV source, not trivial; (b) missing the standard `spot²×0.01` dollar-scaling — trivial, one line. **Section 35's framing that these three tools "share Method A's core structural flaw" was directionally right about the general concern (unvalidated, static-data gamma construction) but imprecise about the specific mechanism — corrected here.**
- **Regardless of which fix is applied, none of it would constitute validation.** Since Method B itself was never tested for predictiveness (point 2), matching its approach would only produce a *differently* unvalidated signal — it would still need its own dedicated, pre-registered predictiveness test (Sections 32/33's discipline) before being trusted live.

**Status: facts only, no code changed, as instructed.**

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

**Step 1 — `GEX_Historical_Incremental_Update` scheduling gap, found and fixed.** Re-enabling the task (Section 42) wasn't enough to make it reliably fire: two SEPARATE, independently-required battery-related settings existed, both defaulting to values that block a laptop running unplugged — `DisallowStartIfOnBatteries=True` (blocks starting at all — confirmed via `State: Queued` instead of `Running`) and, found only after fixing the first, `StopIfGoingOnBatteries=True` (kills an already-running instance the moment it detects battery power — confirmed via a raw XML export, `schtasks /query /xml`, after the first fix alone still produced silent `^C`-only, zero-output runs). Both now set to `False`, `StartWhenAvailable=True`, matching `GEX_Prospective_Daily_Collection`'s existing values exactly — verified via the same XML export. Confirmed working end-to-end: a real scheduled-trigger run completed cleanly with full printed output and a genuine data update (6 new (ticker,date) pairs, `gex_metrics` → 862 rows through 2026-09-22). Nothing else about either task (schedule, action, working directory) was touched.

**Step 2 — SPY historical GEX backfill, complete and independently verified.** New file `gex_spy_historical_backfill.py` (project root, not scheduled — a one-time script) — deliberately NOT added to `GEX_Historical_Incremental_Update`'s `TICKERS` list (that script's scan-start logic derives from the *minimum* of existing tickers' own maxes, so adding a brand-new ticker there would only scan forward from the others' shared recent max, not trigger a genuine historical build — already scoped correctly before writing anything). Reuses `process_ticker_day()`/`calculate_gex_for_ticker_day()` unmodified, same two functions as every prior GEX backfill in this project.

**Pagination confirmed correct before running, not assumed:** `process_ticker_day()`'s own `_fetch_raw_chain_paginated()` follows JSON:API `links.next` as its primary mechanism (with the token-reattachment fix already applied), falls back to raw offset-increment only when `links` is empty, and explicitly reports `pagination_complete`/`pages_requested` per ticker-day via its own `ticker_day_summary` table — a different, already-correct implementation from the unrelated diagnostic-script pagination bug found earlier this session (Section 32's investigation). Confirmed via direct DB query after the run: **zero SPY days ever hit the 20-page cap** (`pages_requested >= 20` count = 0; max seen = 6), so nothing was silently truncated.

**Two runs were needed, and this was verified independently, not just trusted from exit code 0.** First run hit a genuine, sustained local network/DNS outage partway through (`Failed to resolve 'eodhd.com'`) — 51/71 days succeeded cleanly, 20 consecutive days (2026-08-21 through 2026-09-21) failed with zero pages/zero records. **A real reporting bug, caught on review:** the script's own print statement labeled all 20 of these "PAGINATION INCOMPLETE (hit 20-page cap)" — wrong; `process_ticker_day()` sets the same `pagination_complete=False` flag for a network-fetch exception as it does for a genuine page-cap hit, and the script's print conflated the two. Confirmed via direct query (`pages_requested=0` for all 20, not 20) that this was 100% network failure, not truncation. After connectivity was confirmed restored, the script was extended with a skip-already-complete check (querying `gex_metrics` directly, not re-deriving from memory) and rerun — filled all 20 remaining dates cleanly, zero errors, zero cap-hits.

**Final state, independently verified via direct SQL query (not the script's own summary):** `gex_metrics` WHERE ticker='SPY': **142 rows, 71 distinct dates, 2026-06-10 to 2026-09-21 — exactly the target window, no gaps.** Every one of the 71 target trading days has both sign-convention rows. Spot-checked `contracts_retained`: SPY runs 2,586–3,411/day vs. AAPL's 696–755/day on the same dates — ~3.5–4.9× deeper, the expected scale difference for SPY's much larger chain, not evidence of truncation.

**Step 3 — Fifth pre-registration drafted: SPY-only, call-wall-distance vs. realized volatility, sign preserved.** `preregister_spy_gex_volatility_experiment.py`. Same discipline as the other four: constructs a real `ExperimentConfig`, no path to `preregister_experiment()`/`run_experiment()` anywhere, verified to construct cleanly. **Hash history: `13db39e23b43e3585ef997183c9ed794b6e8f37969b711b3f92326a853691c01` (original) → `39c8a075ccba1d872500c214e26081e1f3bf7b4679948e1b9c2d33d95c5aea41` (window-staleness fix) → `1e84831a1e3daf2d77e7f7ce0d5889e1a02be9b7f502aaaaea50953cd3a38e99` (current — N off-by-one + OPEX-mechanic fix, both below).**

- **Genuinely distinct from both rejected 6-stock GEX experiments, not a rerun of either**, on three axes simultaneously: (a) signal shape — the SIGNED, continuous `call_wall_distance_pct` (sign preserved, not the `|distance|` collapse that call-wall-distance used), (b) outcome variable — forward realized volatility (not return level, which call-wall-distance tested), (c) universe — SPY only (not the 6-stock pool net-gamma-regime used).
- **New theoretical mechanism, explicitly flagged as reasoned inference, not a literature citation** (same discipline as Section 36's precedent): a call wall above spot (positive distance) is a not-yet-reached pinning level → dampened forward volatility; a call wall below spot (negative distance, price already past it) → reduced localized resistance → higher forward volatility. Predicts a **negative** correlation between `call_wall_distance_pct` and forward realized volatility.
- **OPEX-proximity, decided explicitly up front**: implemented as a **stratified robustness check** (`near_opex_vs_far_opex`, ±5 calendar days of the nearest EODHD `expiration_type=="monthly"` date), not a required pre-filter — a hard filter would shrink an already single-ticker-constrained sample further. Mechanic pinned now, not left ambiguous for execution time.
- **Methodology**: reuses IV term structure's exact day-clustered Pearson correlation + Monte Carlo permutation construction verbatim (daily-bar realized-vol formula, not net-gamma-regime's 5-minute-bar one — deliberate). Primary horizon 20-day, Bonferroni family size 3 (10/20/50-day), α_corrected=0.0167, effect-size floor |r|≥0.15 — all matching the established IV term structure/strike positioning bar.
- **5 robustness checks — see the 2026-09-24 audit below for which were actually verified functioning empirically, not just structurally**: `near_opex_vs_far_opex`, `alternate_horizon:10day`, `alternate_horizon:50day`, `alternate_signal:net_gex_normalized`, `alternate_signal:put_wall_distance_pct`.

**CORRECTED 2026-09-24, same day, caught by explicit user review before Stage 1 was touched — a real window-staleness bug, not a nitpick, and already concretely manifested, not just theoretical.** The file itself contains no execution/query logic (confirmed — like every pre-registration in this family, it's declarative config construction only; execution happens in a separate, not-yet-written script). But `date_range`/`train_period` were hardcoded literals (`"2026-06-10"` to `"2026-09-21"`, the 71-day state at draft time) — the exact bug class already caught for IV term structure's original `test_period` and already fixed once for GEX call-wall-distance's own Stage 1 dataset definition (Section 32). It had already gone stale within the same session: SPY was added to `GEX_Historical_Incremental_Update`'s ongoing `TICKERS` list the same day (below), and `gex_metrics` grew to 146 rows / 73 distinct dates / through 2026-09-23 before this correction was even applied. **Fixed the same way as call-wall-distance's Stage 1**: no result has ever been computed against the 71-day snapshot, so this is a pre-execution construction correction, not a post-hoc reshuffle — `date_range`/`train_period` updated to `("2026-06-10", "2026-09-23")`, confirmed by direct query, with explicit documentation that this value will keep drifting forward nightly now that SPY is on the same incremental cadence as the 6 stocks, and must be re-verified against `gex_metrics`' actual current SPY max immediately before Stage 1 is ever executed — never treated as locked from today.

**Infrastructure gap #2 (Stage 2 data collection) — RESOLVED same day, not left open.** `daily_collection_run.py`/`prospective_gex_pipeline.py` (the literally-named `GEX_Prospective_Daily_Collection` task) was checked directly and confirmed to gate on V1's frozen entry logic (bullish regime + intraday breakout + entry_score≥20, 5-minute bars) and log forward *returns* into a schema built for the closed call-wall-distance hypothesis — none of which matches this experiment's actual design (day-level, unconditional, daily-bar *realized volatility*). Wiring SPY into that task would have built infrastructure serving the wrong population and the wrong outcome variable — the same mistake already caught once this session on net-gamma-regime's original design. **Instead, `"SPY"` was added to `GEX_Historical_Incremental_Update`'s `TICKERS` list** (`gex_historical_incremental_update.py`) — the task that actually populates `gex_metrics` itself, which is what both Stage 1's window and Stage 2 genuinely depend on. Safe now that SPY has real historical data (the original exclusion reason — broken scan-start logic for a ticker with no prior max — no longer applies).

**Independent audit pass, 2026-09-24, before Stage 1 was ever touched — five checks, two real bugs found and fixed, everything reported plainly, nothing rounded up:**

1. **Scheduled task — confirmed real, but with a genuine nuance, not overclaimed.** `schtasks /query` confirms `GEX_Historical_Incremental_Update` is genuinely `Enabled`, `Daily`, 19:45 ET, and a real clock-triggered run the prior night succeeded (`Last Result: 0`). But that run's log predates SPY's addition to `TICKERS` (added later the same day via manual edit) — so **no unattended, scheduler-fired run has included SPY yet**; the next 19:45 ET fire is the first genuine automatic test.
2. **Computable-N off-by-one — found, root-caused, fixed.** The previously-reported figures (54/64/24 computable at 20/10/50-day) were each **one too high**. Root cause: the Alpaca daily-bar calendar used for forward-return-computability checks included *today's* still-forming, incomplete trading session (confirmed via anomalously low volume vs. genuinely closed days, and the check running during live market hours) as if it were a real, closed trading day — shifting every horizon's eligibility boundary by +1. **Corrected, reverified figures**: **53/73 computable at 20-day (primary)**, 63/73 at 10-day, 23/73 at 50-day (as of 2026-09-24 — these keep shifting as both time passes and the window grows).
3. **`near_opex_vs_far_opex` was a structural no-op — found, root-caused, fixed, a *different* bug from #2.** The original mechanic (live EODHD chain query, filtered to `expiration_type=='monthly'`) can only see expirations at or after the observation date — an already-expired contract has no queryable forward quotes — so it could only ever detect *upcoming* OPEX proximity, never *just-passed* proximity, despite the parameter's own stated "before or after" definition. Confirmed empirically before assuming a fix was needed: querying 2026-07-17 itself (a real monthly OPEX date) as the observation date wrongly returned "35 days away" instead of 0. Across all 73 real Stage-1 days (full population, not a sample — an initial every-7th-day sample had misleadingly shown 0/11 near, which turned out to be a stride-aliasing artifact, not the real finding), this produced **0 NEAR / 72 FAR**, a genuine structural no-op. **Fixed** by replacing the live-chain-query method entirely with a pure calendar computation (3rd Friday of the observation month ± the adjacent months, minimum absolute distance) — removes the forward-only bias structurally, needs no EODHD call for this check. Sanity-checked against EODHD's own confirmed monthly labels before trusting it (exact match: 2026-07-17/08-21/09-18/10-16). **Re-verified against all 73 real days after the fix, not just trusted structurally**: NEAR=31, FAR=42 — both buckets genuinely populate now, and the 2026-07-17 spot-check correctly returns 0 days away.
4. **Hash/window drift — none found.** Fresh query confirmed `gex_metrics` SPY state exactly matched the file's `date_range`/`train_period` at check time; hash recomputed fresh matched the recorded value before any of the above fixes were applied.
5. **"No data touched" — confirmed clean at both the code and database level.** Zero references to this file's `experiment_id` anywhere else in the codebase (grep); zero matching rows in `research_database.db`'s `experiments` table.

**One additional finding, confirmed a real market fact, not a bug — left as documented, not "fixed" (nothing to fix):** on ~9 of the 73 days, `call_wall_strike` and `put_wall_strike` are the exact same strike (SPY's liquid chain often clusters peak OI at the same round-number strike on both sides — `find_gamma_walls()` computes each side's maximum completely independently, confirmed by direct code re-read, not a wiring bug). On those specific days, `put_wall_distance_pct` is the exact negation of `call_wall_distance_pct` by construction — not independent evidence on those days specifically, though the check remains meaningfully non-degenerate across the full sample (empirical cross-correlation -0.38 with `call_wall_distance_pct`, not -1.0). `net_gex_normalized` confirmed genuinely distinct too (cross-correlation -0.49 with `call_wall_distance_pct`, +0.45 with `put_wall_distance_pct`). Both disclosures recorded in the pre-registration file's own comments, not just here.

**Remaining, still-open gap: single-ticker N ceiling.** With no cross-ticker pooling, Stage 1's day-clustered N is structurally capped by the window's own day count, currently far below the family-wide `min_n_per_stage=100` standard used by every other experiment. **Deliberately kept at 100 rather than quietly lowered**, for family-wide comparability; Stage 1 is expected to land at INCONCLUSIVE if run today, not VALIDATED/REJECTED, unless the threshold itself is separately, explicitly reconsidered — a decision left open for explicit review, not made here. Since the window now grows nightly, N≥100 is reachable through ordinary accumulation over several more weeks without needing that threshold decision at all. **Neither of the two bugs fixed in this audit changes this** — both were about making the file's own stated numbers and mechanics correct, not about clearing the N≥100 bar, which remains unmet before and after (53 < 100 at the primary horizon either way).

**Status: drafted, hashed (current: `1e84831a1e3daf2d77e7f7ce0d5889e1a02be9b7f502aaaaea50953cd3a38e99`), NOT submitted, NOT run.** Nothing about this hypothesis's actual predictive relationship has been computed or inspected. Next deliberate step, only when approved: either run Stage 1 now (N=53 at the primary horizon, explicitly caveated as underpowered/likely-INCONCLUSIVE) or wait for N≥100 to accumulate — an open decision, not made here. **SUPERSEDED 2026-10-01:** see the two subsections below. **Current experiment: `spy_gex_callwall_volatility_v2_20261001`, hash `ce0c2c0cee7571ddb08a66f24f3eb1a55525002403ec0170d9f317383a8b6c1b`** (adds the volatility_control_gate). v1 (`spy_gex_callwall_volatility_v1_20260924`, hash `c2629dc1…`) is superseded and was never run. The decision is to wait for N≥100 (night of 2026-11-30) and run v2.

### Stage 1 window bug fix + framework registration, 2026-10-01

- **Bug:** `train_period` and `date_range` were hard-coded to end **2026-09-23**, and so was the `dataset_version` label (`…_20260610_20260923_…`).
  - That capped Stage 1 at **73 distinct days**, so `min_n_per_stage=100` could never be met.
  - It contradicted the file's own stated design ("N>=100 is reachable through ordinary accumulation over several more weeks"; "this WILL drift forward again").
  - Same bug class as IV term structure's original hard-coded `test_period` (Section 33). Found by direct check of `preregister_spy_gex_volatility_experiment.py`.
  - Treated as a **bug fix** (correcting code to match its documented intent), not a new design decision.
- **Fix:**
  - `train_period=None`.
  - `date_range=("2026-06-10", "OPEN_END_AT_EXECUTION")`.
  - `dataset_version="spy_gex_metrics_v1_20260610_open_end_single_ticker"`.
  - New `parameters.stage1_window_definition`: fixed start 2026-06-10; end re-derived at execution from data existence only. N = distinct SPY trading days with a computable `call_wall_distance_pct` and a computable 20-trading-day forward realized vol. **Stop and lock on the first night N≥100; run the primary test ONCE.** Any later Stage 2 uses only dates strictly after the locked end.
  - `alpha_per_test_one_sided = 0.05/3` made explicit, plus a `framework_alpha_mismatch_note`.
  - Un-hashed `DECISION_RULES` items updated to match.
- **Hash:** `1e84831a1e3daf2d77e7f7ce0d5889e1a02be9b7f502aaaaea50953cd3a38e99` → **`c2629dc1e8aff9f3037a16894622e96c8681899b28ad4fd7d037ae3e004256c2`**.
- **Status as of 2026-10-01:** N = **58** at the 20-day horizon. That's 77 SPY `gex_metrics` dates (6/10–9/29, no gaps), 58 of them with ≥20 closed sessions after them. It matches the 9/24 figure of 53 plus 5 newly closed sessions.
- **Recalculated completion date (verified, not restated):**
  - A night-by-night simulation on the real NYSE calendar (Alpaca; holidays 6/19, 7/3, 9/7, 11/26) reproduces today's N=58.
  - It reaches **N=100 on the night of Monday 2026-11-30**, with N=99 on 11/27 (early close).
  - Observation #100 is 2026-10-30 (session #100); its 20-session window closes at session #120 = 11/30.
  - Assumes SPY GEX keeps covering every session through 10/30 (currently through 9/29, one day behind).
- **Framework registration:** `research_database.db` row `spy_gex_callwall_volatility_v1_20260924` (previously absent, like IV term structure).
  - `state=PREREGISTERED`, `preregistered_at=2026-10-01T17:13:05Z`, `hypothesis_amended_after_results=0`.
  - Hash `c2629dc1…`, `date_range_end=OPEN_END_AT_EXECUTION`, `train_period` null, `INDEPENDENT_SINGLE`.
- **FIXED 2026-10-01 (commit `11a2c8b`): the framework now returns 0.0167 automatically for this experiment and for v2.** Original note, now historical:
- **⚠ THRESHOLD MISMATCH:** the binding one-sided α is **0.0167** (`DECISION_RULES` item 2: "Bonferroni-corrected alpha = 0.05 / 3 = 0.0167"; 3 horizons). The framework's `multiple_testing.compute_per_test_alpha()` returns **0.05** (`none_single_test`), the same limitation as IV term structure: it can only apply Bonferroni across separately registered experiments, not across one experiment's 3 horizons. When this test runs, evaluate `multiple_testing_survived` against **0.0167**, not the framework's automatic result. This is also recorded in the registered `parameters.framework_alpha_mismatch_note`.
- **Not run:** the primary test was not run (N=58 < 100).

### v2: volatility-level control added; v1 superseded, 2026-10-01

- **Gap found** (design check, before any Stage 1 analysis on any version): v1's only feature was `call_wall_distance_pct`, with no control for the general volatility level anywhere (features, parameters, decision rules, or robustness checks). Dealer GEX substantially tracks overall market volatility, and forward realized vol clusters, so a positive v1 result could have reflected the volatility regime rather than dealer positioning.
- **VIX not available:** no VIX data source exists in this project (`features_regime.py:34`: "NOT RUNNABLE … no VIX data source is currently connected anywhere in this project").
- **The control:** SPY's own **trailing 20-day realized volatility ending at the T-1 close** (`trailing_realized_vol_20d_t_minus_1`). Same Alpaca adjusted daily bars and same formula as the target; fully known at the market-open anchor; never overlaps the forward window.
- **How it's used:** a mandatory **`volatility_control_gate`**, equal priority to the primary test.
  - Test: residualize both the signal and the 20-day forward realized vol on the control, then correlate the residuals; 1000 permutations, seeds [42, 43], one-sided.
  - Pass: the partial correlation is negative and significant at **0.0167**.
  - Fail: if this gate fails, the experiment is REJECTED, i.e. the effect is attributed to the volatility level.
  - Also added to `declared_robustness_checks`, as decision rule 6, and as a REJECTED trigger.
- **Registered as a new experiment,** per the user's decision:
  - **`spy_gex_callwall_volatility_v2_20261001`**, hash **`ce0c2c0cee7571ddb08a66f24f3eb1a55525002403ec0170d9f317383a8b6c1b`**, file `preregister_spy_gex_volatility_v2_experiment.py`, `state=PREREGISTERED`, `preregistered_at=2026-10-01T18:59:46Z`.
  - Everything else is copied from v1 unchanged: hypothesis, signal, target, horizons, α, effect floor, and the 5 original robustness checks.
- **v1 superseded, plan untouched:**
  - The `spy_gex_callwall_volatility_v1_20260924` row keeps its plan exactly as registered (hash `c2629dc1…`, parameters, `state=PREREGISTERED`; verified by fingerprinting all non-annotation columns before and after).
  - Only the annotation columns were set: `status=SUPERSEDED`, `notes` (never run, superseded before any result, reason), and `related_experiment_ids=["…_v2_20261001"]`. This follows the precedent of `finalize_experiment1.py`, which sets `status`/`notes`.
  - The framework's `VALID_STATES` has no SUPERSEDED state, so `state` stays PREREGISTERED.
  - The v1 file is byte-identical and still hashes to `c2629dc1…`.
- **Window/N logic transfers unchanged (verified):** `stage1_window_definition` and `min_n_per_stage` are identical to v1's. The control is computable for **77/77** SPY dates (the earliest needs closes back to 2026-05-11; Alpaca has them), so it never removes an observation. N = 58 now; N ≥ 100 on the night of **2026-11-30**, as for v1. **v2 is the experiment that runs then.**
- **Framework α:** `compute_per_test_alpha` returned 0.05 for v2 as well; **0.0167 binds**. **Fixed 2026-10-01 (commit `11a2c8b`): it now returns 0.0167.**
- **Power (added 2026-10-01; `POWER_ANALYSIS` in the v2 file, outside the config, hash unchanged):** at N = 100, α = 0.0167 one-sided, power is **26% at r = 0.15, 45% at 0.20, 65% at 0.25**; 80% power only for |r| ≥ **0.29**. 80% power at r = 0.15 / 0.20 / 0.25 needs N = 390 / 218 / 139, i.e. lock nights 2028-01-26 / 2027-05-20 / 2027-01-27. A REJECTED means "no effect ≥ ~0.29 detected", not "no effect ≥ 0.15". ~~**Whether to raise N is an open user decision.**~~ **Decided 2026-10-01: N raised to 139 — v2 superseded by v3, below.**
- **SUPERSEDED 2026-10-01 by `spy_gex_callwall_volatility_v3_20261001` (power-driven N increase, user decision, before any Stage 1 result). v2 is no longer the experiment that runs on 2026-11-30.**
  - **v3 hash `afdf29dc28c9cdc2eff657171e65cf0a5af8dcfe553823dd129500dd18b3c41e`**, file `preregister_spy_gex_volatility_v3_experiment.py`, `state=PREREGISTERED`, `preregistered_at=2026-10-01T21:15:38Z`, `related_experiment_ids=["…_v2_20261001", "…_v1_20260924"]`.
  - **SPY has no separate Stage 2 with its own threshold:** its locked test is Stage 1 itself (rolling window, stop-and-lock at N), so here the literal `min_n_per_stage` change 100 → 139 is the correct one (unlike IV, where it is split by stage).
  - Config diff vs v2, verified field by field: `experiment_id`, `code_version`, `min_n_per_stage` 100 → 139, `stage1_window_definition` ("lock on the first night N ≥ 139"), `supersedes`. Nothing else; the volatility-control gate and all checks carry over.
  - **Lock date (night-by-night simulation, real NYSE calendar + real SPY `gex_metrics` dates, horizon 20 sessions; reproduces the old 2026-11-30):** N ≥ 139 first on the night of **Wed 2027-01-27** (N = 138 on 2027-01-26); observation #139 = 2026-12-28. Current N = **59** (last closed session 2026-10-01); 80 trading sessions / 118 calendar days to go.
  - **Power at N = 139:** 35.7% / 59.3% / 80.2% / 89.0% at r = 0.15 / 0.20 / 0.25 / 0.28; MDE at 80% = 0.249.
  - **v2 row:** plan columns unchanged (fingerprinted before/after); annotated `status=SUPERSEDED`, `notes`, `related_experiment_ids=["…_v1_20260924", "…_v3_20261001"]` (backward link kept, forward link added). v2 file byte-identical (SHA-256 `15895820…`), still hashes to `ce0c2c0c…`.
  - **Framework α, scratch-copy check:** `compute_per_test_alpha` → `bonferroni_within_experiment`, **0.016667**, k = 3.

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

**Direct follow-up to the regularized-XGBoost-v2 placebo re-leak (Section 56's addendum). Root cause, established via a 30-shuffle-seed sweep + a within-ticker-blocked shuffle + a bare ticker-mean baseline test**: real per-ticker mean forward-realized-volatility levels vary ~4x across this project's 6-ticker universe (AAPL 0.24, NVDA 0.46, AMD 0.50, TSLA 0.58, MSTR 0.85, SMCI 0.92). The `shuffled_target_placebo`'s *global* (non-ticker-blocked) label permutation does not fully destroy this between-ticker structure — for any one random permutation, a model that can even weakly infer ticker identity from the features can exploit the residual, chance-driven per-ticker mean. Confirmed systematic, not 8-seed noise: a 30-seed sweep under the already-fixed frozen-rounds mechanism showed **9/30 significant** (expected ~1.5), and **Ridge itself** — plain linear, no adaptive anything — showed spurious R²>0.01 on **10/30** shuffles, ruling out "XGBoost capacity" as the sole explanation. A within-ticker-blocked shuffle (permuting only inside each ticker's own rows) came back **30/30 "significant,"** with R² for both models landing almost exactly on the real, unshuffled result — because within-ticker shuffling can't touch the between-ticker mean structure that's actually driving most of the apparent skill.

**The confirming test**: a model using **zero options-derived features** — literally "which of the 6 tickers is this, predict that ticker's own historical average forward realized volatility" — scores **R²=0.50–0.51** on the real, locked primary test set, matching or beating every one of this project's own real, fully-tuned 8-feature models in this entire track.

**Per explicit instruction, Option A implemented and applied retroactively to all four experiments sharing this dataset/target — not just the one that surfaced the issue.** Method: add explicit ticker one-hot dummy columns to the input alongside the 8 real features, for both Model A and Model B in each experiment (reusing each experiment's own already-tuned hyperparameters — a disclosed, diagnostic-scale analysis, not a full re-tune of the enlarged input space; script: `analyze_ticker_fixed_effects.py`, log: `ticker_fixed_effects_analysis_20260928.log`). Reports incremental R² = (model with 8 features + ticker dummies) − (ticker-only baseline), on each experiment's own real primary test set:

| Experiment | Ticker-only baseline R² | Model A (Ridge) + features + dummies | Ridge incremental | Model B + features + dummies | Model B incremental |
|---|---|---|---|---|---|
| RF v1 / RF v2 (shared split, N=173) | 0.5028 | 0.4671 | **−0.0357** | RF: 0.4766 | **−0.0262** |
| XGBoost v1 (same split, N=173) | 0.5028 | 0.4671 | **−0.0357** | XGBoost: 0.4264 | **−0.0764** |
| Regularized XGBoost v2 (own locked split, N=174) | 0.5078 | 0.4727 | **−0.0351** | reg. XGBoost: 0.4890 | **−0.0189** |

**Every single incremental R², for every model, in every experiment, is negative.** Adding the 8 real options-derived features (`term_structure_slope_pct`, `oi_skew`, `trailing_realized_vol_20d`, `delta`, `gamma`, `theta`, `charm`, `vega_per_1pct_iv`) on top of explicit ticker identity does not merely fail to help — it makes every model's real-test-set prediction modestly *worse* than simply predicting each ticker's own historical average. This is a clean, unambiguous, negative result, not a borderline call.

**What this means, stated plainly**: RF v2's original "VALIDATED at Stage 1" result (Section 48, before the data-contamination fix was even found) was never measuring real options-feature signal — across every experiment in this track, once ticker identity is accounted for, there is nothing left. This does not retroactively change any experiment's own formal, pre-registered verdict (each was decided under its own literal, pre-specified decision rules, and none of those rules included a ticker-fixed-effects control — a real, now-documented gap in all four designs, not a reason to relitigate a verdict after the fact). But it does mean: **none of RF v1, RF v2, XGBoost v1, or regularized XGBoost v2 should be read as evidence that this project's 8-feature options-derived set carries real predictive value for forward realized volatility.** Whatever apparent skill any of them showed, at any point in this project's history, is fully explained by ticker-mean recovery.

**Not yet done, per explicit instruction — deferred, not abandoned**: the gap-closure comparator question for regularized XGBoost v2 (Section 56's other open item) stays moot until/unless a genuinely redesigned version of this experiment family (with ticker fixed effects built into the primary test and placebo from the start, per the new Section 1 rule) produces a different answer. No pre-registration file has been touched, no formal verdict has been changed, no new hash has been generated. **Regularized XGBoost v2 stays REJECTED** — the placebo re-leak is now fully root-caused (this section), but "root-caused" is not "passing clean," and per explicit instruction the verdict does not change until it is.

---

## 60. Eleventh formal experiment: broader-universe (59-ticker) forward realized volatility, Target C — pre-registration drafted (2026-09-29, NOT YET SUBMITTED, NOT RUN)

*(Archived 2026-10-01, pass 2. The full original text is verbatim in `CLAUDE_ARCHIVE.md` under this same section number. **This stub is a locator, not a substitute:** read the archived section before citing any number or relying on any detail from it.)*

**Condensed 2026-10-01 to current state.** The full design history and the complete operational log of 2026-09-29 → 2026-10-01 (quota exhaustion, call-volume investigation, the provided-script review, network crashes, Modern Standby kills, the manual catch-ups, the `schtasks /run` test, the full probe table) are in the archive.

**⛔ RETIRED 2026-10-01 (user decision): Target C will not be registered or run.**
- **Why, specifically:** Target C predicts forward realized vol (relative to each ticker's own history), not what a volatility position pays. The IV Stage 1 economic check that evening (Section 33) showed this class of target mostly recovers the already-priced implied-vol level. The slope's correlation with RV was −0.25 to −0.30, but with the straddle payoff (RV − IV)/IV only −0.07 to −0.10, about one spread. Target C's ticker-demeaning removes Section 58's ticker-mean confound but not this one, so even a clean pass would not have been tradeable.
- **Replaced by:** the cross-sectional straddle hypothesis (Section 62), which takes its slot under Section 1's three-hypothesis rule.
- **What happened to the pieces:**
  - The pre-registration file stays as written and was never registered (hash `10f10a13…`).
  - `broader_universe_volatility_dataset.db` stays as is (34/59 tickers complete, 23,552 candidates).
  - Task `BroaderUniverse_Volatility_Nightly_Update` was **disabled**.
  - `quota_probe_and_resume.py` no longer relaunches the backfill (`TARGET_C_RETIRED`).
  - The health check reports the backfill as retired.
  - The freed daily EODHD quota goes to Section 62's option snapshot collection.
- **Reusable for Section 62:** the ticker universe and IPO/depth checks, the RAW/ADJUSTED price rule, the quota-safe fetch pattern, and the walk-forward purge logic.

**Experiment (locked design, NOT submitted, NOT run) — retired, see above.**
- **Files:** `preregister_broader_universe_volatility_c_experiment.py`, `config_hash` `10f10a1364cd6034bc578c6807b9582a5fbe5f5912648cc71d2525f624e699cc` (was `bf9fef62…` until the 2026-10-01 purge fix below).
- **Universe:** 59 tickers (the original 6 + 53).
- **Target C:** forward realized vol relative to the ticker's own trailing history. This structurally removes Section 58's ticker-mean confound.
- **Models:** Model A = Ridge, Model B = Random Forest. No XGBoost, per Section 47's reasoning.
- **Test parameters:** horizons 10/20/50, primary 20; α_corrected=0.0167; R²-delta floor 0.05.
- **Two mandatory gates of equal priority:** `ticker_identity_baseline_gate` and `fold_stability_gate` (Model B must beat Model A in all 4 folds).
- **K=4 expanding-window walk-forward:** Stage 1 = 2024-04-02 .. 2026-07-10 (569 real SPY-calendar trading days), split into 5 equal ~113-day blocks: block 1 is training-only and blocks 2-5 are the 4 test folds. Stage 2 is rolling from 2026-07-13.
- **Purge added 2026-10-01** (design fix, before registration or any result). **Hash `bf9fef62…` → `10f10a1364cd6034bc578c6807b9582a5fbe5f5912648cc71d2525f624e699cc`**; still not registered.
  - **Gap:** the folds had no train/test gap; each test block started the trading day after its train block ended (fold 1: train ends 2024-09-11, test starts 2024-09-12). Because the targets are *forward* realized vols (10/20/50 days), the last *h* training rows' labels were computed from test-period prices: label leakage despite zero shared dates.
  - **What it isn't:** the backward-looking feature windows (longest `trailing_realized_vol_20d`, `TRAILING_WINDOW = 20`) are not themselves a leak, since those prices are known at prediction time; the purge covers them anyway.
  - **Fix** (`fold_structure.purge_rule`): drop from each fold's training set, and from every nested-CV inner split and the ticker-baseline training means, the last **max(h, 20)** trading days before the test start. That's 20 for the primary 20-day target and the 10-day check, and 50 for the 50-day check. Test blocks are unchanged.
  - **No post-test embargo needed:** expanding folds never train on later data.
  - **Real cost** (NYSE calendar), training sessions removed: 20-day purge, fold 1–4 = 18% / 9% / 6% / 4%; 50-day check = 44% / 22% / 15% / 11%.
  - Also recorded in `target_c_baseline_and_walkforward_design_v1.md` §2.3.
- **Eligibility:** ≥113 of 126 trailing days valid; `alternate_lookback:252day` is mandatory.
- **`dataset_version`** is provisional; append a content hash once the backfill completes.
- **Target A** (cross-sectional rank) is preserved as a separate future hypothesis.
- **Design docs:** `broader_universe_feasibility_report.md`, `target_design_comparison_v1.md`, `target_c_baseline_and_walkforward_design_v1.md`, `preregistration_prep_resolution_v1.md`.
- **Data facts:** one shared `START_DATE` (2023-10-02) for all 59 tickers (the IPO-limited ones were verified). Alpaca IEX has a 3-day gap (2021-04-19, 2021-10-25, 2022-03-08) for 44/53 candidates. DIS's 2018 bar is a stray.

**Backfill state (2026-10-01 04:41 UTC).**
- `generate_broader_universe_volatility_dataset.py` writes `broader_universe_volatility_dataset.db`.
- Totals: 23,239 saved + 313 excluded. **34/59 tickers complete**; GS partial (364/682); 24 not started.
- The last run stopped cleanly on a 429 at GS: the normal daily options quota ran out again (the $25 extra calls never applied to it; see below).
- Resumable and idempotent. After any interruption, check for an orphaned `*.lock` with no matching process before relaunching.
- Nightly task: `BroaderUniverse_Volatility_Nightly_Update` (20:30 ET).

**EODHD quota facts.**
- **Quota:** the UnicornBay Options add-on (`/api/mp/unicornbay/options/eod`) is 100,000/day per the dashboard. The window is rolling: it resets 24h after the first request. **It is shared by every EODHD task.**
- **Observed:** only ~10k real page calls before the wall (measured). The gap is unexplained; one unconfirmed hypothesis is that usage is metered by records returned.
- **MEASURED TWICE, 2026-10-01:** successful options requests between a quota reset and the next 429 were **~9,998** (9/30 night) and **~9,976** (10/01, 00:19→04:41 UTC: backfill 9,948 page-calls + GEX 23 + probes 5).
  - Records per request vary widely (GEX averaged 691), yet the stopping point barely moves. So the cap behaves like **~10,000 requests/day**, not a records-based meter.
  - **Best hypothesis (unconfirmed):** each options request is billed as **10 API calls** against a 100,000-call/day allowance.
  - Separately, the general account's `extraLimit` read **500** on 2026-10-01 ~16:55 ET, down from 500,500 that morning; the 500,000 extra calls are gone from it (refund, expiry or consumption unknown).
  - **Needs EODHD support** (draft text in the 2026-10-01 report): the real options limit, the per-request cost, and where the $25 went.
  - Practical planning number until then: **~10,000 options requests/day, shared** (~9,950 completed 59-ticker candidates per night when nothing else runs).
- **CORRECTED 2026-10-01: the $25 extra-calls purchase almost certainly did NOT apply to the UnicornBay options quota.** The earlier "buffer live 00:19 / exhausted 04:41" reading was wrong, and so is the matching wording in the archived Section 60 text. Evidence:
  1. EODHD `/api/user` (queried directly 2026-10-01) shows `subscriptionType: free`, `dailyRateLimit: 20`, **`extraLimit: 500500`**, `apiRequests: 1`. The extra calls sit on the general/base account, which this project barely uses (one call: the `check_eodhd_quota.py` check).
  2. **Timing matches a normal reset exactly.** The previous window opened at RF v2's first successful call (~00:15 UTC 2026-09-30); 24h later is ~00:15 UTC 2026-10-01. The probes show 429 at 00:08:29 (just after the purchase) and 200 at 00:19:54.
  3. **The budget was the same both nights.** Each night the run went ~4.4-4.5h after clearing before hitting 429 (09-30: 00:15 → 04:42 UTC; 10-01: 00:19 → 04:41 UTC, with a 6-min reboot gap). Half a million extra calls would have been nowhere near exhausted.
  - **Not directly verified:** the dashboard's options-product usage panel (not visible from this machine). It's also unknown whether `extraLimit` is a remaining balance or a static total.
  - **Action:** ask EODHD support to move the credit to the UnicornBay Options add-on, or refund it.
- **Authoritative check:** `single_quota_test.py` (project root), which hits the real endpoint.
- **Don't trust:** `check_eodhd_quota.py` tests the *base* EOD API and gives a false "QUOTA OK". EODHD's `/user` endpoint reports the unrelated base quota (`dailyRateLimit: 20`).
- **Reference only:** `eodhd_quota_safe.py` is kept but not used; it's equivalent to the deployed fix.
- `GEX_Prospective_Daily_Collection` makes zero EODHD calls (it reads local `gex_metrics` only).

**Safety fixes in place.**
- `QuotaExhaustedError`: the first 429 stops the whole run, which logs `RUN STOPPED EARLY (QUOTA)`. No in-process retry. Present in both `generate_broader_universe_volatility_dataset.py` and `generate_iv_termstructure_stage2_dataset.py`.
- A failed Alpaca daily-bar fetch now skips that ticker instead of crashing; DNS drops killed the run twice at DIS before this fix.

**Scheduled tasks** (all `WakeToRun=true` since 2026-10-01 **except `EODHD_Quota_Probe_And_Resume`**, which has it deliberately off; all `State: Ready` except `RF_v2_Stage2_Nightly_Update`, which has been Disabled since 2026-10-01):

| ET | Task | Notes |
|---|---|---|
| every 2h at :23 (from 2026-10-01 12:23) | `EODHD_Quota_Probe_And_Resume` | Added 2026-10-01; replaced the session-only probe jobs. Action: `pythonw.exe run_logged.py quota_probe_and_resume.py quota_probe_and_resume_log.txt` (windowless). `WakeToRun` deliberately **off** (would otherwise wake the laptop 12×/day); `StartWhenAvailable=true`, 30-min limit, `InteractiveToken`. See the probe-log paragraph below. **Bug fixed 2026-10-01:** its 12:23 and 14:23 ET runs crashed (`StopIteration`, exit 1) because a CLAUDE.md heading it parsed was renamed. **Decoupled the same day:** the script now logs to its own `quota_probe_log.db` (table `probe_log`: utc_ts, result, category BACKFILL/GEX/PROBE, action, dry_run) and never reads or writes CLAUDE.md, so this document can be edited freely. |
| 21:05 | `ExecutionCost_EOD_Spreads` | **Added 2026-10-01.** `pythonw.exe run_logged.py execution_cost_eod.py execution_cost_eod_log.txt`. Builds real EODHD end-of-day spreads from the GEX task's stored chains; zero EODHD calls. Section 26. |
| 21:15 | `EODHD_Daily_Health_Check` | **Added 2026-10-01.** `pythonw.exe run_logged.py health_check.py health_check_log.txt`, `WakeToRun=true`, 15-min limit. See "Daily health check" below. |
| 19:44 | `PreventSleep_DuringCollectionWindow` | `prevent_sleep_during_collection_window.py`, `SetThreadExecutionState(ES_SYSTEM_REQUIRED\|ES_AWAYMODE_REQUIRED)` for 65 min, self-expiring. First real run 2026-10-01. |
| 19:45 | `GEX_Historical_Incremental_Update` | Section 40. `gex_metrics` MAX = 2026-09-29, 1,074 rows after the 2026-10-01 manual catch-up. **Since 2026-10-01 the action is `pythonw.exe run_logged.py gex_historical_incremental_update.py gex_historical_update_log.txt`**: windowless, no cmd/conhost; the wrapper appends stdout and stderr to the same log, line-buffered. Verified via `schtasks /run`: result 0, only `pythonw.exe` spawned, full output logged. `run_gex_historical_update.bat` is kept but no longer called; original action XML is in `task_backup_GEX_Historical_Incremental_Update.before_pythonw_20261001.xml`. |
| 20:00 | `GEX_Prospective_Daily_Collection` | `RestartOnFailure` removed 2026-09-29. The state flipped Disabled/Enabled 3 times with no explanation; the Task Scheduler Operational audit log has been enabled since. **Since 2026-10-01 the action is `pythonw.exe run_logged.py daily_collection_run.py gex_collection_log.txt`**: windowless, verified the same way (result 0, no console process). `run_gex_collection.bat` is kept but unused; rollback XML is in `task_backup_GEX_Prospective_Daily_Collection.before_pythonw_20261001.xml`. |
| 20:15 | ~~`RF_v2_Stage2_Nightly_Update`~~ | **DISABLED 2026-10-01** (RF v2 REJECTED; it was spending shared quota). Section 52. Frozen at 4,051 rows. |
| 20:30 | `BroaderUniverse_Volatility_Nightly_Update` | The backfill above. |
| 20:45 | `IVTermStructure_Stage2_Nightly_Update` | `generate_iv_termstructure_stage2_dataset.py` → `iv_termstructure_stage2_dataset.db`. Correctly 0 rows until 50 forward trading days have elapsed after 2026-09-10. **Since 2026-10-01 the action is `pythonw.exe run_logged.py generate_iv_termstructure_stage2_dataset.py iv_termstructure_stage2_update_stdout_log.txt`**: windowless, verified the same way (result 0, no console process). `run_iv_termstructure_stage2_update.bat` is kept but unused; rollback XML is in `task_backup_IVTermStructure_Stage2_Nightly_Update.before_pythonw_20261001.xml`. |

**OPEN — verify the 2026-10-01 natural firings after 20:45 ET.**
- **Why (CORRECTED 2026-10-01; the earlier "Modern Standby" attribution was wrong):** `GEX_Historical_Incremental_Update`, `GEX_Prospective_Daily_Collection`, and `IVTermStructure_Stage2_Nightly_Update` are being killed a few seconds after launch with exit code 3221225786 / 0xC000013A (`STATUS_CONTROL_C_EXIT`). Task Scheduler event log (Operational, events 100/201):
  - 9/30: 19:45:01 → 19:45:04; 20:00:01 → 20:00:05; 20:45:00 → 20:45:04.
  - The midnight manual `schtasks /run` test (10/01 00:00:47) ended the same way.
  - The 19:45 and 20:00 kills came well before the 20:19 standby event, and System-log Kernel-Power events show the machine awake at every kill. **Not sleep-related.**
  - Python buffers output when writing to a file, so a killed run can leave no log text at all.
  - `BroaderUniverse_Volatility_Nightly_Update` returned 0 on 9/30 only because it exited (`LOCK HELD`) in ~2s, before the kill.
- **What to check:** each task's `LastTaskResult` and log tail, plus real DB growth: `gex_metrics` MAX date, broader-universe counts, `iv_termstructure_stage2_dataset.db`. RF v2 is now disabled, so its task should NOT fire; confirm it didn't (no new 20:15 `LastRunTime`). That leaves four collection tasks plus `PreventSleep` to verify.
- **Root cause: UNRESOLVED, not sleep-related.** A separate investigation into what sends the signal is underway. Its notes haven't been written to a file yet, so this line is where they'll be referenced once they exist. Until then, a scheduled run's exit code and log can't be trusted as evidence that it did its work; verify against the databases.

**Reset of 2026-10-01 00:30:24 ET:** the backfill was killed mid-GS; the 3 surviving python processes are the NSSM services. Stale locks `broader_universe_volatility_generation.lock` and `xgboost_volatility_generation.lock` were cleared, and the backfill was resumed at 00:36 ET (it then stopped on quota, above). The prior probe job `1fe19d18` died with its session.

**Daily health check (added 2026-10-01).** `health_check.py`, run nightly at 21:15 ET by `EODHD_Daily_Health_Check`. Each check is OK / WARN / FAIL:
- **(a) Data:** `gex_metrics` covers the previous closed session for all 7 tickers; IV Stage 2 has 0 rows before the night of 2026-11-19 and keeps up after it; the 59-ticker backfill advanced since the last check (WARN, not FAIL, if every probe since then was a 429).
- **(b) Tasks:** each ran on schedule with result 0, **and** its own log has a run block starting at or after that run, with a completion marker and no traceback. The backfill check inspects **every** run since the previous health check (a failed run can't hide behind a later healthy one) and flags all-error tickers. The probe check needs a `quota_probe_log.db` row for its last run and no crashes in `quota_probe_and_resume_log.txt`.
- **(c) Bots:** each service running with a live python child, and a heartbeat (`uptime_log.db`) within the latest session.
- **Alerts on any FAIL:** email if `HEALTH_SMTP_HOST/PORT/USER/PASSWORD` and `HEALTH_ALERT_TO` are set in `.env` (**not configured yet**, needs e.g. a Gmail app password); otherwise it writes `HEALTH_ALERT.txt` and shows a Windows toast. Status also goes to `health_check_status.json`; state (last check time, backfill count) to `health_check_state.json`.
- **Verified by replaying real incidents on historical logs:** it catches the 2026-09-29 "RUN COMPLETE" with 50 all-error tickers, the 2026-09-30 GEX run killed at 19:45:04 ("ran but did no logged work"), and the 2026-10-01 12:23/14:23 probe crashes. A `schtasks /run` test gave result 0 and raised the alert (fallback channel).

**Quota probe log.** Since 2026-10-01 ~16:50 ET, **probe results go to `quota_probe_log.db` (table `probe_log`), not to this document.** The table below is a frozen history (2026-09-29 → 2026-10-01). Rows are produced by the **durable Windows Scheduled Task `EODHD_Quota_Probe_And_Resume`**, created 2026-10-01. It replaced the Claude Code session jobs `323501bc` → `6d005d8e` → `1fe19d18`, which died with their sessions and expired after 7 days; `323501bc` was deleted.
- **Action:** `pythonw.exe run_logged.py quota_probe_and_resume.py quota_probe_and_resume_log.txt` (windowless; the script's own output goes to `quota_probe_and_resume_log.txt`).
- **Schedule:** TimeTrigger from 2026-10-01 12:23 ET, repeating every 2h with no end. `StartWhenAvailable=true`. `WakeToRun` is deliberately off, so it won't wake the laptop 12×/day; the nightly collection tasks still wake it.
- **Settings:** same `InteractiveToken` logon type as the other tasks (runs only while you're logged on, no stored password), `IgnoreNew`, 30-min time limit. It survives reboots.
- **Verified 2026-10-01:**
  - A `schtasks /run` test exercised the 429 path: result 0, no console process, one row appended, CRLF preserved.
  - A `--dry-run-success` test under a temporary task confirmed a backfill launched from inside the task outlives it. That temporary task was deleted.
- **Not yet exercised under real quota:** the success path (backfill launch plus GEX trigger) awaits the first open-quota firing.

Each run does three things:
- **On a 429:** logs one row only; the backfill and GEX are untouched.
- **`[BACKFILL]` on success:** relaunches the backfill only if no backfill process is running, clearing a stale lock first.
- **`[GEX CATCH-UP]` on success:**
  - It runs the read-only `gex_gap_check.py`, which reuses `gex_historical_incremental_update.py`'s own scan rule: earliest per-ticker max through yesterday (UTC), both sign-convention rows required.
  - If anything is missing, it triggers the real `GEX_Historical_Incremental_Update` task via `schtasks /run`, waits up to 10 min for it to finish, then reruns the gap check.
  - It logs success, partial, still missing, or error, with pairs filled and row counts before and after.
  - Like the updater, it can't see interior gaps older than the scan start (e.g. SMCI 2026-09-28).

On success, backfill and GEX results are logged as separate rows prefixed `[BACKFILL]` and `[GEX CATCH-UP]`. When the backfill reaches 59/59, the task logs "[BACKFILL] complete" and keeps running for GEX catch-up. If this table has no new rows for more than ~3h while you're logged on, check the task: `Get-ScheduledTaskInfo EODHD_Quota_Probe_And_Resume` and `quota_probe_and_resume_log.txt`. Earlier rows (2026-09-29 → 2026-10-01 02:30) are in the archive.

| UTC timestamp | Result | Action taken |
|---|---|---|
| 2026-10-01T00:19:54 | 200 (cleared) | backfill resumed. *Corrected:* this was the normal 24h reset, not the purchased calls (see quota facts above) |
| 2026-10-01T04:36:17 | 200 (cleared) | post-reboot resume |
| 2026-10-01T04:41:53 | 429 (backfill's own stop) | backfill stopped cleanly at GS (normal daily options quota exhausted again); probe job will relaunch on next success |
| 2026-10-01T06:48:43 | 429 (blocked) | none (probe job 6d005d8e; backfill not complete: 34/59 done, GS at 364) |
| 2026-10-01T08:48:42 | 429 (blocked) | none (probe job 6d005d8e; backfill unchanged: 34/59, GS at 364) |
| 2026-10-01T10:48:43 | 429 (blocked) | none (probe job 6d005d8e; backfill unchanged: 34/59, GS at 364) |
| 2026-10-01T12:48:45 | 429 (blocked) | none (probe job 6d005d8e; backfill unchanged: 34/59, GS at 364) |
| 2026-10-01T13:23:41 | 429 (blocked) | none (manual check at user request; `check_eodhd_quota.py` had just said "QUOTA OK" for the base API, so the false positive recurred) |
| 2026-10-01T13:39:58 | 429 (blocked) | none. **First run of the trimmed probe:** `single_quota_test.py` now makes one direct request with the same URL and filters as `_fetch_raw_chain_paginated`, but `page[limit]=1` and no pagination, instead of pulling the ~545-record chain. JSONL log format unchanged. It also prints the token-redacted request URL and HTTP status to stdout. The success path is untested until the quota reopens. |
| 2026-10-01T15:12:19 | 429 (blocked) | none (durable probe task; backfill and GEX untouched) |
| 2026-10-01T20:23:01 | 429 (blocked) | none (durable probe task; backfill and GEX untouched) |
| 2026-10-02T01:32:09 | 200 (no SMCI data) | [SMCI 9/28 ONE-TIME] EODHD has no SMCI options data for 9/28 (confirmed twice). 1 request, no errors; 38 records returned, all dated to other days (rejected by the id-date rule); gex_metrics unchanged at 1,088 rows. |

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

**Phase 0 decisions (user, 2026-10-01), all fixed BEFORE any snapshot data existed:**
- **Hypothesis family:** each month, rank the eligible universe on a volatility signal; long ATM straddles on the top end, short (as iron butterflies) on the bottom end; hold to the next monthly expiration; all execution costs inside the test.
- **Primary signal, FIXED:** Goyal–Saretto (2009) realized-minus-implied gap, `HV − IV`.
  - HV = annualized stdev of daily log returns over the 252 trading days ending at the entry close (split-adjusted closes).
  - IV = mean of EODHD implied vol for the ATM call and put of the target expiration on the entry date (strike nearest the raw entry close).
  - Direction: **long straddles where HV − IV is highest, short where it is lowest.**
- **Secondary / robustness only:** cross-sectional IV term-structure slope (Vasquez 2017). Never promoted to primary after seeing data.
- **Calendar** (`straddle_schedule.py`): entry = first trading day after a monthly expiration (3rd Friday, or the prior trading day on a holiday); target = the next monthly expiration; exit variant = the last trading day before it.
- **Data windows (fixed):**
  - **DEV** = cycles with target expiry ≤ 2025-09-30: 23 cycles, 2023-10-23 → 2025-09-19. Exploration allowed.
  - **BLIND** = later cycles: 13 so far. A pipeline go/no-go gate only, not confirmatory. **Not to be examined until the gate runs.**
  - **Confirmation:** later, on untouched pre-2023 history (ORATS or a one-time purchase), only once the confirmatory test is ready.
- **Liquidity rule (approved), applied at each entry using only data known at entry:**
  - The ticker's ATM ~30-day straddle quoted full spread must be ≤ 5% of mid, as the median over its current and previous up-to-5 entry snapshots.
  - **Open-interest floor:** each ATM leg ≥ 100 contracts AND total open interest across the target expiration ≥ 1,000.
  - Reasoning for the OI numbers: a planned position of ~1–5 contracts per leg stays ≤ ~5% of the strike's open interest, and the expiration-level floor drops thinly traded chains whose quotes may be stale. The spread rule does most of the filtering; the OI floor is a backstop.
  - Expected to exclude SMCI/MSTR-type names.
- **Structures and risk:**
  - Long leg = ATM straddle (bought at the ask).
  - Short leg = **iron butterfly**: short ATM straddle at the bid, long wings at the call/put with |delta| nearest 0.10 at the ask. Capped loss is a hard requirement; no naked short straddles.
  - No stop-losses on the options; risk is capped by the wings and by position sizing.
  - Returns on the short leg are measured on max-loss capital (wing width − net credit).
- **Delta hedge:** optional variant, once daily at the close, stock-only, Black-Scholes delta at the entry IV. Hedge cost: 1 bp of hedge notional traded. Literature convention (e.g. Cao & Han).
- **Costs:**
  - Entry at ask (long) / bid (short), with variants at mid + 0.5× and 1× the half-spread.
  - Exit at expiry intrinsic using the RAW close against strikes (Section 56 rule), or at the close of the day before expiry, paying the exit spread.
- **Splits:** any ticker-cycle whose holding window contains a split (detected from the raw vs split-adjusted close ratio) is excluded, since option contracts get adjusted.
- **Earnings source — SEC EDGAR, decided 2026-10-01:**
  - EODHD's plan has no earnings data (`/api/calendar/earnings` → HTTP 403 "Only EOD data allowed for free users").
  - `earnings_dates_edgar.py` → `earnings_dates.db` uses the official, free, keyless EDGAR submissions API: US issuers' 8-K Item 2.02 filings, with exact acceptance time mapped to the affected session (after 16:00 ET → next session; before 09:30 → same day). Paged older filings are included.
  - Coverage: **54/58 single stocks `ok`.** ASML, ARM and NIO are foreign filers with untagged 6-Ks, and XOM files results under other items. Those 4 are `unknown`, and SPY has no earnings.
  - Caveat: some issuers also tag pre-announcements or delivery reports as 2.02 (TSLA, LCID), so the flag is conservative ("a results disclosure fell in the window").
  - Use: an earnings-in-window flag for stratification and robustness, not a filter on the primary.
- **Phase 3 quotes:** Interactive Brokers (OPRA top-of-book $1.50/month, waived at $20/month in commissions; IBKR Pro, ~$500 balance). No Alpaca $99 tier.

**Phase 1 build (2026-10-01; commits `fbe0322`, `d6e5deb`, `db4bc07`):**
- **`straddle_schedule.py`:** the cycle calendar (holiday-aware: Good Friday 2025 → 4/17 expiry, Juneteenth 2026 → 6/18).
- **`daily_prices.py` → `daily_prices.db`:** **consolidated SIP** daily closes from Alpaca, raw and split-adjusted, 59 tickers, 2022-06 onward.
  - Historical SIP is free on the basic plan; verified on NVDA 2024-06-07: raw 1208.88 is the official close, while IEX gives 1208.42.
  - Used for settlement, HV and hedging in this pipeline, instead of the project's usual IEX bars.
- **`option_snapshot_collector.py` → `option_snapshots.db`** (tables `chain`, `snapshot_summary`):
  - Entry snapshot: all expirations ≤ 60 DTE. Exit snapshot: the target expiration only. Strikes within ±25% of the raw close (EODHD `filter[strike_from/to]`, confirmed honored).
  - Same-day (id-date) records only. Stops on the first 429, lockfile, resumable. Never collects BLIND unless `--blind`.
- **Measured request cost (AAPL, cycle 2024-03-18 → 2024-04-19): 2 requests per ticker-cycle.** The entry snapshot returned 328 contracts across 7 expirations, the exit snapshot 66, and the strike filter halves the records (670 unfiltered).
  - The retired backfill's logs show 1.0–2.1 pages per ticker-day without a strike filter (mean 1.2).
  - **DEV estimate: ~2,700–3,300 requests** (2,714 ticker-day snapshots), not the 6–13k guessed earlier: under half of one day's ~10k quota.
- **`straddle_backtester.py` + `test_straddle_backtester.py`** (14 test cases / 51 hand-computed assertions, all passing). The tests caught two things:
  - A $0.00 exit bid is a valid quote (the leg is worthless), not a missing one.
  - One of my own hand calculations was wrong.
- **Rule fixed after the first snapshot, before any result:** EODHD leaves open interest **null** on many half-dollar strikes (e.g. AAPL 172.5, the ATM strike on 2024-03-18). Missing leg OI is treated as **unknown**, which skips the per-leg floor; the expiration-level floor (≥1,000, summed over known values) and the 5% spread rule still apply. The count of missing legs is recorded per trade (`leg_oi_missing`).
- **`straddle_dev_analysis.py`:** the DEV pipeline validation (Goyal–Saretto basis at three cost levels, the implementable long-straddle + iron-fly book, hedged and day-before variants, within-cycle shuffled-rank placebo, two-way fixed-effects check, earnings split, power).
  - Smoke-tested on synthetic trades with a planted effect, which it recovered (placebo p = 0.001).
  - The term-structure secondary signal isn't computed in this pass.
- **Automation:**
  - `quota_probe_and_resume.py` launches the DEV collector on quota success (GEX catch-up first), in the retired backfill's place.
  - The health check reports DEV snapshot progress.
  - DEV collection started manually at ~20:30 ET 2026-10-01.

**Phase 1 result (2026-10-01): pipeline validated; NO-GO on drafting the pre-registration yet.** Full report: `straddle_phase1_report.md`; numbers in `straddle_dev_analysis_results.json`.
- **DEV collection complete:** 2,714 snapshots, **2,758 requests** total, 614,577 contracts, 0 errors.
  - 75 empty snapshots are real EODHD gaps: all of 2025-01-16 (day-before exit for one cycle only) plus 16 ticker-days rejected by the same-day filter.
- **Backtest coverage:** 1,325/1,357 ticker-cycles evaluated (7 split exclusions, 11 short history, 14 no ATM quotes).
- **Second open-interest problem**, found after the first run had shown returns, so both versions are reported, never one silently:
  - EODHD also reports false **0** OI on liquid ATM legs.
  - As-specified rule: 780 eligible ticker-cycles. Refinement treating 0 as unknown (`eligible_zero_oi_unknown`): 987.
- **Goyal–Saretto on DEV** (as-specified / refinement):
  - Straddle-basis spread at mid +6.5% / +10.0% per cycle (t 0.6 / 0.9; placebo p 0.25 / 0.11); after quoted spreads +2.7% / +5.4%.
  - Implementable book (long straddle + iron fly) after costs −0.8% / +1.2%.
  - **Delta-hedged spread −1.5% / −0.9%.**
  - Trade-level corr(signal, return) ≈ 0 (−0.003 raw, +0.01 to +0.03 two-way demeaned).
  - Reads as: published sign, noise-level, and gone once hedged.
- **Regime caveat:** realized vol beat implied in this window. Long straddles returned +13% to +18% per cycle, and iron flies lost ~15% of max-loss capital per cycle.
- **Power** (80%, one-sided 0.05), minimum detectable effect per cycle:
  - Hedged spread: 13% at 23 cycles, 10% at 36, 4.4% at 192.
  - Implementable book: 14% / 11% / 4.9%.
  - Hedging cuts single-leg noise (0.48 → 0.19) but not the spread's (0.25), whose noise is name-specific. **Breadth is the binding constraint, more than history length.**
- **Path to GO:**
  - Buy the ORATS near-EOD archive (2007 → present, 5,000+ symbols, NBBO): **$599 one-time, not a subscription.**
  - Re-scope to a few hundred liquid names, with 2007–2023 as untouched confirmation data.
  - Re-run power. Draft only if the detectable effect is ≤ ~2% per cycle, with the **delta-hedged spread as the primary metric**.
  - ~~**This is a user decision.**~~ **Decided 2026-10-02: declined; hypothesis HELD (see the top of this section).**
- BLIND untouched; IV Stage 2 and SPY GEX v3 unchanged.

## 63. Thirteenth hypothesis: VIX term-structure timing of index volatility selling — PREREGISTERED 2026-10-02 (NOT run)

Trial #13 (Section 1). Takes trial #12's slot by deliberate user reallocation. File: `preregister_vix_termstructure_vrp_experiment.py`. Experiment **`vix_termstructure_vrp_index_timing_v1_20261002`, hash `188828a66ad359c28692d923a8c7c57d8d91cdd507b1932f6427acb38e488d09`**.
- **Registered** in `research_database.db` via `experiment.preregister_experiment()`: `state=PREREGISTERED`, `preregistered_at=2026-10-02T18:36:18.352210Z`, `INDEPENDENT_SINGLE`, `hypothesis_amended_after_results=0`. Pre-registration DB backup: `research_database.db.pre_trial13_20261002.bak` (SHA-256 `2194F811…`).
- **Framework α check:** `compute_per_test_alpha` → `none_single_test`, **0.05**, as intended (one test).
- **Superseded draft:** hash `06090007…` (BFLY primary, every sign check required, Stage 2 as a VALIDATED gate). It was never registered and was replaced by the user's four decisions below.

**User decisions locked before registration (2026-10-02):**
1. **Strictness:** at most 1 of the 13 sign-only checks may fail. The post-2014 subsample check and the `vrp_control_gate` must always pass; a failure of either is an automatic REJECTED.
2. **Stage 2 is directional / informative only:** it is reported but never changes the verdict. **SUGGESTIVE is the ceiling**; anything stronger needs a new pre-registered confirmatory test.
3. **Primary payoff = CNDR (iron condor), BFLY is a robustness payoff.** The reasons are tradability (the XSP iron-condor analog, less active management) and a user-reported max drawdown of 19% vs 47.1%. **That drawdown figure was not verified:** doing so would mean computing the target before locking. The choice rests on unconditional payoff properties only, and is disclosed in the file.
4. **α = 0.05 one-sided:** a single horizon, so the project's 3-horizon Bonferroni doesn't apply.

**Why this:** predicting realized vol mostly recovers already-priced IV (Sections 33, 60). A vol seller is paid realized minus implied, so this experiment's target is the return of a tradeable vol-selling strategy. It costs $0 and is the first design in the project with decades of free history.

**Design:**
- **Signal:** `ln(VIX3M/VIX)` at the close of the trading day before each monthly SPX roll (third Friday, or the prior business day on a holiday). Positive = upward-sloping (contango).
- **Target:** the next roll-to-roll return of the Cboe S&P 500 Iron Condor Index (CNDR), minus the 4-week T-bill. CNDR is short ~0.20-delta SPX puts and calls with long ~0.05-delta wings: capped loss and near delta-neutral. Excess returns are required because CNDR holds T-bills equal to 10× its options' maximum loss. CNDR's methodology (read in full) shares BFLY's roll rule, 11:00 ET strike selection, midpoint pricing and 2015-08-03 launch.
- **Data (free, no key):** Cboe daily history CSVs (`cdn.cboe.com/api/global/us_indices/daily_prices/<SYM>_History.csv`) for VIX, VIX3M, VIX6M, SPX, BFLY, CNDR, PUT, BXM, plus Treasury daily bill rates (`home.treasury.gov`; FRED timed out from this machine). Snapshot SHA-256 recorded at execution.
- **Sample:** **203 non-overlapping cycles**, signal dates 2009-10-15 → 2026-08-20, last cycle ending 2026-09-17. VIX3M history starts 2009-09-18. 153 cycles start after Johnson's 1996–2013 sample; 134 after CNDR/BFLY's 2015-08-03 launch (earlier values are Cboe back-tests).
- **Primary test:** Spearman ρ, 10,000 permutations, seeds 42/43, one-sided α = 0.05 (one payoff, one horizon), floor ρ ≥ 0.15.
- **Mandatory `vrp_control_gate`:** partial Spearman controlling for ln VIX and the VRP proxy VIX² − 21-day SPX realized variance (Bollerslev–Tauchen–Zhou). It must be positive and significant.
- **13 sign-only robustness checks** (sign only, no significance needed; pinned in advance, fixing the IV Stage 1 ambiguity): BFLY / PUT / BXM payoffs, Pearson, VIX6M slope from 2008 (224 cycles), post-2014 (**must pass**) and post-launch subsamples, bottom-quintile nonlinearity, **OOS R² > 0 vs the historical mean** (the "always sell" baseline; Goyal–Welch), Stambaugh/Amihud–Hurvich correction, lagged-return control, drop the top-5 |return| cycles, block-bootstrap null. **At most 1 may fail.**
- **Verdict:** SUGGESTIVE if the primary test is significant with ρ ≥ 0.15, the gate passes, the post-2014 sign holds, and ≤ 1 sign check fails. Otherwise REJECTED. INCONCLUSIVE only if fewer than 180 cycles load.
- **Stage 2 (informative only):** 36 forward cycles after registration (~3 years); ρ, sign and p reported, verdict unchanged either way. Power 21% at ρ = 0.15.
- **Economic check (reported, not part of the verdict):** sit in T-bills when the slope is below its expanding 20th percentile. Compare with always-on CNDR, including the break-even cost per roll. Cboe prices every leg at the bid/ask midpoint, so index returns include no trading costs.

**Power (`POWER_ANALYSIS`, outside the config):** Spearman at N = 203, α = 0.05: **66.7% at ρ = 0.15, 87.3% at 0.20, 96.9% at 0.25; MDE 0.179.** A simulation with a persistent AR(1) predictor and a fat-tailed, left-skewed payoff gave 68.0 / 87.5 / 96.8%. Plausible size from Johnson's monthly OOS R² for straddles: |r| ≈ 0.14–0.32. Chance the must-pass post-2014 sign check flips by noise under a real effect: 3.6% at ρ = 0.15, 0.8% at 0.20.

**Literature check (~30 min; `LITERATURE_CHECK` in the file):**
- **Johnson 2017 (JFQA), read in full:** it sets the direction. SLOPE predicts *lower* long-variance returns, i.e. higher short-vol returns, and turns them negative in the bottom quintile. VIX LEVEL doesn't predict, and SLOPE adds information beyond implied-minus-expected variance.
- **Other sources and what each added:**
  - Bollerslev–Tauchen–Zhou: the VRP proxy used as a control.
  - Goyal–Welch / Campbell–Thompson: the out-of-sample R² test against the historical mean.
  - Stambaugh / Amihud–Hurvich: the correction for a persistent predictor.
  - Simon–Campasano: VIX futures basis, which corroborates the direction.
  - AQR (Israelov–Nielsen): PUT and BXM carry equity beta, so they serve only as consistency checks.
  - Cboe's BFLY and CNDR methodologies: midpoint pricing, the 10× T-bill account, and the launch date.
- **Gap:** no direct post-2017 replication on Cboe strategy indices turned up.

**Looked at before registration:** data existence only (date coverage, missing days, cycle counts; `vrp_feasibility_check.py`). No slope, return, or relationship has been computed. Unavoidable contamination: market history and the literature are public, and the direction came from Johnson.
- **Known bug in `vrp_feasibility_check.py`:** it infers a fake roll on the last data date, so it prints 204 cycles. The design uses the correct 203. Don't reuse its roll logic; fix it in the dataset builder.

**Next step:** build the Stage 1 dataset, then run Stage 1 once.
- **Build:** a builder script that downloads the Cboe CSVs and Treasury bill rates into a local snapshot with per-file SHA-256, using the correct roll logic (no inferred future rolls).
- **Verify before running:** 203 cycles and the holiday rolls. Also check that the timing matches the methodology: the signal is taken at the close of the trading day before each roll, and the return runs from that close to the same point before the next roll.
- **Run:** Stage 1 exactly as registered (primary, gate, 13 sign checks, economic check), then record the verdict.

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

### Archived-identifier index (identifiers that appear only in `CLAUDE_ARCHIVE.md`, as of pass 2)

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

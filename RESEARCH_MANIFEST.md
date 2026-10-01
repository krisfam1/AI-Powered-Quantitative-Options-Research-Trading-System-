# AI Option Trading Bot — Research Manifest

**Purpose:** a persistent, honest ledger of the codebase, research state, and what's actually verified vs. remembered-by-summary.

**Last updated:** 2026-09-20, after resolving the combined-correction contract-identity investigation and cross-checking against prior historical scripts.

---

## 1. Core philosophy (unchanged since project start)

- V1 is frozen — permanent benchmark/control, never deleted even if superseded.
- Every new idea is a hypothesis, not an assumption. Failures get root-caused into one of: genuine signal failure / redundant / incompatible with V1's restricted population / data-limited / destroyed by pricing-execution economics / model-limited / inconclusive.
- Successes are never immediately implemented — independent validation + robustness/OOS/economic checks required first.
- Correctness over speed. Weeks/months timeline explicitly accepted.
- North star: long-term real profitability with options.
- The SQLite research databases (v1_v2_research_results.db, v2_pricing_log.db, the research-framework DB from create_research_db_schema.py, etc.) are the authoritative source of truth for results — not any chat conversation's memory. Query them directly when a past number matters.

---

## 2. Codebase scale

317 .py files. Most are one-off fix_*/patch_*/add_*/check_*/investigate_* scripts accumulated over a long iterative history, alongside the live trading engine and the research framework. Lesson from tonight: always check for an existing script before building a new one — two separate bugs "discovered" via fresh diagnostics had already been found and fixed elsewhere in the codebase (see below).

---

## 3. Key file status (pricing/execution thread — most active area)

- **combined_iv_spread_correction.py** — HAS A CONFIRMED BUG: fetch_exact_contract_quote() filters only by tradetime + exact exp_date, never checks the authoritative record-ID snapshot date. 17 of 105 "matched" trades used a quote from the WRONG day (always LATER than requested — a lookahead-relevant forward-fill artifact). Left untouched (frozen, like V1); superseded by combined_iv_spread_correction_v2.py.
- **combined_iv_spread_correction_v2.py** (built 2026-09-20) — THE CORRECTED VERSION, current best estimate. Reuses _select_real_contract() from v2_iv_pricing_model.py unchanged for entry selection. Adds fetch_fixed_contract_quote() (modeled on get_v2_checkpoint_iv()) for exit-side lookup using the SAME contract symbol fixed at entry. Result: 248/251 trades matched (98.8% coverage), corrected combined P&L = -$45,477.00 vs original synthetic +$21,594.85 on that subset. 60.9% of real expirations differ from V1's synthetic 14-day target. NOT YET independently spot-checked against raw API JSON — do that before treating as fully final.
- **v2_iv_pricing_model.py** — validated V2 historical-IV pricing module. _select_real_contract() queries a WIDE exp_date range (0-45 days out), hard-filters id_date == obs_date (parsed from record["id"].split("-",1)[1]), requires bid/ask/volatility present. Never fabricates.
- **gex_data_loader.py** — get_previous_trading_day(), get_real_trading_days(), _parse_id_suffix_date() (canonical id-date parsing). Real pagination via JSON:API links.next (needs api_token manually re-attached to next URLs or every page after the first 401s).
- **investigate_date_discrepancy.py** — historical investigation that originally surfaced the tradetime-unreliability problem; likely origin of the id-date-authoritative rule.
- **fix_real_expiration_bug.py** — patch applied to portfolio_backtest.py's v2_corrected pricing path: fixed v2_exp_date_str to use the REAL matched contract's actual expiration instead of the synthetic flat-14-day target.
- **full_v1_v2_research_experiment.py** — "OFFICIAL" V1 vs V2-corrected comparison via run_portfolio_backtest(..., pricing_mode="v2_corrected"). Likely true source of "-$1,874.37 IV-only correction." Does NOT use real bid/ask (theoretical BS price only) — does not overlap with the v2 combined correction above. Saves to v1_v2_research_results.db — query this DB directly for the actual number.
- **close_the_loop_real_spreads.py** — likely source of "-$27,307.36 spread-only correction," and NOT yet id-date-verified (same vulnerability class as the original combined_iv_spread_correction.py). Treat -$27,307.36 as unverified/suspect until rebuilt with the id-date check.
- **check_lookahead_bias.py** — different bug class (entry-score/breakout truncation test). Result: no lookahead bias detected. Closed.
- **check_contract_identity.py** — narrow sanity check, one trade, confirms selection determinism. Adjacent to but not the same as the fixed-contract-identity fix above.

Everything else (research framework: experiment_config.py/gates.py/verdict.py/multiple_testing.py/robustness.py/run_experiment.py/canonical_hash.py/db_interface.py/experiment.py/create_research_db_schema.py; Feature Factory; ML Experiment 1 pipeline; EODHD audits) is described in detail in prior research history but should be re-read directly from disk when precision matters — don't trust chat-summary recollection of exact behavior.

---

## 4. Status by roadmap area (16 permanent research areas)

1. Options pricing/Greeks — real progress: combined correction at 98.8% coverage (-$45,477.00); IV-only theoretical correction already existed (-$1,874.37, likely trustworthy); spread-only (-$27,307.36) flagged as needing the same id-date fix.
2. IV/vol structure — used in Feature Factory (ML Exp1, rejected); EODHD audit confirmed constructible; no dedicated experiment yet.
3. Liquidity/bid-ask/volume/OI — confirmed constructible; touched via execution-realism correction.
4. Options term structure — confirmed constructible; unused.
5. Strike structure/positioning — confirmed constructible; unused.
6. Gamma/GEX — UNCERTAIN, not confirmed-untouched: gex_calculator.py, gex_data_loader.py, gamma_gradient.py, gamma_landscape.py, gamma_regime.py all exist — check these before assuming zero progress.
7. Statistical arbitrage — untouched.
8. Cross-sectional/relative-value — untouched (on the neutral hypothesis list).
9. Market microstructure/tick-level — untouched, EODHD is EOD-only.
10. XGBoost — untouched.
11. LSTM — untouched.
12. Monte Carlo — untouched.
13. Reinforcement learning — untouched.
14. Execution optimization — real progress tonight (the combined correction).
15. Dynamic position sizing/exits — untouched by dedicated experiment (Phase 7 flagged concern only).
16. Alternative strategy architectures — untouched.

---

## 5. Open issues, in priority order

1. Manual spot-check raw EODHD JSON for 2-3 trades from combined_iv_spread_correction_v2.py's output before treating -$45,477 as final.
2. Query v1_v2_research_results.db directly to confirm the actual archived V1-vs-V2_corrected number.
3. Rebuild close_the_loop_real_spreads.py with the id-date check before trusting -$27,307.36.
4. Decide which EODHD hypothesis to pursue first (bid-ask spread / OI-concentration-gamma-wall / call-put OI ratio / term-structure slope / individual Greeks beyond delta / volume-vs-OI / cross-sectional-relative-value) — deferred by explicit prior instruction, still open.
5. Decide when to start next ML method (XGBoost/LSTM/Monte Carlo/RL) — none designed yet.

Known closed findings (don't re-litigate without new evidence): V1's raw entry signal shows no edge beyond random chance (Phase 6); V1's apparent profitability concentrated in a few trades + reversal-guard exits (Phase 7); ML Experiment 1 Feature Factory REJECTED, 5-bar exploratory finding did not replicate OOS; no lookahead bias in entry-score/breakout computation.

---

## 6. How to use this doc

- Read this first at the start of any new session (cloud or local) on this project.
- Before trusting any claim about a file's exact behavior, read the real file.
- Update this doc when: a file's status changes, an experiment closes out, a roadmap area gets first real work, or a blocking issue resolves.
- Prefer querying the actual .db files over recalling numbers from memory/conversation.

"""
Archive pass 3 (2026-10-05, user-approved): move the full current text of CLAUDE.md sections
26 (bots' operations subsections), 33, 34, 35, 36, 43, 58, 60, 62, 63 and three header bullets
verbatim into CLAUDE_ARCHIVE.md under "# Pass 3", and replace them in CLAUDE.md with condensed
current-state text. Then prove the round trip: rebuilding CLAUDE.md from the NEW file plus the
archived text (read back from CLAUDE_ARCHIVE.md, not from memory) must reproduce the backup
byte for byte.

  python archive_pass3_20261005.py            # apply + verify
  python archive_pass3_20261005.py --verify   # verify only
"""
import hashlib
import re
import sys

MD, AR = "CLAUDE.md", "CLAUDE_ARCHIVE.md"
MD_BAK, AR_BAK = "CLAUDE.md.pre_archive_pass3_20261005.bak", "CLAUDE_ARCHIVE.md.pre_pass3_20261005.bak"
PASS_HDR = "# Pass 3 — archived 2026-10-05"
HEADER_KEY = "## Header: reorganization notice history (pass 1 and pass 2 bullets)"
NL = "\r\n"


def rd(p):
    return open(p, "rb").read().decode("utf-8")


def wr(p, s):
    open(p, "wb").write(s.encode("utf-8"))


def crlf(s):
    return s.replace("\r\n", "\n").replace("\n", NL)


def sections(text):
    """[(number_or_None, start, end)] for every '## ' region (start of heading to the next '## ' heading)."""
    starts = [m.start() for m in re.finditer(r"(?m)^## ", text)]
    out = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else len(text)
        m = re.match(r"## (\d+)\.", text[s:])
        out.append((m.group(1) if m else None, s, e))
    return out


def trailer(orig):
    return NL + NL + "---" + NL + NL if orig.rstrip().endswith("---") else NL + NL


LOC = ("*(Condensed 2026-10-05, archive pass 3. The full prior text is verbatim in `CLAUDE_ARCHIVE.md` under "
       "this same section number (Pass 3). **This is a current-state summary, not a substitute:** read the archived "
       "text before citing any detail not repeated here.)*")

CONDENSED = {}

CONDENSED["26_tail"] = """### Bots' purpose and operations (condensed 2026-10-05, pass 3; full history archived)

- **Purpose (user decision 2026-10-01):** StockTradingBot and OptionsShadowLoop keep running (not paused) as an **execution-cost measurement instrument**, not to validate V1. Design: `execution_cost_measurement_design_v1.md`. Options only; the stock bot is out of scope.
- **Primary cost source: EODHD end-of-day spreads.** `execution_cost_eod.py` → `execution_cost_log.db:eod_spreads`, task `ExecutionCost_EOD_Spreads` (21:05 ET). Zero extra EODHD calls: it reads the chains the GEX task already stores. Panel: 6 tickers + SPY; near (7–16 DTE) and far (30–45 DTE); ATM and ~0.30-delta; calls and puts.
- **Secondary: the Alpaca intraday sampler** (`execution_cost_logger.py`, once per 60 s cycle from `options_shadow_loop.py`, no orders). The account has only Alpaca's **indicative** options feed (OPRA not signed), so its spreads are not real market cost; it serves only to estimate the time-of-day shape. Stream A (fill-log hooks in the order code) was not built.
- **Median full spread** (% of mid, 2026-06-10..09-29, ATM / 0.30-delta):
  - far: SPY 0.6/0.7, TSLA 2.2/2.7, NVDA 2.8/3.9, AAPL 5.8/9.3, AMD 7.1/12.3, MSTR 10.2/16.2, SMCI 11.9/20.4.
  - near: SPY 0.8/1.2, TSLA 2.2/2.8, NVDA 3.4/3.4, MSTR 5.5/8.4, SMCI 6.0/8.5, AMD 6.8/10.4, AAPL 8.3/12.1.
  - Day-to-day noise is large, so use medians. Backtest convention: base = EODHD median by ticker/bucket/role, sensitivity 0.5× (patient limits) and 1.5× (open / market orders). End-of-day quotes can't measure open or intraday costs.
- **Restart-churn fix (2026-10-01):** at 16:05 ET the bots now idle until the next ET day instead of exiting (1 NSSM restart per evening instead of ~450), and `main.py` retries `get_account()` at startup (waits 5/10/20/40/60 s) before exiting with code 1.
- **PENDING (user, admin shell):** NSSM stdout/stderr capture: `nssm set <svc> AppStdout|AppStderr <project>\\service_logs\\<svc>_stdout.log|_stderr.log` for both services, then restart them outside market hours.
"""

CONDENSED["33"] = LOC + """

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
"""

CONDENSED["34"] = LOC + """

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
"""

CONDENSED["35"] = LOC + """

- **Not a copy of Method A.** SpyGammaLoop's live gamma tools use a hardcoded vol of 0.30 and raw `gamma × OI × 100` without the `spot²×0.01` scaling, and they output an aggregate sign or unsigned per-strike concentration, not a zero-crossing price.
- **But they share Method A's architecture:** gamma is computed at one static spot with no hypothetical-price repricing sweep, the same vulnerability class Method B fixes.
- Flagged, not fixed. It sharpens Section 7 item 8d.
"""

CONDENSED["36"] = LOC + """

- **The two methods:** Method A walks cumulative signed gamma across strikes without recomputing gamma. Method B sweeps ~200 hypothetical spots (±20%) and recomputes Black–Scholes gamma at each.
- **Method B was never validated as predictive.** It became "primary" only because it doesn't show Method A's implausible-distance symptom. Method A's root cause was never isolated; the static-spot explanation is inference.
- **Porting Method B into SpyGammaLoop isn't the applicable fix**, because `gamma_regime.py` only checks the sign at the real spot. The real gaps are the hardcoded vol 0.30 (needs a live IV source) and the missing `spot²×0.01` scaling (one line).
- None of these fixes would be validation. Any live signal needs its own pre-registered test.
"""

CONDENSED["43"] = LOC + """

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
"""

CONDENSED["58"] = LOC + """ The standing rule it produced is in Section 1 (group fixed effects).

- **Finding (2026-09-28):** per-ticker mean forward realized vol varies ~4× (AAPL 0.24 … SMCI 0.92). A model with **no options features** ("predict each ticker's own average") scores R² = 0.50–0.51 on the real test sets, matching or beating every tuned 8-feature model.
- Adding the 8 options features on top of ticker dummies made every model **worse** than the ticker-only baseline: incremental R² from −0.019 to −0.076 across RF v1/v2, XGBoost v1 and regularized XGBoost v2 (`analyze_ticker_fixed_effects.py`).
- **Read:** none of those four experiments ever showed options-feature signal beyond ticker means. The verdicts are unchanged (each was decided under its own rules); regularized XGBoost v2 stays REJECTED.
"""

CONDENSED["60"] = LOC + """

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
| every 2h at :23 | `EODHD_Quota_Probe_And_Resume` | `quota_probe_and_resume.py` → `quota_probe_log.db`. On quota success it runs GEX catch-up (`gex_gap_check.py`, then the GEX task if anything is missing) and the straddle snapshot step (a no-op now). Never reads CLAUDE.md. |
| 19:44 | `PreventSleep_DuringCollectionWindow` | `prevent_sleep_during_collection_window.py`: `SetThreadExecutionState(ES_SYSTEM_REQUIRED\\|ES_AWAYMODE_REQUIRED)` for 65 min. |
| 19:45 | `GEX_Historical_Incremental_Update` | `gex_historical_incremental_update.py` → `gex_metrics` (Section 40). |
| 20:00 | `GEX_Prospective_Daily_Collection` | `daily_collection_run.py`; zero EODHD calls. `RestartOnFailure` removed 2026-09-29. |
| 20:15 | ~~`RF_v2_Stage2_Nightly_Update`~~ | **Disabled 2026-10-01** (Section 52). |
| 20:30 | ~~`BroaderUniverse_Volatility_Nightly_Update`~~ | **Disabled** (Target C retired). |
| 20:45 | `IVTermStructure_Stage2_Nightly_Update` | Section 33. |
| 21:05 | `ExecutionCost_EOD_Spreads` | Section 26; zero EODHD calls. |
| 21:15 | `EODHD_Daily_Health_Check` | `health_check.py`, below. |

Rollback XML for the pythonw conversions: `task_backup_<task>.before_pythonw_20261001.xml`.

**OPEN: collection-window failures.**
- On 2026-09-30 tasks were killed seconds after launch with `0xC000013A`; that root cause is still unknown.
- On 2026-10-04 tasks ran inside Modern Standby with no network: the event logs show the machine re-entering standby a second after its wake timer.
- `PreventSleep` didn't help: it held no display request, and its process ran ~20 h while suspended.
- Proposed fixes: network-wait task conditions, Wi-Fi in standby, a weekday keep-awake window, and retiring PreventSleep.
- Until fixed, verify scheduled runs against the databases, not their exit codes.

**Daily health check** (`health_check.py`, 21:15 ET):
- **(a) Data freshness**, **(b) tasks:** each ran on schedule with result 0 and its own log shows a completion marker, and **(c) bots:** running, with fresh heartbeats.
- On any FAIL it emails if SMTP is configured in `.env` (it isn't yet); otherwise it writes `HEALTH_ALERT.txt` and shows a toast. Status goes to `health_check_status.json`.

**Probe log:** since 2026-10-01, probe results go to `quota_probe_log.db` (table `probe_log`); the frozen 2026-09-29→10-02 table is archived.
"""

CONDENSED["62_tail"] = """**Phase 0/1 summary (condensed 2026-10-05, pass 3; full detail is verbatim in `CLAUDE_ARCHIVE.md`):**
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
"""

CONDENSED["63"] = LOC + """

- **Experiment** `vix_termstructure_vrp_index_timing_v1_20261002`, hash `188828a66ad359c28692d923a8c7c57d8d91cdd507b1932f6427acb38e488d09`, registered 2026-10-02T18:36:18Z. Registry: `status=REJECTED` (state PREREGISTERED, like every script-run experiment).
- **Hypothesis:** ln(VIX3M/VIX) at the close before each monthly SPX roll positively predicts the next cycle's CNDR excess return over T-bills, beyond ln VIX and the VRP proxy (Johnson 2017).
- **Result (203 cycles, 2009-10-15→2026-09-17): REJECTED. Genuine signal failure, and well powered (87% at ρ = 0.20).**
  - Spearman ρ = −0.020 (p 0.61).
  - `vrp_control_gate` partial ρ = +0.056 (p 0.21): failed.
  - 10 of 13 sign checks failed, including the must-pass post-2014 subsample.
  - PUT and BXM went strongly the other way (ρ −0.27 / −0.36). Spotted after the fact, so not a finding.
- **Economic check (2012-10→2026-09):** always-on CNDR returned −1.08%/yr vs T-bills (Sharpe −0.17, max drawdown 18.4%), and timing didn't help. Costs aren't the problem (~0.01% of account value per roll).
- **Files:** `preregister_vix_termstructure_vrp_experiment.py`, `build_vrp_timing_dataset.py`, `data_snapshots/vrp_timing_20261002/` (SHA-256 manifest), `vrp_timing_stage1_execution.py`, `vrp_timing_stage1_results.json`.
"""

HEADER_NEW = ("- **Archive passes:** pass 1 and pass 2 (2026-10-01) and pass 3 (2026-10-05) each moved text verbatim to "
              "`CLAUDE_ARCHIVE.md` and passed a byte-for-byte restore check. Backups and their SHA-256s are listed in "
              "each pass's header in `CLAUDE_ARCHIVE.md`." + NL)


def plan(md):
    """[(key, orig_start, orig_end, new_text)] in file order."""
    secs = {n: (s, e) for n, s, e in sections(md) if n}
    out = []
    # header bullets: pass 1, pass 2, round-trip (3 consecutive bullets)
    hs = md.index("- **2026-10-01, pass 1:**")
    he = md.index("- **Known cross-document drift:**")
    out.append(("header", hs, he, crlf(HEADER_NEW)))
    for n in ("26", "33", "34", "35", "36", "43", "58", "60", "62", "63"):
        s, e = secs[n]
        orig = md[s:e]
        heading = orig.split(NL, 1)[0] + NL + NL
        if n == "26":
            new = orig[: orig.index("### Bots' purpose")] + crlf(CONDENSED["26_tail"]).rstrip() + trailer(orig)
        elif n == "62":
            new = orig[: orig.index("**Phase 0 decisions")] + crlf(CONDENSED["62_tail"]).rstrip() + trailer(orig)
        else:
            new = heading + crlf(CONDENSED[n]).rstrip() + trailer(orig)
        out.append((n, s, e, new))
    return sorted(out, key=lambda t: t[1])


def archive_block(key, orig):
    if key == "header":
        return HEADER_KEY + NL + orig          # the bullets themselves, verbatim, ending at the next heading
    return orig                               # the section verbatim, its own heading included


def apply():
    md, ar = rd(MD_BAK), rd(AR_BAK)
    if hashlib.sha256(md.encode()).hexdigest() != hashlib.sha256(open(MD, "rb").read()).hexdigest():
        raise SystemExit("CLAUDE.md differs from the pass-3 backup; refusing to apply")
    p = plan(md)
    new, pos = [], 0
    for key, s, e, txt in p:
        new.append(md[pos:s]); new.append(txt); pos = e
    new.append(md[pos:])
    blocks = [archive_block(k, md[s:e]) for k, s, e, _ in p]
    pre = (NL + PASS_HDR + NL + NL +
           "Verbatim from CLAUDE.md as of backup `CLAUDE.md.pre_archive_pass3_20261005.bak` (SHA-256 "
           f"`{hashlib.sha256(open(MD_BAK, 'rb').read()).hexdigest().upper()}`); archive backup "
           "`CLAUDE_ARCHIVE.md.pre_pass3_20261005.bak` (SHA-256 "
           f"`{hashlib.sha256(open(AR_BAK, 'rb').read()).hexdigest().upper()}`). User-approved 2026-10-05. "
           "Sections 26 (operations subsections), 33, 34, 35, 36, 43, 58, 60, 62 and 63 were condensed in CLAUDE.md to "
           "current-state summaries; the full text they replaced is below, plus three header bullets. Sections 33, 43, 60 "
           "and 62 remain active, so their CLAUDE.md versions are the current state and this is the history. Produced and "
           "verified by `archive_pass3_20261005.py`." + NL + NL + "---" + NL + NL)
    wr(MD, "".join(new))
    wr(AR, ar + pre + "".join(blocks))


def verify():
    md_new, ar_new, md_bak, ar_bak = rd(MD), rd(AR), rd(MD_BAK), rd(AR_BAK)
    assert ar_new.startswith(ar_bak), "archive: earlier passes were modified"
    p3 = ar_new[ar_new.index(PASS_HDR):]
    # archived blocks, read back from the archive file
    archived = {}
    for n, s, e in sections(p3):
        archived[n or "header"] = p3[s:e]
    p = plan(md_bak)                                     # where each region sat in the original
    # rebuild: in the NEW file, replace each condensed region with the archived original
    rebuilt, pos = [], 0
    secs_new = {n: (s, e) for n, s, e in sections(md_new) if n}
    regions = []
    for key, _, _, txt in p:
        if key == "header":
            s = md_new.index(txt); regions.append((s, s + len(txt), archived["header"][len(HEADER_KEY + NL):]))
        else:
            s, e = secs_new[key]
            assert md_new[s:e] == txt, f"section {key} in CLAUDE.md is not the planned condensed text"
            regions.append((s, e, archived[key]))
    for s, e, orig in sorted(regions):
        rebuilt.append(md_new[pos:s]); rebuilt.append(orig); pos = e
    rebuilt.append(md_new[pos:])
    rebuilt = "".join(rebuilt)
    ok = rebuilt.encode() == md_bak.encode()
    print(f"round trip (new CLAUDE.md + archived text == backup, byte for byte): {'PASS' if ok else 'FAIL'}")
    print(f"archive earlier passes unchanged: PASS")
    for label, s in (("CLAUDE.md before", md_bak), ("CLAUDE.md after", md_new), ("archive before", ar_bak), ("archive after", ar_new)):
        print(f"  {label:17} {len(s):>9,} chars  {len(s.encode()):>9,} bytes")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    if "--verify" not in sys.argv:
        apply()
    verify()

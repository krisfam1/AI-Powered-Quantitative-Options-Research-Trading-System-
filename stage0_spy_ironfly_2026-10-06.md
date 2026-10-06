# Stage 0: 1-day SPY iron fly, data coverage and quote quality (2026-10-06)

This is a coverage and quote-quality check for "Options Hypothesis Study v2" (Finalist A), approved by the user on 2026-10-06.

- **No outcomes were used.** It computes no returns, no P&L, no price moves between sessions, and no signal-versus-return relationship.
- **It is not a trial:** nothing was registered or hashed, and no ledger row was added.
- **Untouched:** `option_snapshots.db`, `research_database.db` and the open experiments. `.env` was not opened.

## Headline

- **Entry quotes are fine.** About 97% of sessions have a next-session expiry and clean quotes on all four legs at the close.
- **Exit quotes are the blocker.** The study's exit is to close the in-the-money legs at *t*+1's closing quote, and EODHD can't support it:
  - EODHD returns contracts on their own expiration day **only up to 2025-06-05**, and only partly. Before that date, 30 of 120 testable sessions had a quote on all four contracts at *t*+1.
  - After that date it returns **none**: 0 of 154 sessions in the probe and 0 of 76 in the in-hand chains.
- **With that exit as written,** the surviving N would be about 100 (power 1.3% at the 3% floor). **With an intrinsic-settlement exit,** the surviving N would be about 728 (power 7.4% at the floor; detectable effect 8.5% of premium).
  - The intrinsic exit uses the SPY close on *t*+1 plus a cost assumption. It would be a design decision for the user, and is not adopted here.

## Sources and method

| Source | Covers | Requests |
| --- | --- | --- |
| In-hand: `gex_data_cache.db` `raw_records`. The GEX task stores the full SPY chain nightly, with bid and ask in `raw_json`; read-only | Entry sessions 2026-06-10 → 2026-09-30, all 78 | 0 |
| One EODHD probe (UnicornBay options EOD) | 272 sampled sessions, 2023-10-02 → 2026-06-09: runs of 4 consecutive sessions out of every 10 | **272** (all HTTP 200; no quota error; no response needed a second page) |
| Session calendar: dates column of `data_snapshots/vrp_timing_20261002/SPX_History.csv` (NYSE sessions through 2026-10-01) | — | 0 |

**Probe request:**
- SPY; `tradetime` = *t*; expirations *t* → *t* + 9 calendar days; strikes ±2.5% around the same-day SPX level ÷ 10 × 0.998.
- The SPX level centres the strike filter only. Nothing else uses it.
- The id-date rule applies.
- The responses sit in a scratch database in the session scratchpad. Not committed.

**Rules applied, each a stand-in for a study rule:**
- **Body:** the put–call-parity at-the-money strike for the *t*+1 expiry, from day-*t* quotes: the strike where |call mid − put mid| is smallest.
  - The study specifies "the strike nearest the raw SIP close", but SPY isn't in `daily_prices.db`, and the approval limited sources to data in hand plus EODHD.
  - Cross-check on the 76 in-hand sessions: against the strike nearest the GEX task's stored SPY spot, the body was the same strike 53 times and $1 away 23 times. That spot comes from a different source and time.
- **Wings:** the listed call strike nearest body + $3 and the listed put strike nearest body − $3.
- **Entry test:** bid > 0 and ask ≥ bid on all 4 legs.
- **Exit test (c):** all 4 contracts have a record on *t*+1 with ask > 0 and ask ≥ bid. A zero bid is allowed.
  - **Deliberate deviation from "the same test":** at expiry, whether a leg's bid is above zero depends on where SPY closed, so counting bid > 0 at exit would reveal outcomes. It was not computed.
- **Ex-dividend exclusion:** *t*+1 = the third Friday of Mar/Jun/Sep/Dec, or the prior session when that Friday is a holiday (2026-06-18).
  - These dates are **derived from the calendar, not checked against data.** SPY isn't in `daily_prices.db`, and that database only adjusts for splits.

## (a) Is there an expiry on the next trading session?

752 entry sessions, 2023-10-02 → 2026-09-30.

| | Sessions |
| --- | --- |
| Next-session expiry confirmed: listed on day *t* | 269 (probe) + 78 (in-hand) = 347 |
| Next-session expiry confirmed: seen listed on an earlier observed day | 326 |
| **Confirmed missing** | **0** |
| Not observed by the sample, so unknown | 79 (probe-period gaps between runs) |

- **Data gaps:** 3 probe days returned an empty response: 2024-11-27, 2025-01-13 and 2025-02-26. Their next-session expiry is counted as "seen earlier".
- **No gaps in daily expiries were found anywhere.**

## (b) Entry quotes at the close, all four legs

| | Probe (272 observed) | In-hand (78) |
| --- | --- | --- |
| Next-session expiry listed on *t* | 269 | 78 |
| Excluding ex-dividend | 264 | 76 |
| Body found (two-sided call and put) | 264 | 76 |
| Wings within $0.50 of ±$3 | 263 | 76 |
| **All 4 legs bid > 0, ask ≥ bid** | **263 (96.7% of observed)** | **76 (97.4%)** |
| Structure spread (sum of 4 leg spreads), % of net-credit mid: median / 90th pct | 3.10% / 6.15% | 2.86% / 6.04% |
| Same, % of the ATM straddle mid: median / 90th pct | 1.92% / 3.04% | 1.63% / 2.71% |

Every session that had a body had all 4 legs passing.

## (c) Exit quotes on *t*+1, same 4 contracts

| *t*+1 | Testable sessions (entry passed, *t*+1 observed) | *t*+1 response has any contract expiring that day | **All 4 contracts quoted** |
| --- | --- | --- | --- |
| ≤ 2025-06-05 | 120 | 108 | **30 (25%)** |
| > 2025-06-05 (probe + in-hand) | 154 | 0 | **0** |

- **Last date with any SPY contract returned on its own expiration day: 2025-06-05.** By year, the probe found expiring-today contracts on 27 days in 2023, 97 in 2024 and 31 in 2025, and none in 2026.
- **Same in the in-hand chains:** the GEX task requests from `exp_date_from = obs date`, yet stores no SPY contract on its expiration day (0 rows; the minimum gap is 1 day).
- **Why only 30 of 120 before the cutoff:** not investigated by leg, since a per-leg breakdown at expiry would hint at where SPY closed.

## (d) Filters and surviving N, before any outcome

**Probe-period entry waterfall (272 observed):**
- 3 lost because no next-session expiry was listed on *t*; they had empty responses.
- 5 ex-dividend.
- 0 with no body.
- 1 with a wing more than $0.50 from ±$3.
- 0 failing the entry quote test.
- **263 survive (96.7%).**

**In-hand (78):** 2 ex-dividend, **76 survive**.

| Exit rule | Projected surviving N | Power at the 3% floor | MDE at 80% power |
| --- | --- | --- | --- |
| Study as written: exit at *t*+1 closing quotes from EODHD | ≈ 100 (420 entry sessions with *t*+1 ≤ 2025-06-05 × 0.967 × 0.25) | **1.3%** | 23.0% of premium |
| Entry-quote survivors only, i.e. if the exit were intrinsic settlement on the *t*+1 close (not adopted) | ≈ 728 (674 × 0.967 + 76) | **7.4%** | 8.5% of premium |
| For reference: *t*+1 ≤ 2025-06-05 only, intrinsic exit | ≈ 406 | 3.9% | 11.4% of premium |

**How power was computed:**
- The study's declared values only: floor 3% of premium, assumed s = 0.65, one-sided α = 0.05/14, so z = 2.689.
- Power = Φ(0.03·√N / 0.65 − 2.689); MDE = (2.689 + 0.842) · 0.65 / √N.
- No dispersion was estimated from this data.

**Read:** even at N ≈ 728 the design has about 7% power at its own floor. A null would grade HELD, not REJECTED. This was already implied by the study's 8.5% MDE; Stage 0 confirms the N.

## (e) Account facts in the repo (read only; no broker API called)

- **Live account:** IBKR Pro with a balance of about **$500** (`CLAUDE_ARCHIVE.md` §62, "Phase 3 quotes", decided 2026-10-01).
- **Options trading level, permission for 4-leg spreads, permission for cash-settled index options (XSP):** **not recorded anywhere** in the repo, CLAUDE.md or the archive.
  - General fact to check with IBKR, not a project finding: multi-leg credit spreads usually need a margin account with spread permissions, and US margin accounts need at least $2,000 of equity (FINRA).
- **Paper (Alpaca) account size:** **not recorded.**
  - The bots read equity at run time.
  - The $100k figures in the repo are V1 backtest assumptions per ticker (§15–16), not the paper balance.
  - Every `TradingClient` is `paper=True` (§26).

## Files

- **This report:** the only file committed.
- **Scripts:** `stage0_spy_ironfly.py` (SHA-256 `3EDDB66942C379798BEF43E9B0272C8650EEABC8F14FA0D054D67BD722794C68`) and `s0_split.py` (`2C9062723B4DF56D66975CC800888DA78C67898F1645322CA90862BDC4BCC91F`), in the session scratchpad, not committed.
- **Probe responses:** the scratchpad's `stage0_probe.db`.
- **EODHD requests used:** 272.

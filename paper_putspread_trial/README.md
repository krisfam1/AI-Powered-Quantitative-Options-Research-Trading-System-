# Paper put-spread trial

**What this is:** a PAPER-ONLY forward trial on the Alpaca paper account, approved by the user on 2026-10-06. It builds an operations and risk track record, and its main purpose is measuring fill realism.

**What this is not:** a hypothesis test. It uses no hypothesis slot and gets no ledger row, no hash and no verdict. It makes no claim of an edge.

**Status: Phase 1, build and dry run only. No orders, not even paper orders.** Phase 2, placing paper orders, needs a separate approval from the user.

- **Script:** `paper_putspread_trial.py`. Tests: `test_paper_putspread_trial.py`, run with `python -m unittest test_paper_putspread_trial -v`.
- **Rules fixed 2026-10-06** (`RULES_VERSION`). Do not change them after seeing any result.

## Safety

- **Paper only.** The script builds its client with `paper=True` and then aborts unless two checks pass:
  - the client's endpoint is `paper-api.alpaca.markets` (`assert_paper_client`);
  - the account number starts with `PA` (`assert_paper_account`).
- **No order code.** The file contains no order-submission call; a unit test checks for this. `build_entry_order_request()` only constructs the multi-leg order object so its shape can be inspected.
- **Live mode is read-only:** account, trading calendar and option-chain snapshot. **Stored mode** reads `gex_data_cache.db` read-only.
- **Credentials** come from `.env` via python-dotenv, like the other modules here, and are never printed or logged.
- **Untouched:** V1, the three bots, their schedules, the registry, `hypothesis_ledger.csv`, the open experiments and every existing database. State and logs belong in this folder only.

## Rules (fixed 2026-10-06)

| Item | Rule |
| --- | --- |
| Underlying and structure | SPY put credit spread: sell 1 put, buy 1 put $5 lower, same expiry |
| Entry | At most one new spread per week, Monday 10:30 ET (the next trading day of that week if Monday is a holiday). A skipped week is not retried later in the week. |
| Expiry | The first listed expiration 10 to 14 calendar days after entry |
| Short put | The strike whose \|delta\| is closest to 0.15, using the quote data's greeks. Skip the week if greeks are missing, or if no strike has \|delta\| between 0.10 and 0.20 (inclusive). |
| Long put | Short strike − $5. Skip the week if that strike isn't listed. |
| Quote skips | Skip if either leg lacks bid > 0, or if the full spread bid/ask width is more than 15% of the mid credit |
| Sizing | Contracts = floor(1% of equity ÷ max loss per contract), with max loss per contract = ($5 − credit) × 100. Minimum 1 contract. Skip if 1 contract's max loss exceeds 1.5% of equity. Total open max loss must stay ≤ 2% of equity. |
| Exits | Checked hourly in market hours and at 15:45 ET. Take profit when the cost to close is ≤ 50% of the credit received. Stop when the cost to close is ≥ 2.0× the credit. Time exit at 15:45 ET two trading days before expiry. Never hold through expiry. |
| Pause | If equity falls 5% or more below its running peak since the trial began, open no new spreads and report to the user. The user decides when to resume. |
| Other filters | None: no VIX, trend or drawdown-state filter. Do not add any. |

**Details the rules leave open, fixed at build time (2026-10-06) before any result was seen:**
- **Delta tie:** goes to the lower strike, which is further out of the money.
- **Missing deltas:** a put without a delta is ignored. The week is skipped only when no put at that expiry has a delta.
- **Valid quote:** a leg also needs ask ≥ bid. A crossed or missing ask makes the mid undefined, so this is a data-validity check, not a strategy filter.
- **Spread quote for selling:** bid = short bid − long ask; ask = short ask − long bid; width = ask − bid; mid credit = (bid + ask) ÷ 2.
- **Credit used for sizing** and as the intended limit price: the mid credit.
- **The 2% total cap** reduces the contract count to the largest that fits. If not even 1 contract fits, the week is skipped.
- **Cost to close**, for both take profit and stop: the natural price, short ask − long bid. This is the price at which the spread can actually be bought back. The mid is logged too.
  - If both trigger at the same check, the logged reason priority is stop, then take profit, then time exit.
  - If the quotes are invalid, profit and stop can't be evaluated at that check, but the time exit still applies.
- **"Credit received"** in the exit rules: the actual paper fill credit in Phase 2.
- **Exit check times:** 10:00, 11:00, 12:00, 13:00, 14:00, 15:00 and 15:45 ET.
  - On early-close days: on-the-hour checks before the close, and the time exit at close − 15 minutes.
  - A missed time-exit check closes at the next check.
- **Pause threshold:** paused when equity ≤ 0.95 × peak. The peak starts at the equity on the trial's first day.

## Logging format (one JSON object per line, from Phase 2: `paper_putspread_trial/log.jsonl`)

Every decision (entry, skip, exit check) and every fill is one record.

| Field | Meaning |
| --- | --- |
| `logged_at` | ET timestamp |
| `mode` | `dry_run` or `paper` |
| `event` | `entry_decision`, `entry_fill`, `exit_check`, `exit_fill` or `pause` |
| `rules_version` | `2026-10-06` |
| `entry_date`, `expiry`, `dte_calendar` | Entry date, expiry, and the calendar days between them |
| `short`, `long` | Per leg: `symbol`, `strike`, `delta`, `bid`, `ask`, `mid`, `quote_ts` |
| `spread_quote` | `bid`, `ask`, `mid`, `width` (the quoted spread width) |
| `width_pct_of_mid` | Spread width as % of mid credit |
| `intended_credit` / `intended_debit` | The intended limit price |
| `contracts`, `max_loss_per_contract`, `max_loss`, `collateral` | Sizing |
| `equity`, `equity_peak`, `open_max_loss` | Account state at the decision |
| `action`, `skip_reason` | `open`/`skip`, or `hold`/`close` with its `reason` and `triggered` list |
| `close_natural`, `close_mid`, `close_width` | Exit checks only |
| `paper_fill_price`, `paper_fill_ts`, `order_id` | Phase 2 only: the actual paper fill |

The dry run prints the entry-decision record with these fields.

## Report format

**One row per closed trade:**
- Entry date, expiry, strikes, short delta, contracts, entry mid and width, exit date, exit reason, exit mid and width.
- P&L under the three fill assumptions:
  1. **Paper actual:** the real paper fills.
  2. **Conservative (the HEADLINE):** entry credit = mid − 0.5 × width; exit debit = mid + 0.5 × width.
  3. **Stress:** entry credit = mid − 1.0 × width; exit debit = mid + 1.0 × width.
- Benchmarks for the same dates:
  - T-bill interest on the collateral (max loss): simple, actual/365.
  - SPY buy-and-hold return from the entry date to the exit date.

**Summary:**
- Trades opened and weeks skipped, by reason; win/loss count.
- Total and average P&L under each fill assumption, headline = conservative.
- Maximum drawdown of cumulative conservative P&L.
- Largest single loss against max loss.
- Paper-actual versus conservative slippage.
- The T-bill and SPY benchmarks.
- Whether the pause rule fired.

No statistical tests, no edge claims and no verdict.

## Limits found in Phase 1 (2026-10-06)

1. **Shared paper account.** It is the same paper account the existing bots use.
   - Equity, the running peak and the pause rule will also move with the stock bot's and options bot's P&L.
   - `live_options_trader.py` counts **every** option position on the account against its 3-position cap. Each spread leg is a position, so one trial spread would take 2 of the options bot's 3 slots.
   - A separate Alpaca paper account would remove both problems. This is the user's decision before Phase 2.
2. **Quote feed.** Only Alpaca's INDICATIVE options feed is available (`OPRA agreement is not signed`).
   - Indicative quotes are not real exchange quotes. Spreads on it looked unrealistically tight: $0.01 per leg on SPY.
   - So the 15% width skip and the conservative and stress fills computed from it understate real costs. Paper fills will tell us more.
3. **Multi-leg orders.** The account is at options level 3 (approved and trading), which is Alpaca's level for spreads.
   - The SDK (alpaca-py 0.44.0) supports `OrderClass.MLEG`, and the order object builds correctly.
   - Actual acceptance of an mleg order can't be confirmed without placing one.
   - The limit-price sign convention for a credit mleg order is unverified. Confirm both at the start of Phase 2.
4. **Expiration listings.** SPY has daily expirations, but the contract list on 2026-10-06 skipped 2026-10-21 and 10-22, perhaps not yet listed. "First listed expiration" uses what is listed at entry time.
5. **Missing deltas.** 64 of 418 SPY puts expiring 10–14 days out had no delta on 2026-10-06.
6. **Stored chains:** EODHD end-of-day quotes, not 10:30 ET quotes. They are only good for checking the script.
7. **T-bill rate source for Phase 2.** The repo's snapshot of Treasury bill rates ends 2026-10-02, so Phase 2 needs a current rate source.

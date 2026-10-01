# Execution-cost measurement — design v1 (2026-10-01, for review; NOT implemented)

**Purpose (decided 2026-10-01):** StockTradingBot and OptionsShadowLoop become an instrument for measuring real execution cost — what we pay to cross the bid/ask — compared against the project's pricing/spread models. They are no longer a test of the V1 signal (rejected, Section 13/18).

## 0. Two facts that shape the design

1. **Current logs cannot measure spread cost.**
   - At options entry, `live_options_trader.py` reads the ask (`get_live_premium`, line 289), sends a market order, and **overwrites** the logged premium with the fill (lines 327–333). The pre-trade quote is lost and the **bid is never captured**, so no mid exists to measure against.
   - Exits (`options_exit_monitor.py:50–118`) are the same: the bid is read, then overwritten by the fill.
   - `options_trades.db` therefore holds fill prices only.
2. **Alpaca paper fills are simulated.** They fill at (or near) the quoted NBBO, with no market impact, queue position, or partial-fill realism. Paper fills therefore measure **the quoted spread at decision time plus quote staleness**, not true live execution. That is still the quantity our models get wrong (V1's tiered estimate; the EOD-quote basis of the −$45,477 correction), but it is a **lower bound** on real cost. Real-money impact cannot be measured on paper.

## 1. Data streams

### Stream A — fill log (validation, low volume)
Wrap the existing entry and exit order calls with **logging only**. Order logic, sizing and signals are unchanged. For each fill, write one row to a new `execution_cost_log.db`, table `fills`:

| Field | Source |
|---|---|
| order_id, trade_id, bot, ticker, contract_symbol (or stock), side (buy/sell), qty, order_type | order request |
| decision_ts | when the bot decided |
| quote_ts, bid, ask, bid_size, ask_size | one `OptionLatestQuoteRequest`/`StockLatestQuoteRequest` **immediately before submit** (bid AND ask) |
| mid = (bid+ask)/2, quoted_half_spread_pct = (ask−bid)/(2·mid) | derived |
| submit_ts, fill_ts, fill_price (`filled_avg_price`), filled_qty, latency_ms | order polling already in the code |
| underlying_spot, dte, moneyness, delta (from the live Greeks already computed) | existing |
| **realized_half_spread_pct** = side·(fill − mid)/mid (buy: +, sell: −) | derived — the paid cost |
| **staleness_pct** = side·(fill − touch)/mid, touch = ask (buy) / bid (sell) | derived — fill vs quoted touch |
| **model_v1_half_spread_pct** = `options_backtest_engine._estimated_spread_cost_pct(premium)/2` | V1's synthetic model (tiers 2/4/7/12%) |
| **eodhd_eod_half_spread_pct** for the same contract and date | filled in the next evening from the EODHD chain (the basis of the −$45,477 estimate) |

### Stream B — quote sampler (the main measurement, high volume, no orders)
Paper fills ≈ quotes, so sampling quotes directly gives the same information far faster. Every options-loop cycle (60s, market hours only), snapshot NBBO for a fixed panel and append to the `quotes` table with the same derived fields:
- Tickers: the 6 research tickers + SPY.
- Contracts per ticker: call and put at the delta closest to 0.30 (V1/live convention) and at ATM, in the 7–16 and 30–45 DTE buckets (the IV term-structure buckets), so up to 8.
- That's ~50 quotes/min, ~19k/day. Calls go to Alpaca's quote endpoint, not EODHD, so the EODHD quota is untouched.
- It is pure logging inside the existing loop, wrapped in try/except so it can never affect trading (same pattern as the existing ML shadow logging).

## 2. Comparisons

Each one is reported by premium tier (<$1, $1–2, $2–5, ≥$5, matching V1's tiers), moneyness/delta bucket, DTE bucket, ticker, and time of day:

1. **Intraday quoted half-spread vs V1's tiered model:** is V1's 1–6% half-spread too optimistic or pessimistic, and where?
2. **Intraday vs EODHD end-of-day half-spread for the same contract and day:** is the −$45,477 real-execution estimate (built on EOD quotes) biased by EOD spread behaviour?
3. **Fills vs quotes (Stream A):** does the paper fill land at the touch (staleness ≈ 0)? This validates using Stream B as the cost proxy.
4. **Time of day:** open/close spreads vs mid-day. V1 entered on 5-minute bar closes at any time of day.

## 3. How long until it says something meaningful

- **Cost distribution (Stream B):** to estimate a tier's mean half-spread within ±0.5 percentage points needs n ≈ (SD/0.5)². With a plausible SD of 2–4pp, that's 16–64 independent observations per cell. One day of sampling gives thousands of quotes, but they're serially correlated within a contract-day, so the binding constraint is **trading days**. **~20 trading days (about one month)** gives a usable cost table across tiers, moneyness, DTE and time of day.
- **Fill validation (Stream A):** ~30–50 options fills settle whether paper fill ≈ touch. The options bot averaged ~1.5 fills/day in Aug–Sep but has had **none since 9/17**, so this could take **1–3+ months** and isn't guaranteed. That's why Stream B, not fills, is the primary measurement.
- **"Could a 0.2–0.3 correlation signal survive costs?"** That also needs the signal's dollar edge, so it's a two-part calculation:
  - (a) translate a correlation into expected P&L per trade for a concrete volatility trade (e.g. buy/sell an ATM straddle or calendar when the forecast diverges from implied);
  - (b) subtract the measured round-trip cost: a straddle crosses the spread on 2 legs × 2 sides, so ≈ 2 × full spread.
  - Part (b) needs Stream B (about one month). **Part (a) and a first version of (b) can be done *now* without waiting:** the IV term-structure Stage 1 window already has historical EODHD bid/ask for every contract, so an economic sanity check on Stage 1 (r = −0.28) using real EOD spreads is possible today, with Stream B later checking whether EOD spreads over- or under-state intraday cost.

## 4. What it cannot tell us
- True live costs (market impact, queue position, partial fills): paper simulation.
- Anything about the V1 signal's edge (rejected).
- Costs for size larger than the bots' small orders.

## 5. Implementation outline (after review)
- New `execution_cost_logger.py`: quote fetch + insert helpers + EOD backfill of the EODHD half-spread.
- Three one-line hooks: before/after submit in `live_options_trader.py` and `options_exit_monitor.py`, and in `live_trader.py` for stock (low value; optional).
- The Stream B sampler is called once per cycle from `options_shadow_loop.py`.
- Nightly: add an "execution cost log grew" check to `health_check.py`.
- No changes to signals, sizing, order types or exits. Bots restart only at their nightly cycle.

## 6. Decisions needed from you
1. Approve Stream B as the primary measurement and Stream A as validation.
2. Include the stock bot? Low value for the options-cost question; it adds noise.
3. Do the "economic sanity check on IV Stage 1 with historical EODHD spreads" now (pure analysis, no waiting)?

# IV term-structure Stage 1 — economic sanity check (2026-10-01)

**Exploratory / descriptive only.** Not a pre-registered test, not a re-test of `iv_term_structure_slope_v2_20261001`, and not a verdict. No pre-registration file or registry row was touched. No date ≥ 2026-09-10 (Stage 2) was used. No EODHD calls. Script: `iv_stage1_economic_sanity_check.py`; raw output: `iv_stage1_economic_sanity_check_results.json`.

## Question
Could a signal of Stage 1's size (term-structure slope vs 20-day forward realized vol, r ≈ −0.28) pay for real bid/ask costs on a tradeable volatility position?

## Key point of method
A straddle or variance swap pays **realized minus implied** vol, not realized vol. A signal that predicts RV only because it tracks the IV level is already priced in. So the tradeable question is whether the slope predicts **(RV20 − IV)/IV**, the approximate return on premium of a delta-hedged straddle.

## Data
- **Signal/IV/RV:** `xgboost_volatility_dataset.db`, the same near (7–16 DTE) / far (30–45 DTE) slope construction, 6 tickers, 2023-10-30 → 2026-07-21. IV = `far_iv` (closest horizon to 20 trading days).
  - It reproduces Stage 1: on Stage 1's window, 604 rows / 101 days, r(slope, RV20) = −0.25 Pearson, −0.30 Spearman (registered: −0.28).
  - `far_iv` sits at the matched median strike, not ATM. Checked against real ATM IV on 168 overlapping ticker-days: corr 0.99, median ratio 1.008. A good proxy.
- **Costs:** real EODHD end-of-day bid/ask for ATM straddles, `gex_data_cache.db` raw chains, 2026-06-10 → 2026-09-09. **Stage 1's own window has no stored bid/ask**; these are the only historical chains on disk.

## Costs (ATM straddle, full relative spread = round trip)
| | AAPL | TSLA | NVDA | AMD | SMCI | MSTR | Pooled median |
|---|---|---|---|---|---|---|---|
| ~30 DTE (25–45) | 5.0% | 1.6% | 2.6% | 6.4% | 10.1% | 7.8% | **4.8%** |
| 7–16 DTE | 8.2% | 2.7% | 3.7% | 6.8% | 7.3% | 6.2% | 5.9% |

Hold to expiry pays about half of the round-trip figure. Delta-hedging costs are not included.

## Edge
Trade tested: long straddle when the slope is in its most-inverted quintile, short when it is in its steepest quintile. The trade is balanced long/short, so the unconditional vol premium cancels and what remains is the signal.

| Period | Days | Spearman slope→RV20 | Spearman slope→(RV−IV)/IV | Gross / trade | Net, round trip (per-ticker cost) | 95% CI (net) |
|---|---|---|---|---|---|---|
| **Stage 1 window** 2026-01-15→06-10 | 101 | −0.30 | −0.10 | +4.4% | **−1.1%** (hold to expiry +1.6%) | −11.3% … +7.4% |
| **Before Stage 1** 2023-10-30→2026-01-14 (never used by it) | 551 | **−0.00** | +0.04 | −2.9% | **−8.8%** | −13.3% … −3.6% |
| 2026-06-11→07-21 | 27 | +0.02 | −0.08 | +3.7% | −2.1% | (27 days; uninformative) |

Confidence intervals use a 20-trading-day block bootstrap (targets overlap).

- **Most of Stage 1's correlation is the IV level.** In Stage 1 the slope correlates −0.38 with far IV. Controlling for far IV and trailing RV, the partial correlation with RV20 is **+0.09** (wrong sign). The slope's correlation with the straddle payoff is only −0.07 (Pearson) / −0.10 (Spearman).
- **Break-even:** with Stage 1's payoff SD (0.37), the quintile trade needs |corr with the straddle payoff| ≈ **0.09 round trip, 0.05 hold to expiry**. Stage 1's 0.07–0.10 is right at that line, with a confidence interval spanning both signs.
- **Not present in the earlier history:** the slope→RV relationship is absent in the 2.2 years before Stage 1 (Spearman −0.002 over 551 days), and the trade loses money there after costs.

## Answer
**Roughly: no, not on this evidence.** Stage 1's r ≈ −0.28 is real as a forecast of realized vol, but almost all of it comes through the IV level, which option prices already charge. What's left is about one round-trip spread on the window where the effect was found, and negative in the earlier history.

Even a VALIDATED Stage 2 (which tests RV, not RV−IV) would not by itself make this tradeable.

## Caveats
- EOD spreads; intraday spreads may differ. Stream B can't settle this until real OPRA quotes are available (the account currently has only Alpaca's indicative feed).
- Spreads were measured Jun–Sep 2026, not in Stage 1's window.
- (RV−IV)/IV is an approximation of delta-hedged straddle P&L. No hedging costs, no calendar or variance-swap pricing.
- Exploratory. The registered Stage 2 test, its decision rules and its lock date are unchanged.

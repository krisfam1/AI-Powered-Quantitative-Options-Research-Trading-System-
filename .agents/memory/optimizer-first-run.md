---
name: Optimizer first-run findings
description: Key takeaways from the first 10-iteration Claude-driven optimization pass on AAPL/TSLA/NVDA/KO/JPM
---

## Best configs found

**Iteration 4** — best net P&L (+8.13%), 49.0% win rate, 102 trades
- stop=1.0×ATR, target=1.0×ATR, trail_trigger=0.8×ATR, trail_dist=2.0×ATR
- rv_threshold=1.5, time_window ON (10:00–15:00 ET), vwap_trend ON, atr_percentile ON (min=60, lookback=50)

**Iteration 3** — most trades (253) with positive P&L (+4.65%), 42.7% win rate
- stop=1.0×ATR, target=1.2×ATR, atr_percentile ON (min=60), vwap ON, no time window
- Shows that ATR percentile gate is the single biggest win-rate driver

## Win rate ceiling

The strategy never exceeded 50% win rate across 10 iterations. The ceiling is a fundamental signal-quality problem, not an exit-parameter problem. A pure 5-min breakout + RV signal on liquid mega-caps (AAPL/TSLA/NVDA/KO/JPM) generates too many false entries at intraday highs.

**Why:** Liquid names have tight spreads and institutional activity that fades breakouts; the 20-30 bar lookback flags already-established ranges, not fresh ones.

## Per-ticker patterns

- **JPM**: structural laggard — 16–33% WR across all 10 iterations; consider dropping or running separately
- **KO**: low-vol, small avg wins; ATR percentile filter often screens it out entirely (positive — fewer bad trades)
- **AAPL**: strongest and most consistent; 49–68% WR when filters are active
- **TSLA**: high variance; big avg wins on winners, but WR swings 28–58% depending on config
- **NVDA**: second-best with ATR filter on; terrible without it (23% WR baseline)

## Filter impact summary

| Filter | Effect |
|--------|--------|
| `use_vwap_trend=True` | Alone: hurts (kills entries without fixing exits). Combined with ATR pct: neutral |
| `use_atr_percentile=True, min=60-70` | Biggest single win-rate driver (+7-15 pp) |
| `use_time_window=True (10:00–15:00)` | Reduces trade count 50-60%, modestly lifts WR |
| `rv_threshold > 1.7` | Over-filters — kills too many valid setups (trade count <50) |

## What to try next

To break past 50% ceiling:
1. **Drop JPM** from the universe — it's a consistent drag
2. **Require multi-bar breakout** (price must hold above prior high for N bars, not just close)
3. **Day-of-week or pre-market gap filter** — avoid breakouts on gap-up opens (fade territory)
4. **Trend filter on daily bars** — only take breakouts in the direction of the 20-day trend
5. **Longer lookback window** (60+ bars = ~5 hours) to avoid entries into already-run moves

**Why:** These address the root cause (false breakouts into exhaustion) rather than tuning exit math.

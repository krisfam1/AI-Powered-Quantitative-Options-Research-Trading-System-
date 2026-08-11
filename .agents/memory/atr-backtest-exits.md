---
name: ATR backtest exits
description: Volatility-adjusted exit behavior for the intraday backtest
---

The intraday backtest uses the prior 14 bars to calculate ATR, then derives initial stop and target levels from ATR multipliers. The trailing stop can only move upward.

**Why:** Fixed percentage exits do not adapt to changing intraday volatility and can make historical strategy results misleading.

**How to apply:** Keep the ATR window and exit-reason labels consistent when comparing future backtest runs; clear the trade table before a strategy-definition change.
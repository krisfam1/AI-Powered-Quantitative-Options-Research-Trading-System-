from dotenv import load_dotenv
load_dotenv()

"""
Compares three real, established volatility estimation approaches
PURELY on stability and plausibility -- never on resulting P&L or
profitability, per explicit instruction. All three are standard,
published methodologies, not invented or tuned for this project:

A) Daily-bar historical vol, recomputed once per trading day (reduces
   noise via longer, cleaner daily-close data; still has a step-change
   at each new day boundary)

B) EWMA (RiskMetrics standard, lambda=0.94) -- the actual industry-
   standard volatility model used in risk management since the 1990s.
   Updates gradually every single bar using exponentially-weighted
   squared returns, so no single 5-minute observation can cause a
   large, sudden jump.

C) Hybrid -- daily-bar base estimate, but blended toward gradually via
   EWMA across day boundaries too (smooths the day-to-day transition
   that approach A still has).

Evaluation is on STABILITY metrics only: max single-step % change in
the vol estimate, distribution of changes, and whether the specific
AAPL 8/13 idx=245->246 scenario (the real, confirmed bug) is resolved.
"""

import math
from datetime import datetime, timezone, timedelta
import backtest_engine as be

end = datetime.now(timezone.utc)
start = end - timedelta(days=120)
bars = be.get_historical_bars("AAPL", start, end)

# Build daily closes by aggregating the 5-min bars we already have -- no new data source needed
daily_closes = {}
for b in bars:
    d = b.timestamp.date()
    daily_closes[d] = float(b.close)  # last close of each day wins, since bars are chronological
daily_dates_sorted = sorted(daily_closes.keys())


def approach_A_daily_bar(bars, index, lookback_days=20):
    """Daily-bar historical vol, recomputed once per trading day."""
    current_date = bars[index].timestamp.date()
    day_position = daily_dates_sorted.index(current_date) if current_date in daily_dates_sorted else 0
    if day_position < lookback_days:
        return 0.30
    recent_dates = daily_dates_sorted[day_position - lookback_days:day_position]
    closes = [daily_closes[d] for d in recent_dates]
    returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0]
    if len(returns) < 2:
        return 0.30
    mean_r = sum(returns) / len(returns)
    var = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    return max(math.sqrt(var) * math.sqrt(252), 0.10)


_ewma_state = {"variance": None}
def approach_B_ewma(bars, index, lam=0.94):
    """RiskMetrics-standard EWMA, updated every bar using squared 5-min log returns."""
    if index < 1:
        return 0.30
    r = math.log(float(bars[index].close) / float(bars[index - 1].close)) if float(bars[index - 1].close) > 0 else 0
    if _ewma_state["variance"] is None:
        _ewma_state["variance"] = r ** 2 if r != 0 else 0.0001
    else:
        _ewma_state["variance"] = lam * _ewma_state["variance"] + (1 - lam) * (r ** 2)
    period_vol = math.sqrt(_ewma_state["variance"])
    return max(period_vol * math.sqrt(252 * 78), 0.10)


_hybrid_state = {"vol": None, "last_date": None}
def approach_C_hybrid(bars, index, lam_daily=0.90):
    """Daily-bar base estimate, blended toward gradually via EWMA across day boundaries."""
    current_date = bars[index].timestamp.date()
    daily_target = approach_A_daily_bar(bars, index)
    if _hybrid_state["vol"] is None:
        _hybrid_state["vol"] = daily_target
    elif current_date != _hybrid_state["last_date"]:
        _hybrid_state["vol"] = lam_daily * _hybrid_state["vol"] + (1 - lam_daily) * daily_target
    _hybrid_state["last_date"] = current_date
    return _hybrid_state["vol"]


results = {"A": [], "B": [], "C": []}
for idx in range(60, len(bars)):
    results["A"].append(approach_A_daily_bar(bars, idx))
    results["B"].append(approach_B_ewma(bars, idx))
    results["C"].append(approach_C_hybrid(bars, idx))

print("=" * 70)
print("STABILITY COMPARISON (higher max-jump = less stable, less realistic)")
print("=" * 70)
for name, series in results.items():
    max_jump = 0.0
    jumps_over_10pct = 0
    for i in range(1, len(series)):
        if series[i-1] > 0:
            rel_jump = abs(series[i] - series[i-1]) / series[i-1]
            max_jump = max(max_jump, rel_jump)
            if rel_jump > 0.10:
                jumps_over_10pct += 1
    print("Approach " + name + ": max single-step jump=" + str(round(max_jump*100,1)) + "%, bars with >10% jump=" + str(jumps_over_10pct) + "/" + str(len(series)))

print("\n" + "=" * 70)
print("SPECIFIC BUG CHECK: AAPL 2026-08-13 13:30-13:35 UTC (the confirmed 98.5%-in-5-min case)")
print("=" * 70)
from datetime import datetime as _dt, timezone as _tz
target_ts_1 = _dt(2026, 8, 13, 13, 30, tzinfo=_tz.utc)
target_ts_2 = _dt(2026, 8, 13, 13, 35, tzinfo=_tz.utc)
idx_245 = next((i for i, b in enumerate(bars) if b.timestamp == target_ts_1), None)
idx_246 = next((i for i, b in enumerate(bars) if b.timestamp == target_ts_2), None)

if idx_245 is None or idx_246 is None:
    print("Could not locate the exact target timestamps in this data fetch.")
else:
    idx_245_pos = idx_245 - 60
    idx_246_pos = idx_246 - 60
    for name, series in results.items():
        if 0 <= idx_245_pos < len(series) and 0 <= idx_246_pos < len(series):
            v245, v246 = series[idx_245_pos], series[idx_246_pos]
            rel_change = abs(v246 - v245) / v245 * 100 if v245 else 0
            print("Approach " + name + ": vol at 13:30=" + str(round(v245,4)) + " at 13:35=" + str(round(v246,4)) + " (" + str(round(rel_change,1)) + "% change)")
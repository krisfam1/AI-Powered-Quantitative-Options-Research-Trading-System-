from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timezone, timedelta, date
import backtest_engine as be
from backtest_engine import get_daily_regime
from entry_scorer import calculate_entry_score
from options_backtest_engine import calculate_historical_volatility

end = datetime.now(timezone.utc)
start = end - timedelta(days=30)
bars = be.get_historical_bars("AAPL", start, end)

target_date = date(2026, 8, 13)
target_indices = [i for i, b in enumerate(bars) if b.timestamp.date() == target_date and i >= 60]

print("Raw qualifying-moment trace for AAPL on " + str(target_date) + " (independent of position state):\n")

spy_regime_cache = {"regime": "neutral", "last_checked": None}
qualifying_count = 0

for idx in target_indices:
    ts = bars[idx].timestamp
    if not be.check_breakout(bars, idx, lookback=20):
        continue

    if spy_regime_cache["last_checked"] is None or (ts.date() - spy_regime_cache["last_checked"]).days >= 5:
        spy_regime_cache["regime"] = get_daily_regime("SPY", ts, period=50)
        spy_regime_cache["last_checked"] = ts.date()

    score_result = calculate_entry_score("AAPL", bars, idx, "call", spy_regime=spy_regime_cache["regime"])
    qualifies = score_result["total_score"] >= 20

    if qualifies:
        qualifying_count += 1
        print("idx=" + str(idx) + " time=" + str(ts) + " score=" + str(score_result["total_score"]) + " -- QUALIFIES")

print("\nTotal raw qualifying moments (breakout=True AND score>=20): " + str(qualifying_count))
print("(This is independent of whether a position was already open -- tells us if entry LOGIC itself agrees)")
from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timezone, timedelta, date
import backtest_engine as be
from delta_strike_finder import find_strike_for_target_delta
from options_backtest_engine import calculate_historical_volatility, black_scholes_price, _estimated_spread_cost_pct

end = datetime.now(timezone.utc)
start = end - timedelta(days=30)
bars = be.get_historical_bars("AAPL", start, end)

entry_idx = 245
entry_price = float(bars[entry_idx].close)
entry_vol = calculate_historical_volatility(bars, entry_idx)
strike = find_strike_for_target_delta(entry_price, 14, entry_vol, "call", 0.30)
expiry_date = bars[entry_idx].timestamp.date() + timedelta(days=14)
entry_premium = black_scholes_price(entry_price, strike, 14, entry_vol, option_type="call")
entry_premium = entry_premium * (1 + _estimated_spread_cost_pct(entry_premium) / 2)

print("Position opened at idx=" + str(entry_idx) + " (" + str(bars[entry_idx].timestamp) + ")")
print("Strike=$" + str(strike) + " entry_premium=$" + str(round(entry_premium, 3)) + "\n")
print("Entry stock price: $" + str(round(entry_price, 2)) + " entry vol: " + str(round(entry_vol, 4)))
print("idx=246 stock price: $" + str(round(float(bars[246].close), 2)) + " idx=246 vol: " + str(round(calculate_historical_volatility(bars, 246), 4)))
print("days_left at entry: " + str((expiry_date - bars[entry_idx].timestamp.date()).days))
print("days_left at idx=246: " + str((expiry_date - bars[246].timestamp.date()).days))
print("")

stop_loss_pct = 0.40

for idx in range(entry_idx + 1, min(entry_idx + 100, len(bars))):
    ts = bars[idx].timestamp
    current_price = float(bars[idx].close)
    days_left = (expiry_date - ts.date()).days
    vol = calculate_historical_volatility(bars, idx)
    current_value = black_scholes_price(current_price, strike, max(days_left, 0), vol, option_type="call")
    pct_change = (current_value - entry_premium) / entry_premium if entry_premium else 0

    exit_reason = None
    if pct_change <= -stop_loss_pct:
        exit_reason = "stop_loss"
    elif pct_change >= 0.40 and idx >= entry_idx + 6:
        closes = [float(bars[i].close) for i in range(idx - 6, idx + 1)]
        ma_before = sum(closes[-7:-2]) / 5
        last_two = closes[-2:]
        if all(c < ma_before for c in last_two):
            exit_reason = "reversal_guard"
    if exit_reason is None and pct_change >= 0.75:
        exit_reason = "take_profit"

    if idx in [315, 316, 321, 322]:
        print("idx=" + str(idx) + " (" + str(ts) + "): price=$" + str(round(current_price,2)) + " value=$" + str(round(current_value,3)) + " (" + str(round(pct_change*100,1)) + "%) -- [SECOND QUALIFYING WINDOW]")

    if exit_reason:
        print("\n*** EXIT at idx=" + str(idx) + " (" + str(ts) + "): " + exit_reason + " at " + str(round(pct_change*100,1)) + "% ***")
        print("Second qualifying window was at idx 315-322 -- exit happened " + ("BEFORE" if idx < 315 else "AFTER") + " that window")
        break
else:
    print("Position never closed within the traced window.")
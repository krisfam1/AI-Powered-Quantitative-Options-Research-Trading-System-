from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timezone, timedelta, date
import backtest_engine as be
from options_backtest_engine import calculate_historical_volatility, black_scholes_price
from delta_strike_finder import find_strike_for_target_delta

end = datetime.now(timezone.utc)
start = end - timedelta(days=30)
bars = be.get_historical_bars("AAPL", start, end)

target_date = date(2026, 8, 11)
target_indices = [i for i, b in enumerate(bars) if b.timestamp.date() == target_date]

print("Total bars on " + str(target_date) + ": " + str(len(target_indices)))
print("\nTracing volatility, price, and computed put option value across the day:\n")

# Use the FIRST bar of the day as a stand-in entry point for this trace
entry_index = target_indices[0] if target_indices else None
if entry_index is None:
    print("No bars found for this date.")
else:
    entry_price = float(bars[entry_index].close)
    entry_vol = calculate_historical_volatility(bars, entry_index)
    strike = find_strike_for_target_delta(entry_price, 14, entry_vol, "put", 0.30)
    entry_premium = black_scholes_price(entry_price, strike, 14, entry_vol, option_type="put")

    print("ENTRY at index " + str(entry_index) + ": price=$" + str(round(entry_price, 2)) + " vol=" + str(round(entry_vol, 4)) + " strike=$" + str(strike) + " premium=$" + str(round(entry_premium, 3)))
    print("")

    for idx in target_indices[1:15]:  # trace the next several bars
        current_price = float(bars[idx].close)
        current_vol = calculate_historical_volatility(bars, idx)
        days_left = 14  # same day, DTE hasn't decremented
        current_value = black_scholes_price(current_price, strike, days_left, current_vol, option_type="put")
        pct_change = (current_value - entry_premium) / entry_premium if entry_premium else 0

        print("idx=" + str(idx) + " price=$" + str(round(current_price, 2)) + " vol=" + str(round(current_vol, 4)) + " -> option_value=$" + str(round(current_value, 3)) + " (" + str(round(pct_change * 100, 1)) + "%)")
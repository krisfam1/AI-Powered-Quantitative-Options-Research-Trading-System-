from dotenv import load_dotenv
load_dotenv()

"""
Tests the underlying-price-sourcing hypothesis directly: for a mismatched
trade, back-solves what underlying price WOULD be needed to reproduce
the originally-saved price (given the same real strike/IV/DTE), then
compares that implied price against the EOD close used in the new
validation script.
"""

import sqlite3
from options_backtest_engine import black_scholes_price

def solve_spot_from_price(target_price, strike, dte, vol, option_type="call", risk_free_rate=0.04):
    low, high = 1.0, 2000.0
    for _ in range(100):
        mid = (low + high) / 2
        price = black_scholes_price(mid, strike, dte, vol, risk_free_rate, option_type)
        if price < target_price:
            low = mid
        else:
            high = mid
        if abs(high - low) < 0.001:
            break
    return (low + high) / 2

with sqlite3.connect("iv_correction_diagnostic.db") as conn:
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM diagnostic WHERE ticker='AMD' AND entry_date='2026-06-24'").fetchone()

print("AMD 2026-06-24:")
print("  Saved iv_corrected_price: $" + str(row["iv_corrected_price"]))
print("  Real strike: " + str(row["real_strike"]) + " | historical_iv: " + str(row["historical_iv"]) + " | actual_dte: " + str(row["actual_dte"]))

implied_spot = solve_spot_from_price(row["iv_corrected_price"], row["real_strike"], row["actual_dte"], row["historical_iv"])
print("  Implied underlying price (back-solved from saved price): $" + str(round(implied_spot, 2)))
print("  EOD close used in validation script: $ (check against printed V2 output -- was underlying_price used)")

# Recompute with new EOD price to show the delta
import backtest_engine as be
from datetime import datetime, timezone, timedelta
obs_dt = datetime(2026, 6, 24, tzinfo=timezone.utc)
bars = be.get_historical_bars("AMD", obs_dt, obs_dt + timedelta(days=1))
eod_close = float(bars[-1].close) if bars else None
print("  Actual EOD close fetched: $" + str(eod_close))
print("  Difference: $" + str(round(abs(implied_spot - eod_close), 2) if eod_close else "N/A") + " (" + str(round(abs(implied_spot-eod_close)/implied_spot*100,1) if eod_close else "N/A") + "% )")
from dotenv import load_dotenv
load_dotenv()

from options_evaluator import get_live_premium

signals = [
    ("TSLA260831P00342500", 4.99, 2, "2026-08-24 19:05"),
    ("TSLA260831P00342500", 5.08, 1, "2026-08-24 19:00"),
    ("TSLA260831P00342500", 3.87, 2, "2026-08-24 18:49"),
    ("TSLA260831P00342500", 3.01, 3, "2026-08-24 17:49"),
    ("AMD260831P00465000", 20.83, 1, "2026-08-24 13:55"),
    ("AMD260831P00480000", 27.70, 1, "2026-08-24 13:35"),
]

print("Checking current hypothetical P&L on today's shadow signals:\n")

total_pnl = 0.0

for symbol, entry_premium, contracts, logged_at in signals:
    try:
        current_premium = get_live_premium(symbol)
        pct_change = (current_premium - entry_premium) / entry_premium * 100
        pnl_dollars = (current_premium - entry_premium) * contracts * 100
        total_pnl += pnl_dollars
        status = "WIN" if pnl_dollars > 0 else ("LOSS" if pnl_dollars < 0 else "FLAT")

        print(logged_at + " " + symbol + " (entry $" + str(entry_premium) + " x " + str(contracts) + "):")
        print("  Current: $" + str(round(current_premium, 2)) + " (" + str(round(pct_change, 1)) + "%)")
        print("  Hypothetical P&L: $" + str(round(pnl_dollars, 2)) + " (" + status + ")")
        print()
    except Exception as exc:
        print(logged_at + " " + symbol + ": could not fetch current price - " + str(exc))
        print()

print("Total hypothetical P&L across today's signals: $" + str(round(total_pnl, 2)))
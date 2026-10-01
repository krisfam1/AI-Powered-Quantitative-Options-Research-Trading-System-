from dotenv import load_dotenv
load_dotenv()

from options_evaluator import get_live_premium

signals_today = [
    ("TSLA260831P00342500", 3.53, 2),
    ("AMD260831P00480000", 27.70, 1),
    ("TSLA260831P00342500", 3.70, 2),
    ("AMD260831P00480000", 29.13, 1),
    ("AMD260831P00465000", 20.83, 1),
    ("TSLA260831P00342500", 3.01, 3),
]

print("Checking hypothetical P&L on today's shadow signals:\n")

total_pnl = 0.0

for symbol, entry_premium, contracts in signals_today:
    try:
        current_premium = get_live_premium(symbol)
        pct_change = (current_premium - entry_premium) / entry_premium * 100
        pnl_dollars = (current_premium - entry_premium) * contracts * 100
        total_pnl += pnl_dollars

        status = "WIN" if pnl_dollars > 0 else ("LOSS" if pnl_dollars < 0 else "FLAT")

        print(symbol + " (entry $" + str(entry_premium) + " x " + str(contracts) + "):")
        print("  Current: $" + str(round(current_premium, 2)) + " (" + str(round(pct_change, 1)) + "%)")
        print("  Hypothetical P&L: $" + str(round(pnl_dollars, 2)) + " (" + status + ")")
        print()
    except Exception as exc:
        print(symbol + ": could not fetch current price - " + str(exc))
        print()

print("Total hypothetical P&L across all shadow signals today: $" + str(round(total_pnl, 2)))
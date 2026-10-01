from dotenv import load_dotenv
load_dotenv()

import sqlite3
from options_evaluator import get_live_premium
from options_data import get_options_chain, filter_near_the_money, pick_best_contract
import backtest_engine as be
from datetime import datetime, timezone, timedelta


def analyze_forward_test_log() -> None:
    """
    Review all logged gamma/charm modifier snapshots and check how price has
    moved since each one was recorded, building real evidence over time.

    Honest limitation: this can only compare against price NOW, not the
    price at some fixed future point -- so early entries get more time to
    "play out" than recent ones. Treat this as an ongoing, growing picture,
    not a final verdict, especially with a small sample size.
    """
    with sqlite3.connect("gamma_forward_test.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM forward_test_log ORDER BY logged_at ASC"
        ).fetchall()

    if not rows:
        print("No forward-test data logged yet.")
        return

    print("Reviewing " + str(len(rows)) + " forward-test snapshot(s):\n")

    sized_up_moves = []
    sized_down_moves = []
    neutral_moves = []

    for row in rows:
        ticker = row["ticker"]
        price_at_log = row["price_at_log"]
        modifier = row["modifier"]
        logged_at = row["logged_at"]

        try:
            now = datetime.now(timezone.utc)
            bars = be.get_historical_bars(ticker, now - timedelta(days=2), now)
            if not bars:
                continue
            current_price = float(bars[-1].close)
        except Exception:
            continue

        move_pct = (current_price - price_at_log) / price_at_log * 100 if price_at_log else 0

        print("  " + ticker + " logged " + logged_at[:16] + " @ $" + str(round(price_at_log, 2)) +
              " (modifier=" + str(modifier) + "x) -> now $" + str(round(current_price, 2)) +
              " (" + str(round(move_pct, 2)) + "%)")

        if modifier > 1.0:
            sized_up_moves.append(move_pct)
        elif modifier < 1.0:
            sized_down_moves.append(move_pct)
        else:
            neutral_moves.append(move_pct)

    print("\n--- Summary ---")
    if sized_up_moves:
        avg = sum(sized_up_moves) / len(sized_up_moves)
        print("Sized UP recommendations (" + str(len(sized_up_moves)) + "): avg subsequent move = " + str(round(avg, 2)) + "%")
    if sized_down_moves:
        avg = sum(sized_down_moves) / len(sized_down_moves)
        print("Sized DOWN recommendations (" + str(len(sized_down_moves)) + "): avg subsequent move = " + str(round(avg, 2)) + "%")
    if neutral_moves:
        avg = sum(neutral_moves) / len(neutral_moves)
        print("Neutral recommendations (" + str(len(neutral_moves)) + "): avg subsequent move = " + str(round(avg, 2)) + "%")

    print("\nNOTE: Sample size is still small. This is directional, ongoing")
    print("evidence-gathering, not a validated conclusion. Keep logging over")
    print("real days/weeks before drawing any real confidence from this.")


if __name__ == "__main__":
    analyze_forward_test_log()
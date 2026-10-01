from dotenv import load_dotenv
load_dotenv()

"""
Per-ticker loss-streak circuit breaker.

If a specific ticker has had 3 consecutive real losses, new signals on that
ticker are automatically blocked until manually cleared -- this stops
repeating a possibly-bad pattern without automatically rewriting any rules.
The decision about WHY it happened and what (if anything) to change stays
with you, reviewed manually, same as the rest of tonight's review process.
"""

import sqlite3
from pathlib import Path

CLEARED_TICKERS_FILE = Path(".circuit_breaker_cleared")


def check_ticker_circuit_breaker(ticker: str, loss_streak_threshold: int = 3) -> dict:
    with sqlite3.connect("options_trades.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT pnl_dollars FROM options_trades "
            "WHERE ticker = ? AND exit_date IS NOT NULL "
            "ORDER BY exit_date DESC LIMIT ?",
            (ticker, loss_streak_threshold),
        ).fetchall()

    if len(rows) < loss_streak_threshold:
        return {"blocked": False, "reason": None}

    all_losses = all(row["pnl_dollars"] is not None and row["pnl_dollars"] < 0 for row in rows)

    if not all_losses:
        return {"blocked": False, "reason": None}

    if CLEARED_TICKERS_FILE.exists():
        cleared = CLEARED_TICKERS_FILE.read_text().splitlines()
        if ticker in cleared:
            return {"blocked": False, "reason": None}

    return {
        "blocked": True,
        "reason": ticker + " has " + str(loss_streak_threshold) + " consecutive losses -- paused pending manual review",
    }


def clear_ticker(ticker: str) -> None:
    existing = []
    if CLEARED_TICKERS_FILE.exists():
        existing = CLEARED_TICKERS_FILE.read_text().splitlines()
    if ticker not in existing:
        existing.append(ticker)
    CLEARED_TICKERS_FILE.write_text("\n".join(existing))
    print(ticker + " circuit breaker cleared.")


if __name__ == "__main__":
    for t in ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]:
        result = check_ticker_circuit_breaker(t)
        status = "BLOCKED: " + str(result["reason"]) if result["blocked"] else "OK"
        print(t + ": " + status)
from dotenv import load_dotenv
load_dotenv()

"""
Cross-trade pattern review.

Looks across multiple recent trades together (not just one at a time) to
identify recurring patterns in wins/losses -- same strict read-only,
advisory-only design as trade_reviewer.py. Zero ability to modify code
or strategy.
"""

import os
import sqlite3
import anthropic
from datetime import datetime, timezone, timedelta

api_key = os.environ.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=api_key)

PATTERN_REVIEW_DB_PATH = "pattern_reviews.db"


def init_pattern_db() -> None:
    with sqlite3.connect(PATTERN_REVIEW_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pattern_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period_days INTEGER NOT NULL,
                generated_at TEXT NOT NULL,
                trades_included INTEGER NOT NULL,
                review_text TEXT NOT NULL
            )
        """)


def get_recent_closed_trades(days: int) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    with sqlite3.connect("options_trades.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM options_trades WHERE exit_date IS NOT NULL AND exit_date >= ? ORDER BY exit_date ASC",
            (cutoff,),
        ).fetchall()
    return [dict(row) for row in rows]


def generate_pattern_review(days: int = 7) -> str:
    """Generate a cross-trade pattern review for the given lookback period."""
    trades = get_recent_closed_trades(days)

    if not trades:
        return "No closed trades in the last " + str(days) + " days to analyze."

    trade_summary = ""
    for t in trades:
        trade_summary += (
            "- " + t["ticker"] + " " + t["option_type"] + " entered " + t["entry_date"] +
            ", exit_reason=" + str(t["exit_reason"]) + ", pnl_pct=" + str(round(t["pnl_pct"], 1)) + "%\n"
        )

    prompt = (
        "Review this set of " + str(len(trades)) + " completed options trades from the last " +
        str(days) + " days. Look for patterns: which types of setups tend to win vs lose, "
        "whether losses cluster around certain conditions (specific tickers, DTE, exit reasons), "
        "and any recurring concerns. Do NOT suggest specific code changes -- just honest, "
        "concise pattern analysis (4-6 sentences) for a human to consider.\n\n" + trade_summary
    )

    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )

    review_text = message.content[0].text

    init_pattern_db()
    with sqlite3.connect(PATTERN_REVIEW_DB_PATH) as conn:
        conn.execute(
            "INSERT INTO pattern_reviews (period_days, generated_at, trades_included, review_text) VALUES (?, ?, ?, ?)",
            (days, datetime.now(timezone.utc).isoformat(), len(trades), review_text),
        )

    return review_text


if __name__ == "__main__":
    print("Generating 7-day pattern review...\n")
    review = generate_pattern_review(days=7)
    print(review)
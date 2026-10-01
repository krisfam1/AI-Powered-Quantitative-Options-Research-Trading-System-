from dotenv import load_dotenv
load_dotenv()

"""
AI-powered trade review generator.

Sends completed trade data to Claude via the Anthropic API for an honest,
plain-language review: why the trade won or lost, whether the process was
followed correctly, and any patterns worth noting.

CRITICAL DESIGN CONSTRAINT: this module has ZERO ability to modify any
strategy code, configuration, or trading logic. It only ever reads trade
data and writes review text to a database. Reviews are advisory only --
any suggested changes must be manually evaluated and implemented by a
human, never applied automatically.
"""

import os
import sqlite3
import anthropic
from datetime import datetime, timezone

api_key = os.environ.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=api_key)

REVIEW_DB_PATH = "trade_reviews.db"


def init_review_db() -> None:
    with sqlite3.connect(REVIEW_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trade_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT NOT NULL,
                reviewed_at TEXT NOT NULL,
                review_text TEXT NOT NULL
            )
        """)


def generate_trade_review(trade_data: dict) -> str:
    """
    Send a completed trade's data to Claude for an honest review.
    Returns the review text. Does NOT modify any code or strategy.
    """
    prompt = (
        "Review this completed options trade honestly and directly. "
        "Explain likely reasons for the outcome (win or loss), whether the "
        "entry/exit process appears to have been followed correctly based "
        "on the data given, and note any concerns or patterns worth "
        "flagging for future review. "
        "If gamma_context data is present, explicitly address: was the gamma "
        "regime/wall signal at entry strong or weak, and would following a "
        "strict gamma-based entry rule (only enter when regime is negative "
        "AND very close to a wall) have taken this trade or skipped it -- "
        "and if skipped, would that have been better or worse for this "
        "specific outcome? Do the same for estimated_volatility if present: "
        "was it elevated or low relative to what a genuinely volatile setup "
        "would suggest? "
        "Also, if price_extremes (real peak/trough) data is present, answer "
        "these broader what-if questions using that real data: (a) if the "
        "stop-loss had been 10 percentage points wider, would the outcome "
        "have changed? (b) if the position had peaked 40%+ before reversing, "
        "would a reversal-guard-style early exit (locking in gains once up "
        "40%+ and price sustains against the position) have improved the "
        "outcome? Answer these using the actual peak/trough numbers given, "
        "not speculation. "
        "Do NOT suggest specific code changes -- just provide analysis and, "
        "if relevant, general ideas worth a human considering later. "
        "End your response with exactly one line in this exact format: "
        "RECOMMENDATION: [KEEP or RECONSIDER] - <specific factor, e.g. stop-loss "
        "width, entry timing, DTE choice> - <one concise reason tied to this "
        "trade's specific data>. "
        "Keep the overall response concise but complete, 6-10 sentences plus "
        "the final recommendation line.\n\n"
        "Trade data:\n" + str(trade_data)
    )

    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=2000,
        thinking={"type": "disabled"},
        messages=[{"role": "user", "content": prompt}],
    )

    review_text = None
    for block in message.content:
        if hasattr(block, "text"):
            review_text = block.text
            break
    if review_text is None:
        review_text = str(message.content)
    return review_text


def review_and_store_trade(trade_id: str, trade_data: dict) -> str:
    """Generate a review and store it, keyed to the trade_id."""
    init_review_db()
    review_text = generate_trade_review(trade_data)

    with sqlite3.connect(REVIEW_DB_PATH) as conn:
        conn.execute(
            "INSERT INTO trade_reviews (trade_id, reviewed_at, review_text) VALUES (?, ?, ?)",
            (trade_id, datetime.now(timezone.utc).isoformat(), review_text),
        )

    return review_text


if __name__ == "__main__":
    test_trade = {
        "ticker": "AAPL",
        "option_type": "put",
        "entry_premium": 2.07,
        "exit_premium": 0.98,
        "pnl_pct": -52.66,
        "exit_reason": "stop_loss",
        "entry_reasoning": "regime=bearish relative_volume=1.8 price=$309.90 strike=$305 dte=6",
    }
    print("Generating test review...\n")
    review = generate_trade_review(test_trade)
    print(review)
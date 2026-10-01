from dotenv import load_dotenv
load_dotenv()

"""
Lessons-learned aggregator.

Pulls every per-trade AI review's RECOMMENDATION line and synthesizes them
across all trades, looking for genuine, repeated patterns -- what factors
keep showing up as KEEP vs RECONSIDER, backed by the specific trades that
drove each recommendation. Strictly advisory -- surfaces patterns for
human review, never modifies code or strategy.
"""

import os
import re
import sqlite3
import anthropic
from datetime import datetime, timezone
from main_bot_statistical_analysis import _get_main_bot_trades, compute_main_bot_statistics

api_key = os.environ.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=api_key)

LESSONS_DB = "lessons_learned.db"


def _init_lessons_db() -> None:
    with sqlite3.connect(LESSONS_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lessons_learned (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generated_at TEXT NOT NULL,
                trades_analyzed INTEGER NOT NULL,
                synthesis TEXT NOT NULL
            )
        """)


def _extract_recommendations() -> list[dict]:
    with sqlite3.connect("trade_reviews.db") as conn:
        rows = conn.execute("SELECT trade_id, review_text FROM trade_reviews").fetchall()

    recommendations = []
    pattern = re.compile(r"RECOMMENDATION:\s*(KEEP|RECONSIDER)\s*-\s*([^-]+?)\s*-\s*(.+)$", re.MULTILINE)

    for trade_id, review_text in rows:
        match = pattern.search(review_text)
        if match:
            recommendations.append({
                "trade_id": trade_id,
                "verdict": match.group(1),
                "factor": match.group(2).strip(),
                "reason": match.group(3).strip(),
            })

    return recommendations


def generate_lessons_learned() -> str:
    """Synthesize patterns across all trade recommendations collected so far."""
    recommendations = _extract_recommendations()

    if not recommendations:
        return "No trade recommendations found yet -- reviews need to accumulate first."

    summary_lines = []
    for r in recommendations:
        summary_lines.append("- " + r["trade_id"] + ": " + r["verdict"] + " (" + r["factor"] + ") -- " + r["reason"])
    summary_text = "\n".join(summary_lines)

    real_trades = _get_main_bot_trades()
    real_stats = compute_main_bot_statistics(real_trades)
    stats_text = "\n".join(
        "  " + factor + ": n=" + str(s["count"]) + ", win_rate=" + str(s["win_rate"]) + "%, avg_pnl=" + str(s["avg_pnl_pct"]) + "%"
        for factor, s in real_stats.items()
    )

    prompt = (
        "Here are the individual RECOMMENDATION lines from " + str(len(recommendations)) +
        " completed trade reviews, PLUS real, computed statistics (actual win rates and "
        "average P&L per factor, not AI-eyeballed) across " + str(len(real_trades)) +
        " total closed trades:\n\n" + stats_text + "\n\n"
        "Ground your synthesis in these REAL COMPUTED STATISTICS above, not just the "
        "qualitative recommendation text. Identify which specific factors show a "
        "genuinely higher or lower win rate/avg P&L with a real, meaningful sample "
        "size (n >= 8-10), and cross-reference this against which factors show up "
        "as RECONSIDER or KEEP in the recommendation lines below. Explicitly flag "
        "any factor where the real statistics and the qualitative recommendations "
        "disagree. Explicitly call out if a factor's sample size is too small to "
        "trust yet. Do NOT suggest specific code changes -- just synthesize what "
        "the real data shows, clearly, for a human to consider. Keep it concise, "
        "6-8 sentences.\n\nRECOMMENDATION LINES:\n" + summary_text
    )

    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1000,
        thinking={"type": "disabled"},
        messages=[{"role": "user", "content": prompt}],
    )

    synthesis = None
    for block in message.content:
        if hasattr(block, "text"):
            synthesis = block.text
            break
    if synthesis is None:
        synthesis = "Could not extract text response."

    _init_lessons_db()
    with sqlite3.connect(LESSONS_DB) as conn:
        conn.execute(
            "INSERT INTO lessons_learned (generated_at, trades_analyzed, synthesis) VALUES (?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), len(recommendations), synthesis),
        )

    return synthesis


if __name__ == "__main__":
    print("Generating lessons-learned synthesis across all trade recommendations...\n")
    result = generate_lessons_learned()
    print(result)
from dotenv import load_dotenv
load_dotenv()

"""
SPY gamma bot -- dedicated pattern-learning system.

Scoped ONLY to spy-gamma- trades, completely separate from the main
bot's lessons_learned.py. Explicitly separates winning trades from
losing trades, analyzes what gamma_context factors (regime, confluence
bonuses, tranche type) correlate with each, and re-synthesizes the FULL
accumulated history every time it runs -- so confidence genuinely grows
as more real trades close, not just verbosity.

Strictly advisory. Never modifies code or strategy automatically.
"""

import json
import sqlite3
import anthropic
import os
from datetime import datetime, timezone
from spy_gamma_statistical_analysis import compute_factor_statistics
from spy_gamma_statistical_analysis import compute_factor_statistics

api_key = os.environ.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=api_key)

DB_PATH = "spy_gamma_lessons.db"


def _init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS spy_gamma_lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generated_at TEXT NOT NULL,
                total_trades INTEGER NOT NULL,
                wins INTEGER NOT NULL,
                losses INTEGER NOT NULL,
                synthesis TEXT NOT NULL
            )
        """)


def _get_spy_gamma_trades() -> list[dict]:
    with sqlite3.connect("options_trades.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM options_trades WHERE trade_id LIKE 'spy-gamma-%' AND exit_date IS NOT NULL"
        ).fetchall()

    trades = []
    for r in rows:
        gamma_context = {}
        if r["gamma_context"]:
            try:
                gamma_context = json.loads(r["gamma_context"])
            except Exception:
                pass
        trades.append({
            "trade_id": r["trade_id"],
            "pnl_pct": r["pnl_pct"],
            "pnl_dollars": r["pnl_dollars"],
            "exit_reason": r["exit_reason"],
            "gamma_context": gamma_context,
        })
    return trades


def generate_spy_gamma_lessons() -> str:
    """Re-analyzes the FULL accumulated SPY gamma trade history, separating wins from losses."""
    trades = _get_spy_gamma_trades()

    if not trades:
        return "No closed SPY gamma trades yet -- nothing to learn from so far."

    wins = [t for t in trades if t["pnl_dollars"] > 0]
    losses = [t for t in trades if t["pnl_dollars"] <= 0]

    win_lines = "\n".join(
        "- " + w["trade_id"] + ": +" + str(round(w["pnl_pct"], 1)) + "% (" + w["exit_reason"] + ") | context: " + str(w["gamma_context"])
        for w in wins
    ) if wins else "(none yet)"

    loss_lines = "\n".join(
        "- " + l["trade_id"] + ": " + str(round(l["pnl_pct"], 1)) + "% (" + l["exit_reason"] + ") | context: " + str(l["gamma_context"])
        for l in losses
    ) if losses else "(none yet)"

    real_stats = compute_factor_statistics(trades)
    stats_text = "\n".join(
        "  " + factor + ": n=" + str(s["count"]) + ", win_rate=" + str(s["win_rate"]) + "%, avg_pnl=" + str(s["avg_pnl_pct"]) + "%"
        for factor, s in real_stats.items()
    )

    prompt = (
        "You are analyzing the FULL accumulated history of a real, live-tracked "
        "gamma/charm-based SPY options day-trading strategy: " + str(len(trades)) +
        " closed trades total (" + str(len(wins)) + " wins, " + str(len(losses)) + " losses). "
        "Each trade includes its gamma_context (regime, wall price, which confluence "
        "bonuses were present -- charm pin, daily S/R level -- and which scale-out "
        "tranche it was). \n\n"
        "REAL, COMPUTED STATISTICS (not AI-eyeballed -- these are actual calculated "
        "win rates and average P&L, broken down by factor):\n" + stats_text + "\n\n"
        "WINNING TRADES:\n" + win_lines + "\n\n"
        "LOSING TRADES:\n" + loss_lines + "\n\n"
        "Ground your analysis in the REAL COMPUTED STATISTICS above, not just your "
        "own read of the trade list. Explicitly separate your analysis into two "
        "parts: (1) what specific factors show a genuinely higher win rate/avg P&L "
        "in the real statistics -- what should this strategy keep doing; (2) what "
        "factors show a genuinely lower win rate/avg P&L -- what should be avoided "
        "or treated with more caution. If any factor's sample size (n) is too small "
        "to trust (under ~8-10), say so explicitly rather than overstating it. Do "
        "NOT suggest specific code changes -- just synthesize what the real, "
        "computed data shows. Keep it concise, 6-8 sentences."
    )

    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1200,
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

    _init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO spy_gamma_lessons (generated_at, total_trades, wins, losses, synthesis) VALUES (?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), len(trades), len(wins), len(losses), synthesis),
        )

    return synthesis


if __name__ == "__main__":
    print("Analyzing full SPY gamma trade history (wins vs. losses)...\n")
    result = generate_spy_gamma_lessons()
    print(result)
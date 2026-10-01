from dotenv import load_dotenv
load_dotenv()

"""
Comprehensive account-level AI review.

Analyzes the whole options account across weekly and monthly windows,
broken down by calls vs puts, hold duration, and exit-reason distribution.
Same strict read-only, advisory-only design as the rest of the review system.

HONEST LIMITATION: gamma modifier correlation is NOT included in this
version -- that data is stored as unstructured text tied to signal logs,
not cleanly linked to trade records, making reliable correlation harder
than initially planned. Worth building properly later if valuable.
"""

import os
import sqlite3
import anthropic
from datetime import datetime, timezone, timedelta

api_key = os.environ.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=api_key)

ACCOUNT_REVIEW_DB_PATH = "account_reviews.db"


def init_account_review_db() -> None:
    with sqlite3.connect(ACCOUNT_REVIEW_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS account_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generated_at TEXT NOT NULL,
                review_text TEXT NOT NULL
            )
        """)


def _get_trades_since(days: int) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    with sqlite3.connect("options_trades.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM options_trades WHERE exit_date IS NOT NULL AND exit_date >= ? ORDER BY exit_date ASC",
            (cutoff,),
        ).fetchall()
    return [dict(row) for row in rows]


def _summarize_period(days: int, label: str) -> str:
    trades = _get_trades_since(days)
    if not trades:
        return label + ": no closed trades in this period.\n"

    calls = [t for t in trades if t["option_type"] == "call"]
    puts = [t for t in trades if t["option_type"] == "put"]

    same_day = [t for t in trades if t["entry_date"] == t["exit_date"]]
    multi_day = [t for t in trades if t["entry_date"] != t["exit_date"]]

    exit_reasons = {}
    for t in trades:
        r = t["exit_reason"] or "unknown"
        exit_reasons[r] = exit_reasons.get(r, 0) + 1

    def avg_pnl(subset):
        if not subset:
            return "n/a"
        return str(round(sum(t["pnl_pct"] for t in subset) / len(subset), 1)) + "%"

    def win_rate(subset):
        if not subset:
            return "n/a"
        wins = len([t for t in subset if t["pnl_dollars"] and t["pnl_dollars"] > 0])
        return str(round(wins / len(subset) * 100, 1)) + "%"

    total_pnl = sum(t["pnl_dollars"] for t in trades if t["pnl_dollars"])

    summary = label + " (" + str(len(trades)) + " trades, total P&L $" + str(round(total_pnl, 2)) + "):\n"
    summary += "  Calls: " + str(len(calls)) + " trades, win_rate=" + win_rate(calls) + ", avg_pnl=" + avg_pnl(calls) + "\n"
    summary += "  Puts: " + str(len(puts)) + " trades, win_rate=" + win_rate(puts) + ", avg_pnl=" + avg_pnl(puts) + "\n"
    summary += "  Same-day exits: " + str(len(same_day)) + " trades, win_rate=" + win_rate(same_day) + ", avg_pnl=" + avg_pnl(same_day) + "\n"
    summary += "  Multi-day (swing) exits: " + str(len(multi_day)) + " trades, win_rate=" + win_rate(multi_day) + ", avg_pnl=" + avg_pnl(multi_day) + "\n"
    summary += "  Exit reason breakdown: " + str(exit_reasons) + "\n"

    with_gamma = [t for t in trades if t.get("gamma_modifier") is not None]
    if with_gamma:
        sized_up = [t for t in with_gamma if t["gamma_modifier"] > 1.0]
        sized_down = [t for t in with_gamma if t["gamma_modifier"] < 1.0]
        neutral = [t for t in with_gamma if t["gamma_modifier"] == 1.0]
        summary += "  Gamma modifier -- sized up: " + str(len(sized_up)) + " trades, win_rate=" + win_rate(sized_up) + ", avg_pnl=" + avg_pnl(sized_up) + "\n"
        summary += "  Gamma modifier -- sized down: " + str(len(sized_down)) + " trades, win_rate=" + win_rate(sized_down) + ", avg_pnl=" + avg_pnl(sized_down) + "\n"
        summary += "  Gamma modifier -- neutral: " + str(len(neutral)) + " trades, win_rate=" + win_rate(neutral) + ", avg_pnl=" + avg_pnl(neutral) + "\n"
    else:
        summary += "  Gamma modifier data: not available for trades in this period (older trades predate this tracking)\n"

    return summary


def generate_account_review() -> str:
    """Generate a comprehensive, multi-window account review."""
    weekly_summary = _summarize_period(7, "PAST 7 DAYS")
    monthly_summary = _summarize_period(30, "PAST 30 DAYS")

    prompt = (
        "Review this options trading account's performance across two time windows. "
        "Analyze: (1) calls vs puts performance differences, (2) same-day vs multi-day "
        "swing hold performance, (3) exit reason distribution and what it implies about "
        "threshold calibration, (4) any notable difference between the weekly and monthly "
        "windows suggesting a trend, and (5) whether the gamma modifier (sized up/down/neutral) correlates with better or worse outcomes. Do NOT suggest specific code changes -- just honest, "
        "clear analysis (6-8 sentences) for a human to consider, and flag if sample sizes "
        "are too small to draw real conclusions.\n\n" + weekly_summary + "\n" + monthly_summary
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

    init_account_review_db()
    with sqlite3.connect(ACCOUNT_REVIEW_DB_PATH) as conn:
        conn.execute(
            "INSERT INTO account_reviews (generated_at, review_text) VALUES (?, ?)",
            (datetime.now(timezone.utc).isoformat(), review_text),
        )

    return review_text


if __name__ == "__main__":
    print("Generating comprehensive account review...\n")
    review = generate_account_review()
    print(review)


def should_run_weekly_account_review() -> bool:
    """Check whether 7+ days have passed since the last account review."""
    import sqlite3
    from datetime import datetime, timezone, timedelta

    with sqlite3.connect("account_reviews.db") as conn:
        row = conn.execute("SELECT generated_at FROM account_reviews ORDER BY generated_at DESC LIMIT 1").fetchone()

    if row is None:
        return True

    last_run = datetime.fromisoformat(row[0])
    return (datetime.now(timezone.utc) - last_run) >= timedelta(days=7)

from dotenv import load_dotenv
load_dotenv()

"""
Generates the real ML training dataset by running the already-validated
backtest configuration (weighted entry, 0.30 delta, reversal_guard,
spread cost) across all 6 tickers, with collect_features=True, and
saving every resulting trade's real feature vector + real outcome to a
dedicated SQLite database.

This is Step 2 of the ML roadmap: real, labeled training data.
"""

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from options_backtest_engine import run_options_backtest

DB_PATH = "ml_training_data.db"
tickers = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]

end = datetime.now(timezone.utc)
start = end - timedelta(days=90)  # use the full 90 days, train + holdout combined, for max training volume


def _init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS training_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                entry_date TEXT,
                exit_date TEXT,
                exit_reason TEXT,
                pnl_pct REAL,
                pnl_dollars REAL,
                won INTEGER,
                features_json TEXT,
                generated_at TEXT
            )
        """)


def generate_dataset() -> dict:
    _init_db()
    total_saved = 0
    total_skipped_no_features = 0

    with sqlite3.connect(DB_PATH) as conn:
        for ticker in tickers:
            result = run_options_backtest(
                ticker, start, end, dte_target=14,
                exit_mode="reversal_guard", entry_mode="weighted",
                entry_score_threshold=20, target_delta=0.30,
                apply_spread_cost=True, collect_features=True,
            )

            for trade in result.get("trades", []):
                features = trade.get("entry_features")
                if not features:
                    total_skipped_no_features += 1
                    continue

                conn.execute(
                    "INSERT INTO training_examples (ticker, entry_date, exit_date, exit_reason, pnl_pct, pnl_dollars, won, features_json, generated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        ticker,
                        str(trade["entry_date"]),
                        str(trade["exit_date"]),
                        trade["exit_reason"],
                        trade["pnl_pct"],
                        trade["pnl_dollars"],
                        1 if trade["pnl_dollars"] > 0 else 0,
                        json.dumps(features),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                total_saved += 1
        conn.commit()

    return {"total_saved": total_saved, "total_skipped_no_features": total_skipped_no_features}


if __name__ == "__main__":
    print("Generating real ML training dataset across all 6 tickers (90 days)...\n")
    result = generate_dataset()
    print("\nTotal training examples saved: " + str(result["total_saved"]))
    print("Skipped (no features captured): " + str(result["total_skipped_no_features"]))
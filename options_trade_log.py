from dotenv import load_dotenv
load_dotenv()

import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).with_name("options_trades.db")


def init_db() -> None:
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS options_trades (
                trade_id TEXT PRIMARY KEY,
                ticker TEXT,
                contract_symbol TEXT,
                option_type TEXT,
                entry_date TEXT,
                entry_premium REAL,
                contracts INTEGER,
                stop_loss_pct REAL,
                take_profit_pct REAL,
                expiry_date TEXT,
                exit_date TEXT,
                exit_timestamp TEXT,
                exit_premium REAL,
                pnl_dollars REAL,
                pnl_pct REAL,
                exit_reason TEXT,
                gamma_modifier REAL,
                gamma_context TEXT
            )
        """)


def log_entry(trade_data: dict) -> None:
    init_db()
    columns = list(trade_data.keys())
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)
    values = tuple(trade_data[c] for c in columns)
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO options_trades (" + column_sql + ") VALUES (" + placeholders + ")",
            values,
        )


def log_exit(trade_id: str, exit_data: dict) -> None:
    columns = list(exit_data.keys())
    assignments = ", ".join(c + " = ?" for c in columns)
    values = tuple(exit_data[c] for c in columns) + (trade_id,)
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            "UPDATE options_trades SET " + assignments + " WHERE trade_id = ?",
            values,
        )


def get_open_positions() -> list[dict]:
    init_db()
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM options_trades WHERE exit_date IS NULL"
        ).fetchall()
        return [dict(row) for row in rows]
"""SQLite-backed trade entry and exit logging."""

import sqlite3
from pathlib import Path
from typing import Any, Mapping


DATABASE_PATH = Path(__file__).with_name("trades.db")

TRADE_COLUMNS = (
    "trade_id",
    "timestamp_entry",
    "ticker",
    "signal_type",
    "direction",
    "volume_at_entry",
    "relative_volume",
    "price_action_pattern",
    "news_present",
    "news_sentiment_score",
    "news_headline_summary",
    "entry_price",
    "position_size",
    "stop_loss_price",
    "target_price",
    "risk_amount",
    "timestamp_exit",
    "exit_price",
    "exit_reason",
    "pnl_dollars",
    "pnl_percent",
    "outcome_class",
    "root_cause",
    "was_process_correct",
    "rule_change_made",
    "rule_change_description",
)

EXIT_COLUMNS = (
    "timestamp_exit",
    "exit_price",
    "exit_reason",
    "pnl_dollars",
    "pnl_percent",
    "outcome_class",
    "root_cause",
    "was_process_correct",
    "rule_change_made",
    "rule_change_description",
)


def init_db() -> None:
    """Create the trades table if it does not already exist."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                timestamp_entry TEXT,
                ticker TEXT,
                signal_type TEXT,
                direction TEXT,
                volume_at_entry REAL,
                relative_volume REAL,
                price_action_pattern TEXT,
                news_present INTEGER,
                news_sentiment_score REAL,
                news_headline_summary TEXT,
                entry_price REAL,
                position_size REAL,
                stop_loss_price REAL,
                target_price REAL,
                risk_amount REAL,
                timestamp_exit TEXT,
                exit_price REAL,
                exit_reason TEXT,
                pnl_dollars REAL,
                pnl_percent REAL,
                outcome_class TEXT,
                root_cause TEXT,
                was_process_correct INTEGER,
                rule_change_made INTEGER,
                rule_change_description TEXT
            )
            """
        )


def clear_trades() -> None:
    """Delete all stored trade records."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("DELETE FROM trades")


def log_trade_entry(trade_data: Mapping[str, Any]) -> None:
    """Insert a trade entry record, ignoring an already-logged trade ID."""
    columns = tuple(column for column in TRADE_COLUMNS if column in trade_data)
    if "trade_id" not in columns:
        raise ValueError("trade_data must include trade_id")

    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)
    values = tuple(trade_data[column] for column in columns)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            f"INSERT OR IGNORE INTO trades ({column_sql}) VALUES ({placeholders})",
            values,
        )


def log_trade_exit(trade_id: str, exit_data: Mapping[str, Any]) -> None:
    """Update an existing trade with exit details."""
    updates = tuple(column for column in EXIT_COLUMNS if column in exit_data)
    if not updates:
        raise ValueError("exit_data must include at least one exit field")

    assignments = ", ".join(f"{column} = ?" for column in updates)
    values = tuple(exit_data[column] for column in updates) + (trade_id,)

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.execute(
            f"UPDATE trades SET {assignments} WHERE trade_id = ?",
            values,
        )
        if cursor.rowcount == 0:
            raise ValueError(f"No trade found with trade_id={trade_id!r}")

"""Search ledger for the SPX volatility-state engine (started 2026-10-17, user-approved).

Append-only record of EVERY combination ever evaluated against a target or relationship
(feature set, transform, window, regime method, detector, target, horizon, metric, block).
The DSR, PBO and Reality Check use its row count as the real search breadth, and so does the
pre-registration's disclosure. Stage 0 evaluated nothing, so the ledger starts empty.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = Path(__file__).resolve().parent / "store" / "spx_vol.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS search_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_utc TEXT NOT NULL,
    stage TEXT NOT NULL,
    data_block TEXT NOT NULL CHECK (data_block IN ('dev_2004_2016', 'val_2017_2020', 'locked_2021_on', 'prospective')),
    feature_set TEXT, transform TEXT, window TEXT, regime_method TEXT, detector TEXT,
    target TEXT, horizon TEXT, metric TEXT, value REAL, notes TEXT, params_json TEXT
);
CREATE TRIGGER IF NOT EXISTS search_ledger_no_update BEFORE UPDATE ON search_ledger
BEGIN SELECT RAISE(ABORT, 'search_ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS search_ledger_no_delete BEFORE DELETE ON search_ledger
BEGIN SELECT RAISE(ABORT, 'search_ledger is append-only'); END;
"""


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    return con


def log(stage, data_block, value=None, params=None, **fields):
    """Append one evaluated combination. Locked-block rows are allowed only at confirmation."""
    con = connect()
    cols = ["logged_utc", "stage", "data_block", "value", "params_json"] + list(fields)
    vals = [datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), stage, data_block, value,
            json.dumps(params, sort_keys=True) if params else None] + list(fields.values())
    con.execute(f"INSERT INTO search_ledger ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)
    con.commit()
    con.close()


def count():
    con = connect()
    n = con.execute("SELECT COUNT(*) FROM search_ledger").fetchone()[0]
    con.close()
    return n


if __name__ == "__main__":
    print("search_ledger rows:", count(), "at", DB)

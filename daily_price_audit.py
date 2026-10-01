from dotenv import load_dotenv
load_dotenv()

"""
Automatic daily price-accuracy audit.

Compares our recorded entry/exit prices (both closed trades and currently
open positions) against Alpaca's real, settled order data. Auto-corrects
any mismatch, since this is purely syncing our records to Alpaca's own
ground truth -- not a strategy decision, just data accuracy.

Runs once per day (checked via a persistent log), not on every cycle,
to keep this separate from the live exit-decision code path.
"""

import os
import sqlite3
from datetime import datetime, timezone, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

api_key = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")
_client = TradingClient(api_key, secret_key, paper=True)

AUDIT_LOG_DB = "price_audit_log.db"


def _init_audit_log() -> None:
    with sqlite3.connect(AUDIT_LOG_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at TEXT NOT NULL,
                trades_checked INTEGER NOT NULL,
                mismatches_found INTEGER NOT NULL,
                details TEXT
            )
        """)


def should_run_daily_audit() -> bool:
    _init_audit_log()
    with sqlite3.connect(AUDIT_LOG_DB) as conn:
        row = conn.execute("SELECT run_at FROM audit_runs ORDER BY run_at DESC LIMIT 1").fetchone()
    if row is None:
        return True
    last_run = datetime.fromisoformat(row[0])
    return (datetime.now(timezone.utc) - last_run) >= timedelta(hours=24)


def run_daily_uptime_check() -> dict:
    """Check for real downtime gaps affecting any open or recently-closed position."""
    from automated_uptime_monitor import check_gaps_during_open_positions
    return check_gaps_during_open_positions()


def run_daily_price_audit() -> dict:
    """Audit all closed trades AND currently open positions against real Alpaca data."""
    _init_audit_log()
    mismatches = []
    trades_checked = 0

    with sqlite3.connect("options_trades.db") as conn:
        conn.row_factory = sqlite3.Row
        all_trades = conn.execute("SELECT * FROM options_trades").fetchall()

    for t in all_trades:
        trades_checked += 1
        symbol = t["contract_symbol"]

        req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=20, symbols=[symbol])
        try:
            orders = _client.get_orders(req)
        except Exception:
            continue

        # PRECISE FIX: the trade_id itself contains the exact Alpaca order
        # ID for the entry (format: "opt-live-{ticker}-{order_id}"), so we
        # fetch that EXACT order -- no ambiguity even when the same symbol
        # was traded multiple times on the same day.
        real_entry = None
        try:
            _id_parts = t["trade_id"].split("-", 3)
            _order_id = _id_parts[3] if len(_id_parts) > 3 else None
            if _order_id:
                _entry_order = _client.get_order_by_id(_order_id)
                if _entry_order.filled_avg_price:
                    real_entry = float(_entry_order.filled_avg_price)
        except Exception:
            real_entry = None

        if real_entry is not None and abs(real_entry - t["entry_premium"]) > 0.01:
            with sqlite3.connect("options_trades.db") as conn2:
                conn2.execute(
                    "UPDATE options_trades SET entry_premium = ? WHERE trade_id = ?",
                    (real_entry, t["trade_id"]),
                )
                conn2.commit()
            mismatches.append(t["trade_id"] + ": entry corrected $" + str(t["entry_premium"]) + " -> $" + str(real_entry))

        if t["exit_date"] is not None and t["exit_timestamp"]:
            from datetime import datetime as _dt
            _exit_ts = _dt.fromisoformat(t["exit_timestamp"])
            _sell_candidates = [o for o in orders if str(o.side) == "OrderSide.SELL" and o.filled_avg_price]
            # Match the SELL order closest in time to this trade's actual
            # recorded exit_timestamp -- precise even with multiple sells
            # for the same symbol.
            real_sells = sorted(_sell_candidates, key=lambda o: abs((o.submitted_at - _exit_ts).total_seconds()))
            if real_sells:
                real_exit = float(real_sells[0].filled_avg_price)
                if abs(real_exit - t["exit_premium"]) > 0.01:
                    real_entry_for_pnl = real_entry if real_entry is not None else t["entry_premium"]
                    real_pnl_dollars = (real_exit - float(real_entry_for_pnl)) * t["contracts"] * 100
                    real_pnl_pct = (real_exit - float(real_entry_for_pnl)) / float(real_entry_for_pnl) * 100 if real_entry_for_pnl else 0
                    with sqlite3.connect("options_trades.db") as conn3:
                        conn3.execute(
                            "UPDATE options_trades SET exit_premium = ?, pnl_dollars = ?, pnl_pct = ? WHERE trade_id = ?",
                            (real_exit, real_pnl_dollars, real_pnl_pct, t["trade_id"]),
                        )
                        conn3.commit()
                    mismatches.append(t["trade_id"] + ": exit corrected $" + str(t["exit_premium"]) + " -> $" + str(real_exit))

    with sqlite3.connect(AUDIT_LOG_DB) as conn:
        conn.execute(
            "INSERT INTO audit_runs (run_at, trades_checked, mismatches_found, details) VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), trades_checked, len(mismatches), "; ".join(mismatches)),
        )
        conn.commit()

    uptime_result = run_daily_uptime_check()
    if uptime_result["flagged_overlaps"]:
        for f in uptime_result["flagged_overlaps"]:
            mismatches.append("UPTIME WARNING: " + f["trade_id"] + " had a " + str(f["gap_minutes"]) + " min monitoring gap")

    return {"trades_checked": trades_checked, "mismatches_found": len(mismatches), "details": mismatches, "uptime_gaps_found": uptime_result["total_real_gaps"]}


if __name__ == "__main__":
    result = run_daily_price_audit()
    print("Trades checked: " + str(result["trades_checked"]))
    print("Mismatches found and corrected: " + str(result["mismatches_found"]))
    for d in result["details"]:
        print("  " + d)
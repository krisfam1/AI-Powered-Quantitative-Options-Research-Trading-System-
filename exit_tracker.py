from dotenv import load_dotenv
load_dotenv()

import os
import sqlite3
from datetime import datetime, timezone
from alpaca.trading.client import TradingClient
import trade_log

api_key = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")
trading_client = TradingClient(api_key, secret_key, paper=True)


def check_and_log_exits() -> int:
    """Check all open trades for a completed exit, and log it if found. Returns count of exits logged."""
    with sqlite3.connect(trade_log.DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        open_trades = conn.execute(
            "SELECT trade_id, ticker, entry_price, position_size, direction FROM trades WHERE timestamp_exit IS NULL"
        ).fetchall()

    exits_logged = 0

    for trade in open_trades:
        trade_id = trade["trade_id"]
        # Extract the Alpaca order ID from our trade_id format: "live-{ticker}-{order_id}"
        parts = trade_id.split("-", 2)
        if len(parts) < 3 or parts[0] != "live":
            continue
        order_id = parts[2]

        try:
            order = trading_client.get_order_by_id(order_id)
        except Exception:
            continue

        # A bracket order's child legs (stop/target) show up as separate orders
        legs = getattr(order, "legs", None) or []
        filled_leg = None
        for leg in legs:
            if str(leg.status) == "OrderStatus.FILLED":
                filled_leg = leg
                break

        if filled_leg is None:
            continue  # still open, nothing to log yet

        exit_price = float(filled_leg.filled_avg_price)
        position_size = float(trade["position_size"])

        # Use the REAL entry fill price from Alpaca (the parent order we already
        # fetched above), not our pre-trade estimate, so P&L reflects what
        # actually happened (accounts for real slippage).
        if order.filled_avg_price:
            entry_price = float(order.filled_avg_price)
        else:
            entry_price = float(trade["entry_price"])

        direction = trade["direction"] or "long"
        if direction == "long":
            pnl_dollars = (exit_price - entry_price) * position_size
            pnl_percent = (exit_price - entry_price) / entry_price * 100
        else:
            pnl_dollars = (entry_price - exit_price) * position_size
            pnl_percent = (entry_price - exit_price) / entry_price * 100

        exit_reason = "take_profit" if str(filled_leg.type) == "OrderType.LIMIT" else "stop_loss"
        outcome_class = "win" if pnl_dollars > 0 else ("loss" if pnl_dollars < 0 else "scratch")

        trade_log.log_trade_exit(trade_id, {
            "timestamp_exit": datetime.now(timezone.utc).isoformat(),
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "pnl_dollars": pnl_dollars,
            "pnl_percent": pnl_percent,
            "outcome_class": outcome_class,
        })
        exits_logged += 1
        print(f"  Logged exit for {trade['ticker']}: {exit_reason}, P&L ${pnl_dollars:.2f}")

    return exits_logged


if __name__ == "__main__":
    count = check_and_log_exits()
    print(f"\nChecked open trades, logged {count} new exit(s).")
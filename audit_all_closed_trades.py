from dotenv import load_dotenv
load_dotenv()

import os
import sqlite3
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

api_key = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")
client = TradingClient(api_key, secret_key, paper=True)

with sqlite3.connect("options_trades.db") as conn:
    conn.row_factory = sqlite3.Row
    trades = conn.execute(
        "SELECT * FROM options_trades WHERE exit_date IS NOT NULL"
    ).fetchall()

print("Auditing " + str(len(trades)) + " closed trades against real Alpaca order data...\n")

for t in trades:
    symbol = t["contract_symbol"]
    print("=" * 70)
    print(t["trade_id"])
    print("Recorded: entry=$" + str(t["entry_premium"]) + " exit=$" + str(t["exit_premium"]) + " pnl_pct=" + str(round(t["pnl_pct"], 1)) + "%")

    req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=20, symbols=[symbol])
    orders = client.get_orders(req)

    real_buys = [o for o in orders if str(o.side) == "OrderSide.BUY" and o.filled_avg_price]
    real_sells = [o for o in orders if str(o.side) == "OrderSide.SELL" and o.filled_avg_price]

    if not real_buys or not real_sells:
        print("  Could not find matching real BUY/SELL fills on Alpaca -- skipping.")
        continue

    real_entry = float(real_buys[0].filled_avg_price)
    real_exit = float(real_sells[0].filled_avg_price)

    print("Real Alpaca:  entry=$" + str(real_entry) + " exit=$" + str(real_exit))

    entry_matches = abs(real_entry - t["entry_premium"]) < 0.01
    exit_matches = abs(real_exit - t["exit_premium"]) < 0.01

    if entry_matches and exit_matches:
        print("  MATCH -- no correction needed.")
        continue

    contracts = t["contracts"]
    real_pnl_dollars = (real_exit - real_entry) * contracts * 100
    real_pnl_pct = (real_exit - real_entry) / real_entry * 100

    print("  *** MISMATCH FOUND ***")
    print("  Corrected P&L: $" + str(round(real_pnl_dollars, 2)) + " (" + str(round(real_pnl_pct, 1)) + "%)")
    print("  Previously recorded P&L: $" + str(round(t["pnl_dollars"], 2)) + " (" + str(round(t["pnl_pct"], 1)) + "%)")
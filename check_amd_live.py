from dotenv import load_dotenv
load_dotenv()

import os
import options_trade_log
from options_evaluator import get_live_bid_price
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

api_key = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")
client = TradingClient(api_key, secret_key, paper=True)

positions = options_trade_log.get_open_positions()
amd_positions = [p for p in positions if p["ticker"] == "AMD"]

if not amd_positions:
    print("No open AMD position found.")
else:
    pos = amd_positions[0]
    symbol = pos["contract_symbol"]

    print("Contract: " + symbol)
    print("Our recorded entry: $" + str(pos["entry_premium"]))

    req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=20, symbols=[symbol])
    orders = client.get_orders(req)
    buys = [o for o in orders if str(o.side) == "OrderSide.BUY" and o.filled_avg_price]
    if buys:
        print("Alpaca real fill price: $" + str(buys[0].filled_avg_price))
    else:
        print("Alpaca real fill price: not found")

    alpaca_positions = client.get_all_positions()
    match = [p for p in alpaca_positions if p.symbol == symbol]
    if match:
        print("Alpaca avg_entry_price: $" + str(match[0].avg_entry_price))
        print("Alpaca current market_value: $" + str(match[0].market_value))
        print("Alpaca unrealized_pl: $" + str(match[0].unrealized_pl))
        print("Alpaca qty: " + str(match[0].qty))
    else:
        print("No matching open position found on Alpaca.")

    bid = get_live_bid_price(symbol)
    print("Our current bid reading: $" + str(round(bid, 2)))

    pct_change = (bid - pos["entry_premium"]) / pos["entry_premium"] * 100
    print("Our calculated pct change: " + str(round(pct_change, 1)) + "%")

    print("Stop-loss threshold:  -" + str(pos["stop_loss_pct"]*100) + "%  (price: $" + str(round(pos["entry_premium"] * (1 - pos["stop_loss_pct"]), 2)) + ")")
    print("Take-profit threshold: +" + str(pos["take_profit_pct"]*100) + "%  (price: $" + str(round(pos["entry_premium"] * (1 + pos["take_profit_pct"]), 2)) + ")")
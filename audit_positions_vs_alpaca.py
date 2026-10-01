from dotenv import load_dotenv
load_dotenv()

import os
import options_trade_log
from options_evaluator import get_live_bid_price, get_live_premium
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

api_key = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")
client = TradingClient(api_key, secret_key, paper=True)

positions = options_trade_log.get_open_positions()

print("=" * 80)
print("FULL AUDIT: our system vs. Alpaca's real data")
print("=" * 80)

for pos in positions:
    symbol = pos["contract_symbol"]
    print("\n" + "-" * 80)
    print(symbol)
    print("-" * 80)

    our_entry = pos["entry_premium"]
    print("Our recorded entry premium:     $" + str(our_entry))

    req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=20, symbols=[symbol])
    orders = client.get_orders(req)
    filled_buys = [o for o in orders if str(o.side) == "OrderSide.BUY" and o.filled_avg_price]
    if filled_buys:
        real_entry = float(filled_buys[0].filled_avg_price)
        print("Alpaca's real fill price:       $" + str(real_entry))
        if abs(real_entry - our_entry) > 0.01:
            print("  *** MISMATCH -- entry price is WRONG ***")
        else:
            print("  MATCH -- entry price correct")
    else:
        print("Alpaca's real fill price:       could not find a filled BUY order")

    try:
        alpaca_positions = client.get_all_positions()
        matching = [p for p in alpaca_positions if p.symbol == symbol]
        if matching:
            print("Alpaca current qty:             " + str(matching[0].qty))
            print("Alpaca avg_entry_price:          $" + str(matching[0].avg_entry_price))
            print("Alpaca current market value:     $" + str(matching[0].market_value))
            print("Alpaca unrealized P&L:           $" + str(matching[0].unrealized_pl))
        else:
            print("No matching open position found on Alpaca (may have closed)")
    except Exception as exc:
        print("Could not fetch Alpaca position: " + str(exc))

    bid = get_live_bid_price(symbol)
    ask = get_live_premium(symbol)
    print("Our current bid (used for exits): $" + str(round(bid, 2)))
    print("Our current ask:                   $" + str(round(ask, 2)))

    correct_entry = real_entry if filled_buys else our_entry
    pct_change = (bid - correct_entry) / correct_entry * 100
    print("Recalculated pct change (using real entry, current bid): " + str(round(pct_change, 1)) + "%")

    print("Stop-loss threshold:  -" + str(pos["stop_loss_pct"] * 100) + "%  (price: $" + str(round(correct_entry * (1 - pos["stop_loss_pct"]), 2)) + ")")
    print("Take-profit threshold: +" + str(pos["take_profit_pct"] * 100) + "%  (price: $" + str(round(correct_entry * (1 + pos["take_profit_pct"]), 2)) + ")")

print("\n" + "=" * 80)
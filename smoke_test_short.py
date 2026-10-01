from dotenv import load_dotenv
load_dotenv()

import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

api_key = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")
trading_client = TradingClient(api_key, secret_key, paper=True)

print("=" * 68)
print("  SMOKE TEST — short-sell order pipeline")
print("=" * 68)

order_request = MarketOrderRequest(
    symbol="AAPL",
    qty=1,
    side=OrderSide.SELL,
    time_in_force=TimeInForce.DAY,
)

try:
    print("Submitting short-sell order for 1 share of AAPL...")
    order = trading_client.submit_order(order_request)
    print(f"  Order ID     : {order.id}")
    print(f"  Status       : {order.status}")
    print(f"  Side         : {order.side}")

    print("Cancelling order...")
    trading_client.cancel_order_by_id(order.id)
    final = trading_client.get_order_by_id(order.id)
    print(f"  Final status : {final.status}")
    print("PASS — short-sell order pipeline works.")
except Exception as exc:
    print(f"FAILED: {exc}")
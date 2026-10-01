from dotenv import load_dotenv
load_dotenv()

import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from options_data import get_options_chain, filter_near_the_money, pick_best_contract
from options_evaluator import get_live_premium
import backtest_engine as be
from datetime import datetime, timezone, timedelta

api_key = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")
trading_client = TradingClient(api_key, secret_key, paper=True)

print("=" * 68)
print("  SMOKE TEST -- PUTS options order pipeline")
print("=" * 68)

ticker = "TSLA"
now = datetime.now(timezone.utc)
bars = be.get_historical_bars(ticker, now - timedelta(days=5), now)
current_price = float(bars[-1].close)
print("Current " + ticker + " price: $" + str(round(current_price, 2)))

chain = get_options_chain(ticker, "put")
near_money = filter_near_the_money(chain, current_price)
best = pick_best_contract(near_money)

if best is None:
    print("FAILED: no suitable put contract found")
else:
    print("Selected contract: " + best.symbol)
    premium = get_live_premium(best.symbol)
    print("Live premium: $" + str(round(premium, 2)))

    order_request = MarketOrderRequest(
        symbol=best.symbol,
        qty=1,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
    )

    try:
        print("Submitting order for 1x " + best.symbol + "...")
        order = trading_client.submit_order(order_request)
        print("  Order ID     : " + str(order.id))
        print("  Status       : " + str(order.status))

        print("Attempting to cancel...")
        try:
            trading_client.cancel_order_by_id(order.id)
            final = trading_client.get_order_by_id(order.id)
            print("  Final status : " + str(final.status))
            print("PASS -- order canceled cleanly before fill.")
        except Exception:
            print("  Cancel failed (order likely already filled). Closing position instead...")
            close_request = MarketOrderRequest(
                symbol=best.symbol,
                qty=1,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
            close_order = trading_client.submit_order(close_request)
            print("  Close order ID: " + str(close_order.id))
            print("  Close status  : " + str(close_order.status))
            print("PASS -- order filled fast, position auto-closed successfully.")
    except Exception as exc:
        print("FAILED: " + str(exc))
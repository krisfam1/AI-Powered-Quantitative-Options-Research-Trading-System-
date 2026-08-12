"""One-off smoke test of the paper order pipeline.

Submits a single 1-share AAPL bracket order (stop-loss + take-profit)
through the same paper ``_trading_client`` and the same bracket structure
that ``live_trader.py`` uses, prints the broker's confirmation, then
immediately cancels it.

Deliberate differences from live_trader.py, for safety only:
- Nothing is written to trades.db or signal_log.db.
- The parent order is a LIMIT order priced ~5% BELOW the market instead of
  a market order. During market hours a 1-share market order would fill
  within milliseconds — before we could cancel — leaving a real position.
  A deeply non-marketable limit order exercises the identical submission
  path (bracket class, stop-loss, take-profit, DAY tif) but sits unfilled
  so the cancel is guaranteed to work.

Run:  python smoke_test_order.py
"""

import sys
import time
from datetime import datetime, timedelta, timezone

from alpaca.data import StockBarsRequest, StockHistoricalDataClient
from alpaca.data.enums import DataFeed
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import (
    LimitOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)

# Reuse the exact same paper trading client live_trader uses (paper=True).
from live_trader import _api_key, _secret_key, _trading_client

TICKER = "AAPL"
QTY = 1


def latest_price() -> float:
    """Most recent close from the permitted IEX feed."""
    client = StockHistoricalDataClient(_api_key, _secret_key)
    end = datetime.now(timezone.utc)
    bars = client.get_stock_bars(
        StockBarsRequest(
            symbol_or_symbols=TICKER,
            timeframe=TimeFrame.Minute,
            start=end - timedelta(days=5),
            end=end,
            feed=DataFeed.IEX,
        )
    )
    df = bars.df
    if df.empty:
        raise RuntimeError(f"No IEX bars returned for {TICKER}")
    return float(df["close"].iloc[-1])


def main() -> int:
    print("=" * 68)
    print("  SMOKE TEST — paper bracket order pipeline (no DB logging)")
    print("=" * 68)

    price = latest_price()
    # Non-marketable prices: limit 5% below market so it cannot fill.
    limit_price = round(price * 0.95, 2)
    stop_price = round(price * 0.90, 2)     # stop-loss below the limit
    target_price = round(price * 1.10, 2)   # take-profit above the market
    print(f"  Latest {TICKER} price (IEX): ${price:.2f}")
    print(f"  Limit ${limit_price:.2f}  stop ${stop_price:.2f}  target ${target_price:.2f}")

    # Same bracket structure as live_trader.py's order_request.
    order_request = LimitOrderRequest(
        symbol=TICKER,
        qty=QTY,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.BRACKET,
        limit_price=limit_price,
        take_profit=TakeProfitRequest(limit_price=target_price),
        stop_loss=StopLossRequest(stop_price=stop_price),
    )

    print("\n→ Submitting bracket order …")
    order = _trading_client.submit_order(order_request)
    print("  Order ID       :", order.id)
    print("  Status         :", order.status)
    print("  Submitted at   :", order.submitted_at)
    print("  Type / class   :", order.type, "/", order.order_class)
    print("  Limit price    :", order.limit_price)
    legs = order.legs or []
    for leg in legs:
        print(f"  Leg            : {leg.type}  status={leg.status}")

    print("\n→ Cancelling order …")
    _trading_client.cancel_order_by_id(order.id)

    # Confirm the cancel actually took (poll briefly).
    final = None
    for _ in range(10):
        time.sleep(1)
        final = _trading_client.get_order_by_id(order.id)
        if str(final.status).lower().endswith(("canceled", "cancelled")):
            break
    print("  Final status   :", final.status if final else "unknown")

    # Safety net: if anything filled in the gap, flatten it immediately.
    filled_qty = float(final.filled_qty or 0) if final else 0.0
    if filled_qty > 0:
        print(f"  ⚠ {filled_qty} share(s) filled before cancel — closing position …")
        _trading_client.close_position(TICKER)
        print("  Position closed.")

    ok = final is not None and "cancel" in str(final.status).lower()
    print("\n" + ("✅ PASS — order pipeline works end-to-end, nothing left open."
                  if ok and filled_qty == 0
                  else "⚠ Check output above — order did not end cleanly cancelled."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

from dotenv import load_dotenv
load_dotenv()

"""Exit monitoring for live options positions.

Alpaca does NOT support bracket orders for options, so unlike the stock bot,
we must actively check open positions ourselves and submit a separate closing
order when our stop-loss, take-profit, or expiry conditions are met.
"""

import os
import time
from datetime import date, datetime, timezone
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

import options_trade_log
from trade_reviewer import review_and_store_trade
from contract_price_extremes import get_contract_price_extremes
from options_evaluator import get_live_bid_price
from main import is_market_open
from overnight_hold_check import check_overnight_hold_safety
from reversal_detector import check_reversal_signal
from zoneinfo import ZoneInfo

api_key = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")

_trading_client = TradingClient(api_key, secret_key, paper=True)


def check_and_close_options_positions() -> int:
    if not is_market_open():
        return 0  # options orders can only be submitted during market hours

    open_positions = options_trade_log.get_open_positions()
    closed_count = 0

    for pos in open_positions:
        trade_id = pos["trade_id"]
        contract_symbol = pos["contract_symbol"]
        entry_premium = pos["entry_premium"]
        contracts = pos["contracts"]
        stop_loss_pct = pos["stop_loss_pct"]
        take_profit_pct = pos["take_profit_pct"]
        expiry_date_str = pos["expiry_date"]

        try:
            current_premium = get_live_bid_price(contract_symbol)
        except Exception as exc:
            print("  Could not fetch premium for " + contract_symbol + ": " + str(exc))
            continue

        pct_change = (current_premium - entry_premium) / entry_premium if entry_premium > 0 else 0
        expiry_date = date.fromisoformat(expiry_date_str)

        # SAFETY NET: force-close 2 days before actual expiry, regardless of
        # profit/loss, so the closing order always has real market-hours
        # margin to execute -- this avoids the position riding into actual
        # expiration, which risks auto-exercise/assignment if in-the-money.
        # This is a rare, last-resort trigger -- normal exits should happen
        # via stop_loss or take_profit well before this point.
        days_until_expiry = (expiry_date - date.today()).days
        approaching_expiry = days_until_expiry <= 2

        ET = ZoneInfo("America/New_York")
        now_et = datetime.now(ET)
        near_close = now_et.hour == 15 and now_et.minute >= 30  # last 30 min of trading

        exit_reason = None
        if pct_change <= -stop_loss_pct:
            exit_reason = "stop_loss"

        if exit_reason is None and pct_change >= 0.40:
            try:
                reversal_check = check_reversal_signal(pos["ticker"], pos["option_type"], pct_change)
                if reversal_check["reversal_detected"]:
                    exit_reason = "reversal_guard"
                    print("  REVERSAL GUARD TRIGGERED: " + reversal_check["reason"])
            except Exception as _rev_exc:
                print("  Reversal check failed (continuing normally): " + str(_rev_exc))

        if exit_reason is None and pct_change >= take_profit_pct:
            exit_reason = "take_profit"

        if exit_reason is None and approaching_expiry:
            exit_reason = "expiry_safety_net"

        if exit_reason is None and near_close:
            overnight_check = check_overnight_hold_safety(pos["ticker"], option_type=pos["option_type"])
            if not overnight_check["safe"]:
                exit_reason = "overnight_risk -- " + "; ".join(overnight_check["reasons"])

        print("  " + contract_symbol + ": entry=$" + str(entry_premium) + " current=$" + str(round(current_premium, 2)) + " (" + str(round(pct_change*100, 1)) + "%) -- " + (exit_reason if exit_reason else "holding"))

        if exit_reason is None:
            continue

        try:
            order_request = MarketOrderRequest(
                symbol=contract_symbol,
                qty=contracts,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
            sell_order = _trading_client.submit_order(order_request)

            # Poll briefly for the REAL fill price -- same as the entry-side
            # fix. Falls back to the current bid reading only if it genuinely
            # never fills in time.
            real_exit_premium = current_premium
            for _poll_attempt in range(10):
                time.sleep(1)
                try:
                    _refreshed_order = _trading_client.get_order_by_id(sell_order.id)
                    if _refreshed_order.filled_avg_price:
                        real_exit_premium = float(_refreshed_order.filled_avg_price)
                        break
                except Exception:
                    continue

            pnl_dollars = (real_exit_premium - entry_premium) * contracts * 100
            pnl_pct = (real_exit_premium - entry_premium) / entry_premium * 100 if entry_premium > 0 else 0

            options_trade_log.log_exit(trade_id, {
                "exit_date": datetime.now(timezone.utc).date().isoformat(),
                "exit_timestamp": datetime.now(timezone.utc).isoformat(),
                "exit_premium": real_exit_premium,
                "pnl_dollars": pnl_dollars,
                "pnl_pct": pnl_pct,
                "exit_reason": exit_reason,
            })
            closed_count += 1
            print("  Closed " + contract_symbol + ": " + exit_reason + ", P&L $" + str(round(pnl_dollars, 2)))

            try:
                review_trade_data = {
                    "ticker": pos["ticker"],
                    "contract_symbol": contract_symbol,
                    "option_type": pos["option_type"],
                    "entry_premium": entry_premium,
                    "exit_premium": real_exit_premium,
                    "contracts": contracts,
                    "pnl_dollars": pnl_dollars,
                    "pnl_pct": pnl_pct,
                    "exit_reason": exit_reason,
                    "entry_date": pos["entry_date"],
                    "expiry_date": pos["expiry_date"],
                }
                if pos.get("gamma_modifier") is not None:
                    review_trade_data["gamma_modifier"] = pos["gamma_modifier"]
                if pos.get("gamma_context"):
                    try:
                        import json as _json
                        review_trade_data["gamma_context"] = _json.loads(pos["gamma_context"])
                    except Exception:
                        review_trade_data["gamma_context"] = pos["gamma_context"]
                try:
                    extremes = get_contract_price_extremes(
                        contract_symbol, pos["entry_date"], datetime.now(timezone.utc).date().isoformat()
                    )
                    if "error" not in extremes:
                        review_trade_data["price_extremes"] = extremes
                except Exception:
                    pass  # peak/trough data is optional context, don't block the review over it
                review_and_store_trade(trade_id, review_trade_data)
                print("  AI review generated for " + contract_symbol)
            except Exception as review_exc:
                print("  AI review failed (trade still closed correctly): " + str(review_exc))
        except Exception as exc:
            print("  Failed to close " + contract_symbol + ": " + str(exc))

    return closed_count


if __name__ == "__main__":
    count = check_and_close_options_positions()
    print("\nChecked open options positions, closed " + str(count) + ".")
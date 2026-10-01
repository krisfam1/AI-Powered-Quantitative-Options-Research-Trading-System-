content = open('live_options_trader.py', encoding='utf-8').read()

old_import = "import time\n"
if old_import not in content:
    content = content.replace(
        "from datetime import datetime, timedelta, timezone\n",
        "from datetime import datetime, timedelta, timezone\nimport time\n",
        1,
    )

old = '''            order = _trading_client.submit_order(order_request)
            _safe_gamma_modifier = gamma_check.get("modifier") if "gamma_check" in locals() else None
            options_trade_log.log_entry({
                "trade_id": "opt-live-" + ticker + "-" + str(order.id),
                "ticker": ticker,
                "contract_symbol": best.symbol,
                "option_type": option_type,
                "entry_date": now.date().isoformat(),
                "entry_premium": premium,'''

new = '''            order = _trading_client.submit_order(order_request)

            # Poll briefly for the REAL fill price -- market orders may not
            # be filled the instant submit_order() returns. Falls back to
            # the pre-trade estimate only if it genuinely never fills in time.
            real_entry_premium = premium
            for _poll_attempt in range(10):
                time.sleep(1)
                try:
                    _refreshed_order = _trading_client.get_order_by_id(order.id)
                    if _refreshed_order.filled_avg_price:
                        real_entry_premium = float(_refreshed_order.filled_avg_price)
                        break
                except Exception:
                    continue

            _safe_gamma_modifier = gamma_check.get("modifier") if "gamma_check" in locals() else None
            options_trade_log.log_entry({
                "trade_id": "opt-live-" + ticker + "-" + str(order.id),
                "ticker": ticker,
                "contract_symbol": best.symbol,
                "option_type": option_type,
                "entry_date": now.date().isoformat(),
                "entry_premium": real_entry_premium,'''

if old not in content:
    print("Could not find target -- no changes made.")
else:
    content = content.replace(old, new, 1)
    with open('live_options_trader.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed entry price logging to use real Alpaca fill price (with brief poll).")
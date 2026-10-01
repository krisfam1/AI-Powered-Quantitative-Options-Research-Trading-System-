content = open('options_exit_monitor.py', encoding='utf-8').read()

old_import = "import os\n"
new_import = "import os\nimport time\n"

if old_import not in content:
    print("Could not find import line -- no changes made.")
else:
    content = content.replace(old_import, new_import, 1)
    print("Added time import.")

old = '''            _trading_client.submit_order(order_request)

            pnl_dollars = (current_premium - entry_premium) * contracts * 100
            pnl_pct = pct_change * 100'''

new = '''            sell_order = _trading_client.submit_order(order_request)

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
            pnl_pct = (real_exit_premium - entry_premium) / entry_premium * 100 if entry_premium > 0 else 0'''

if old not in content:
    print("Could not find target -- no changes made.")
else:
    content = content.replace(old, new, 1)
    print("Added exit-price polling for real fill accuracy.")

    old_log = '"exit_premium": current_premium,\n'
    new_log = '"exit_premium": real_exit_premium,\n'
    content = content.replace(old_log, new_log)
    print("Updated logged exit_premium to use real fill price.")

with open('options_exit_monitor.py', 'w', encoding='utf-8') as f:
    f.write(content)
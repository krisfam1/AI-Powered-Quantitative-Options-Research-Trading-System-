content = open('options_backtest_engine.py', encoding='utf-8').read()

old_param = '    target_delta: float = None,  # if set, overrides strike_offset_pct with delta-based strike selection\n'
new_param = old_param + '    apply_spread_cost: bool = False,  # ESTIMATED, not real data -- models bid-ask spread cost\n'

if old_param not in content:
    print("Could not find parameter insertion point -- no changes made.")
else:
    content = content.replace(old_param, new_param, 1)
    print("Added apply_spread_cost parameter.")

    old_func_marker = "def calculate_historical_volatility"
    spread_func = '''def _estimated_spread_cost_pct(option_price: float) -> float:
    """
    ESTIMATE, not real market data -- models round-trip bid-ask spread cost
    as a percentage of price, scaled inversely with price (cheaper options
    have proportionally wider spreads). Used only as a sensitivity test,
    not a validated cost model.
    """
    if option_price >= 5.0:
        return 0.02
    elif option_price >= 2.0:
        return 0.04
    elif option_price >= 1.0:
        return 0.07
    else:
        return 0.12


def calculate_historical_volatility'''

    if old_func_marker not in content:
        print("Could not find insertion point for spread function -- no changes made.")
    else:
        content = content.replace(old_func_marker, spread_func, 1)
        print("Added _estimated_spread_cost_pct helper function.")

    old_entry_premium = '            entry_premium = black_scholes_price(stock_price, strike, dte_target, vol, option_type=option_type)\n'
    new_entry_premium = '''            entry_premium = black_scholes_price(stock_price, strike, dte_target, vol, option_type=option_type)
            if apply_spread_cost:
                entry_premium = entry_premium * (1 + _estimated_spread_cost_pct(entry_premium) / 2)
'''

    if old_entry_premium not in content:
        print("Could not find entry_premium line -- no changes made to that part.")
    else:
        content = content.replace(old_entry_premium, new_entry_premium, 1)
        print("Applied spread cost to entry premium (pay slightly more, modeling the ask side).")

    old_exit_calc = '''                pnl_dollars = (current_option_value - entry_value) * open_position["contracts"] * 100
                trades.append({'''
    new_exit_calc = '''                _exit_value_after_spread = current_option_value
                if apply_spread_cost:
                    _exit_value_after_spread = current_option_value * (1 - _estimated_spread_cost_pct(current_option_value) / 2)
                pnl_dollars = (_exit_value_after_spread - entry_value) * open_position["contracts"] * 100
                trades.append({'''

    if old_exit_calc not in content:
        print("Could not find exit pnl calculation -- no changes made to that part.")
    else:
        content = content.replace(old_exit_calc, new_exit_calc, 1)
        print("Applied spread cost to exit value (receive slightly less, modeling the bid side).")

    with open('options_backtest_engine.py', 'w', encoding='utf-8') as f:
        f.write(content)
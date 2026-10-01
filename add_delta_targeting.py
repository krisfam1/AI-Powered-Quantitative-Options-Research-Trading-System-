content = open('options_backtest_engine.py', encoding='utf-8').read()

old_param = '    require_elevated_volatility: bool = False,  # only enter when realized vol is above its own 60-bar trailing median\n'
new_param = old_param + '    target_delta: float = None,  # if set, overrides strike_offset_pct with delta-based strike selection\n'

if old_param not in content:
    print("Could not find parameter insertion point -- no changes made.")
else:
    content = content.replace(old_param, new_param, 1)
    print("Added target_delta parameter.")

    old_strike = '            strike = round(stock_price * (1 + strike_offset_pct), 2)\n'
    new_strike = '''            if target_delta is not None:
                from delta_strike_finder import find_strike_for_target_delta
                _vol_for_strike = calculate_historical_volatility(bars, index)
                strike = find_strike_for_target_delta(stock_price, dte_target, _vol_for_strike, option_type, target_delta)
            else:
                strike = round(stock_price * (1 + strike_offset_pct), 2)
'''

    if old_strike not in content:
        print("Could not find strike selection line -- no changes made to that part.")
    else:
        content = content.replace(old_strike, new_strike, 1)
        print("Wired delta-based strike selection into the entry logic.")

    with open('options_backtest_engine.py', 'w', encoding='utf-8') as f:
        f.write(content)
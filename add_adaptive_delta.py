content = open('options_backtest_engine.py', encoding='utf-8').read()

old_param = '    target_delta: float = None,  # if set, overrides strike_offset_pct with delta-based strike selection\n'
new_param = old_param + '    adaptive_delta: bool = False,  # if True, scales target_delta by entry score conviction (overrides target_delta)\n'

if old_param not in content:
    print("Could not find parameter insertion point -- no changes made.")
else:
    content = content.replace(old_param, new_param, 1)
    print("Added adaptive_delta parameter.")

    old_strike = '''            if target_delta is not None:
                from delta_strike_finder import find_strike_for_target_delta
                _vol_for_strike = calculate_historical_volatility(bars, index)
                strike = find_strike_for_target_delta(stock_price, dte_target, _vol_for_strike, option_type, target_delta)
            else:
                strike = round(stock_price * (1 + strike_offset_pct), 2)
'''

    new_strike = '''            if adaptive_delta:
                from delta_strike_finder import find_strike_for_target_delta
                _vol_for_strike = calculate_historical_volatility(bars, index)
                _score_for_delta = _score_result["total_score"] if entry_mode == "weighted" else 50
                if _score_for_delta >= 80:
                    _adaptive_target = 0.20
                elif _score_for_delta >= 60:
                    _adaptive_target = 0.30
                elif _score_for_delta >= 40:
                    _adaptive_target = 0.35
                else:
                    _adaptive_target = 0.45
                strike = find_strike_for_target_delta(stock_price, dte_target, _vol_for_strike, option_type, _adaptive_target)
            elif target_delta is not None:
                from delta_strike_finder import find_strike_for_target_delta
                _vol_for_strike = calculate_historical_volatility(bars, index)
                strike = find_strike_for_target_delta(stock_price, dte_target, _vol_for_strike, option_type, target_delta)
            else:
                strike = round(stock_price * (1 + strike_offset_pct), 2)
'''

    if old_strike not in content:
        print("Could not find strike selection block -- no changes made to that part.")
    else:
        content = content.replace(old_strike, new_strike, 1)
        print("Wired adaptive delta selection based on entry score conviction.")

    with open('options_backtest_engine.py', 'w', encoding='utf-8') as f:
        f.write(content)
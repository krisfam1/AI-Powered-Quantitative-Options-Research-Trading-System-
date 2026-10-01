content = open('options_backtest_engine.py', encoding='utf-8').read()

old = '''            elif exit_mode == "reversal_guard" and pct_change >= 0.40 and index >= 6:
                _closes = [float(bars[i].close) for i in range(index - 6, index + 1)]
                _last_two = _closes[-2:]
                _ma_before = sum(_closes[-7:-2]) / 5
                if option_type == "call" and all(c < _ma_before for c in _last_two):
                    exit_reason = "reversal_guard"
                elif option_type == "put" and all(c > _ma_before for c in _last_two):
                    exit_reason = "reversal_guard"'''

new = '''            elif exit_mode == "reversal_guard" and pct_change >= 0.40 and index >= 6:
                _closes = [float(bars[i].close) for i in range(index - 6, index + 1)]
                _last_two = _closes[-2:]
                _ma_before = sum(_closes[-7:-2]) / 5
                if option_type == "call" and all(c < _ma_before for c in _last_two):
                    exit_reason = "reversal_guard"
                elif option_type == "put" and all(c > _ma_before for c in _last_two):
                    exit_reason = "reversal_guard"
            elif exit_mode == "time_decay" and days_left <= 10:
                try:
                    from time_decay_exit import check_time_decay_exit
                    _decay_result = check_time_decay_exit(ticker, bars, index, option_type, open_position["strike"], days_left, current_option_value)
                    if _decay_result["should_exit"]:
                        exit_reason = "time_decay"
                except Exception:
                    pass'''

if old not in content:
    print("Could not find target -- no changes made.")
else:
    new_content = content.replace(old, new, 1)
    with open('options_backtest_engine.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Added time_decay exit mode to the backtest engine.")
content = open('options_backtest_engine.py', encoding='utf-8').read()

old_param = '    require_entry_confirmation: bool = False,  # require breakout to hold for 2 consecutive bars before entering\n'
new_param = old_param + '    require_close_strength: bool = False,  # require the triggering bar to close in the strong part of its own range\n'

if old_param not in content:
    print("Could not find parameter insertion point -- no changes made.")
else:
    content = content.replace(old_param, new_param, 1)
    print("Added require_close_strength parameter.")

    old_weighted_gate = '''                if require_entry_confirmation and index >= 1:
                    _prev_qualified_w = False
                    if option_type == "call":
                        _prev_qualified_w = be.check_breakout(bars, index - 1, lookback=20)
                    else:
                        _prev_qualified_w = be.check_breakdown(bars, index - 1, lookback=20)
                    if not _prev_qualified_w:
                        continue
'''

    new_weighted_gate = '''                if require_entry_confirmation and index >= 1:
                    _prev_qualified_w = False
                    if option_type == "call":
                        _prev_qualified_w = be.check_breakout(bars, index - 1, lookback=20)
                    else:
                        _prev_qualified_w = be.check_breakdown(bars, index - 1, lookback=20)
                    if not _prev_qualified_w:
                        continue

                if require_close_strength:
                    _bar_high = float(bars[index].high)
                    _bar_low = float(bars[index].low)
                    _bar_close = float(bars[index].close)
                    _bar_range = _bar_high - _bar_low
                    if _bar_range > 0:
                        _close_position = (_bar_close - _bar_low) / _bar_range
                        if option_type == "call" and _close_position < 0.70:
                            continue
                        if option_type == "put" and _close_position > 0.30:
                            continue
'''

    if old_weighted_gate not in content:
        print("Could not find weighted gate insertion point -- no changes made to that part.")
    else:
        content = content.replace(old_weighted_gate, new_weighted_gate, 1)
        print("Added close-strength filter to weighted mode.")

    with open('options_backtest_engine.py', 'w', encoding='utf-8') as f:
        f.write(content)
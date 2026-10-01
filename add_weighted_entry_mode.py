content = open('options_backtest_engine.py', encoding='utf-8').read()

old_param = '    exclude_first_n_minutes: int = 0,  # skip entries within N minutes of market open (9:30 AM ET)\n'
new_param = old_param + '    entry_mode: str = "binary",  # "binary" = existing AND-gate, "weighted" = scored entry\n    entry_score_threshold: float = 60.0,  # min score (0-100) required when entry_mode="weighted"\n'

if old_param not in content:
    print("Could not find parameter insertion point -- no changes made.")
else:
    content = content.replace(old_param, new_param, 1)
    print("Added entry_mode and entry_score_threshold parameters.")

    old_gate = '''            if option_type == "call" and not be.check_breakout(bars, index, lookback=20):
                continue
            if option_type == "put" and not be.check_breakdown(bars, index, lookback=20):
                continue
            rv = be.calculate_relative_volume(bars, index)
            if rv < 1.5:
                continue'''

    new_gate = '''            if entry_mode == "weighted":
                from entry_scorer import calculate_entry_score
                _score_result = calculate_entry_score(ticker, bars, index, option_type, spy_regime=_spy_regime)
                if _score_result["total_score"] < entry_score_threshold:
                    continue
            else:
                if option_type == "call" and not be.check_breakout(bars, index, lookback=20):
                    continue
                if option_type == "put" and not be.check_breakdown(bars, index, lookback=20):
                    continue
                rv = be.calculate_relative_volume(bars, index)
                if rv < 1.5:
                    continue'''

    if old_gate not in content:
        print("Could not find entry gate block -- no changes made to that part.")
    else:
        content = content.replace(old_gate, new_gate, 1)
        print("Wired weighted entry mode into the entry gate.")

    old_loop_start = "    open_position = None\n\n    for index, bar in enumerate(bars):\n"
    new_loop_start = '''    _spy_regime = "neutral"
    if entry_mode == "weighted":
        try:
            _spy_regime = be.get_daily_regime("SPY", bars[0].timestamp, period=50)
        except Exception:
            _spy_regime = "neutral"

    open_position = None

    for index, bar in enumerate(bars):
'''
    if old_loop_start not in content:
        print("Could not find loop start -- no changes made to that part.")
    else:
        content = content.replace(old_loop_start, new_loop_start, 1)
        print("Added SPY regime computation (once per backtest run).")

    with open('options_backtest_engine.py', 'w', encoding='utf-8') as f:
        f.write(content)
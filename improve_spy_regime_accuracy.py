content = open('options_backtest_engine.py', encoding='utf-8').read()

old_spy_setup = '''    _spy_regime = "neutral"
    if entry_mode == "weighted":
        try:
            _spy_regime = be.get_daily_regime("SPY", bars[0].timestamp, period=50)
        except Exception:
            _spy_regime = "neutral"

    open_position = None

    for index, bar in enumerate(bars):
'''

new_spy_setup = '''    _spy_regime = "neutral"
    _spy_regime_last_checked_date = None

    def _refresh_spy_regime_if_needed(current_timestamp):
        nonlocal _spy_regime, _spy_regime_last_checked_date
        current_date = current_timestamp.date()
        if _spy_regime_last_checked_date is None or (current_date - _spy_regime_last_checked_date).days >= 5:
            try:
                _spy_regime = be.get_daily_regime("SPY", current_timestamp, period=50)
            except Exception:
                pass
            _spy_regime_last_checked_date = current_date

    open_position = None

    for index, bar in enumerate(bars):
'''

if old_spy_setup not in content:
    print("Could not find SPY setup block -- no changes made.")
else:
    content = content.replace(old_spy_setup, new_spy_setup, 1)
    print("Replaced with periodic SPY regime refresh function.")

    old_gate = '''            if entry_mode == "weighted":
                from entry_scorer import calculate_entry_score
                _score_result = calculate_entry_score(ticker, bars, index, option_type, spy_regime=_spy_regime)'''

    new_gate = '''            if entry_mode == "weighted":
                _refresh_spy_regime_if_needed(timestamp)
                from entry_scorer import calculate_entry_score
                _score_result = calculate_entry_score(ticker, bars, index, option_type, spy_regime=_spy_regime)'''

    if old_gate not in content:
        print("Could not find entry gate call -- no changes made to that part.")
    else:
        content = content.replace(old_gate, new_gate, 1)
        print("Wired periodic refresh into the entry gate (checks every 5 days).")

    with open('options_backtest_engine.py', 'w', encoding='utf-8') as f:
        f.write(content)
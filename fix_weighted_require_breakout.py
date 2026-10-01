content = open('options_backtest_engine.py', encoding='utf-8').read()

old_gate = '''            if entry_mode == "weighted":
                _refresh_spy_regime_if_needed(timestamp)
                from entry_scorer import calculate_entry_score
                _score_result = calculate_entry_score(ticker, bars, index, option_type, spy_regime=_spy_regime)
                if _score_result["total_score"] < entry_score_threshold:
                    continue'''

new_gate = '''            if entry_mode == "weighted":
                # MANDATORY: real breakout/breakdown confirmation required, same
                # as the original binary system -- the weighted score then
                # determines which of THESE genuinely confirmed setups are
                # strong enough, rather than letting volume alone substitute
                # for a real breakout.
                if option_type == "call" and not be.check_breakout(bars, index, lookback=20):
                    continue
                if option_type == "put" and not be.check_breakdown(bars, index, lookback=20):
                    continue

                _refresh_spy_regime_if_needed(timestamp)
                from entry_scorer import calculate_entry_score
                _score_result = calculate_entry_score(ticker, bars, index, option_type, spy_regime=_spy_regime)
                if _score_result["total_score"] < entry_score_threshold:
                    continue'''

if old_gate not in content:
    print("Could not find target -- no changes made.")
else:
    new_content = content.replace(old_gate, new_gate, 1)
    with open('options_backtest_engine.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Made breakout/breakdown confirmation mandatory in weighted mode.")
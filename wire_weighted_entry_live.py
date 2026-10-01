content = open('live_options_trader.py', encoding='utf-8').read()

old = '''    if blocks:
        _log_options_signal(ticker, False, blocks)
        result["note"] = "; ".join(blocks)
        return result

    breaker_check = check_ticker_circuit_breaker(ticker)'''

new = '''    if blocks:
        _log_options_signal(ticker, False, blocks)
        result["note"] = "; ".join(blocks)
        return result

    try:
        from entry_scorer import calculate_entry_score
        _spy_regime = get_daily_regime("SPY", now_dt, period=50)
        _score_result = calculate_entry_score(ticker, bars, index, option_type, spy_regime=_spy_regime)
        if _score_result["total_score"] < 20:
            note = "entry score too low (" + str(_score_result["total_score"]) + "/100, need 20+)"
            _log_options_signal(ticker, False, [], note=note)
            result["note"] = note
            return result
    except Exception as _score_exc:
        # If scoring fails for any reason, do NOT block the trade -- fall
        # back to the already-confirmed breakout signal, same as before
        # this system existed. Fail safe, not fail closed.
        pass

    breaker_check = check_ticker_circuit_breaker(ticker)'''

if old not in content:
    print("Could not find target -- no changes made.")
else:
    new_content = content.replace(old, new, 1)
    with open('live_options_trader.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Wired weighted entry scoring into live trading, with safe fallback on any error.")
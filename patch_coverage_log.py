content = open('portfolio_backtest.py', encoding='utf-8').read()

old = '''                        v2_coverage_log.append({
                            "ticker": ticker, "signal_timestamp": timestamp, "strike": strike,
                            "direction": direction, "v2_iv_available": _v2_iv_available,
                            "v2_skip_reason": _v2_skip_reason,
                        })'''

new = '''                        v2_coverage_log.append({
                            "ticker": ticker, "signal_timestamp": timestamp, "strike": strike,
                            "direction": direction, "v2_iv_available": _v2_iv_available,
                            "v2_skip_reason": _v2_skip_reason,
                            "v1_vol": vol, "v2_iv": (_v2_result["historical_iv"] if _v2_iv_available else None),
                            "underlying_price": current_price, "target_dte": dte_target,
                            "v1_raw_price": black_scholes_price(current_price, strike, dte_target, vol, option_type=direction),
                            "v2_raw_price": (black_scholes_price(current_price, strike, dte_target, _v2_result["historical_iv"], option_type=direction) if _v2_iv_available else None),
                        })'''

if old not in content:
    print("Pattern not found -- no changes made. Send this message back for investigation.")
else:
    content = content.replace(old, new, 1)
    with open('portfolio_backtest.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patch applied successfully.")
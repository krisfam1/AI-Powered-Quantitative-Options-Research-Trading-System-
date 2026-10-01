content = open('portfolio_backtest.py', encoding='utf-8').read()

old = '''                                if pricing_mode == "v2_corrected" and _v2_iv_available:
                                    ticker_position_meta[position_id]["v2_contract"] = _v2_result["contract"]
                                    ticker_position_meta[position_id]["v2_exp_date_str"] = expiry_date.isoformat()
                                    ticker_position_meta[position_id]["v2_last_checkpoint_date"] = timestamp.date()
                                    ticker_position_meta[position_id]["v2_last_iv"] = _v2_result["historical_iv"]
                                    ticker_position_meta[position_id]["v2_checkpoint_gaps"] = 0
                                    ticker_position_meta[position_id]["v2_entry_date"] = timestamp.date()'''

new = '''                                if pricing_mode == "v2_corrected" and _v2_iv_available:
                                    ticker_position_meta[position_id]["v2_contract"] = _v2_result["contract"]
                                    # HONEST FIX: use the REAL matched contract's actual expiration
                                    # (parsed from the contract symbol itself), NOT the synthetic
                                    # flat-14-day target expiry_date -- these silently diverged
                                    # whenever the closest real match wasn't exactly 14 DTE,
                                    # causing every later checkpoint lookup to query the wrong
                                    # expiration and falsely report a "gap" even when real IV
                                    # data was genuinely available the whole time.
                                    import re as _re
                                    _m = _re.match(r"^[A-Z]+(\\d{6})[CP]\\d{8}$", _v2_result["contract"])
                                    _real_exp_date = datetime.strptime("20" + _m.group(1), "%Y%m%d").date() if _m else expiry_date
                                    ticker_position_meta[position_id]["v2_exp_date_str"] = _real_exp_date.isoformat()
                                    ticker_position_meta[position_id]["v2_last_checkpoint_date"] = timestamp.date()
                                    ticker_position_meta[position_id]["v2_last_iv"] = _v2_result["historical_iv"]
                                    ticker_position_meta[position_id]["v2_checkpoint_gaps"] = 0
                                    ticker_position_meta[position_id]["v2_entry_date"] = timestamp.date()'''

if old not in content:
    print("Pattern not found -- no changes made.")
else:
    content = content.replace(old, new, 1)
    with open('portfolio_backtest.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Real-expiration fix applied: v2_exp_date_str now uses the actual matched contract's real expiration, not the synthetic target.")
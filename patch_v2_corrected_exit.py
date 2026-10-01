content = open('portfolio_backtest.py', encoding='utf-8').read()

# --- PATCH 1: Extend entry-side check to include "v2_corrected", and store contract identity ---
old1 = '''                        if pricing_mode == "v2_entry_iv":
                            _v2_result = get_v2_entry_iv(ticker, timestamp, strike, option_type=direction, target_dte=dte_target)
                            if _v2_result is not None:
                                _pricing_vol = _v2_result["historical_iv"]
                                _v2_iv_available = True
                            else:
                                _v2_skip_reason = "no_valid_historical_iv"'''

new1 = '''                        if pricing_mode in ("v2_entry_iv", "v2_corrected"):
                            _v2_result = get_v2_entry_iv(ticker, timestamp, strike, option_type=direction, target_dte=dte_target)
                            if _v2_result is not None:
                                _pricing_vol = _v2_result["historical_iv"]
                                _v2_iv_available = True
                            else:
                                _v2_skip_reason = "no_valid_historical_iv"'''

if old1 not in content:
    print("PATCH 1 pattern not found -- aborting, no changes made.")
    exit()
content = content.replace(old1, new1, 1)

# --- PATCH 2: store contract identity + checkpoint cache fields when opening a v2_corrected position ---
old2 = '''                            position_id = account.open_position(ticker, timestamp, contracts, entry_premium, strike=strike, option_type=direction, expiry_date=expiry_date)
                            if position_id is not None:
                                ticker_positions[ticker] = position_id
                                ticker_position_meta[position_id] = {"strike": strike, "option_type": direction, "expiry_date": expiry_date}'''

new2 = '''                            position_id = account.open_position(ticker, timestamp, contracts, entry_premium, strike=strike, option_type=direction, expiry_date=expiry_date)
                            if position_id is not None:
                                ticker_positions[ticker] = position_id
                                ticker_position_meta[position_id] = {"strike": strike, "option_type": direction, "expiry_date": expiry_date}
                                if pricing_mode == "v2_corrected" and _v2_iv_available:
                                    ticker_position_meta[position_id]["v2_contract"] = _v2_result["contract"]
                                    ticker_position_meta[position_id]["v2_exp_date_str"] = expiry_date.isoformat()
                                    ticker_position_meta[position_id]["v2_last_checkpoint_date"] = timestamp.date()
                                    ticker_position_meta[position_id]["v2_last_iv"] = _v2_result["historical_iv"]
                                    ticker_position_meta[position_id]["v2_checkpoint_gaps"] = 0'''

if old2 not in content:
    print("PATCH 2 pattern not found -- aborting, no changes made.")
    exit()
content = content.replace(old2, new2, 1)

with open('portfolio_backtest.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("PATCH 1 and 2 applied successfully.")
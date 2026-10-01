content = open('portfolio_backtest.py', encoding='utf-8').read()

old = '''                                if pricing_mode == "v2_corrected" and _v2_iv_available:
                                    ticker_position_meta[position_id]["v2_contract"] = _v2_result["contract"]
                                    ticker_position_meta[position_id]["v2_exp_date_str"] = expiry_date.isoformat()
                                    ticker_position_meta[position_id]["v2_last_checkpoint_date"] = timestamp.date()
                                    ticker_position_meta[position_id]["v2_last_iv"] = _v2_result["historical_iv"]
                                    ticker_position_meta[position_id]["v2_checkpoint_gaps"] = 0'''

new = '''                                if pricing_mode == "v2_corrected" and _v2_iv_available:
                                    ticker_position_meta[position_id]["v2_contract"] = _v2_result["contract"]
                                    ticker_position_meta[position_id]["v2_exp_date_str"] = expiry_date.isoformat()
                                    ticker_position_meta[position_id]["v2_last_checkpoint_date"] = timestamp.date()
                                    ticker_position_meta[position_id]["v2_last_iv"] = _v2_result["historical_iv"]
                                    ticker_position_meta[position_id]["v2_checkpoint_gaps"] = 0
                                    ticker_position_meta[position_id]["v2_entry_date"] = timestamp.date()'''

if old not in content:
    print("PATCH A not found -- aborting.")
    exit()
content = content.replace(old, new, 1)

old2 = '''    else:
        # HONEST FIX: mark this day as checked even on failure, so a genuine
        # gap is logged ONCE per calendar day, not re-attempted and re-logged
        # on every single intraday bar for the rest of that day.
        meta["v2_last_checkpoint_date"] = current_date
        meta["v2_checkpoint_gaps"] = meta.get("v2_checkpoint_gaps", 0) + 1
        if gap_log is not None:
            gap_log.append({"ticker": ticker, "contract": meta["v2_contract"], "checkpoint_date": current_date, "carried_forward_iv": meta["v2_last_iv"]})
        return meta["v2_last_iv"]'''

new2 = '''    else:
        meta["v2_last_checkpoint_date"] = current_date
        meta["v2_checkpoint_gaps"] = meta.get("v2_checkpoint_gaps", 0) + 1
        if gap_log is not None:
            gap_log.append({"ticker": ticker, "contract": meta["v2_contract"], "checkpoint_date": current_date, "carried_forward_iv": meta["v2_last_iv"], "entry_date": meta.get("v2_entry_date"), "exp_date_str": meta.get("v2_exp_date_str")})
        return meta["v2_last_iv"]'''

if old2 not in content:
    print("PATCH B not found -- aborting.")
    exit()
content = content.replace(old2, new2, 1)

with open('portfolio_backtest.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Gap-log entry_date fix applied successfully.")
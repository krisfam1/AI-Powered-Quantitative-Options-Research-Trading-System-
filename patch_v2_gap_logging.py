content = open('portfolio_backtest.py', encoding='utf-8').read()

# --- PATCH 6: add a proper, function-level gap log so checkpoint gaps are never silently lost ---
old6 = '''    v2_coverage_log = []  # records every qualifying signal's V2 IV availability, even when pricing_mode="v1" is unused for this run'''
new6 = '''    v2_coverage_log = []  # records every qualifying signal's V2 IV availability, even when pricing_mode="v1" is unused for this run
    v2_checkpoint_gap_log = []  # records every genuine checkpoint-IV gap under pricing_mode="v2_corrected" -- never silent'''

if old6 not in content:
    print("PATCH 6a pattern not found -- aborting.")
    exit()
content = content.replace(old6, new6, 1)

# Pass the gap log into the helper via a nonlocal-style approach: append directly using a closure-friendly pattern
old6b = '''def _get_v2_checkpoint_vol(meta, ticker, timestamp):'''
new6b = '''def _get_v2_checkpoint_vol(meta, ticker, timestamp, gap_log=None):'''
if old6b not in content:
    print("PATCH 6b pattern not found -- aborting.")
    exit()
content = content.replace(old6b, new6b, 1)

old6c = '''    else:
        meta["v2_checkpoint_gaps"] = meta.get("v2_checkpoint_gaps", 0) + 1
        return meta["v2_last_iv"]'''
new6c = '''    else:
        meta["v2_checkpoint_gaps"] = meta.get("v2_checkpoint_gaps", 0) + 1
        if gap_log is not None:
            gap_log.append({"ticker": ticker, "contract": meta["v2_contract"], "checkpoint_date": current_date, "carried_forward_iv": meta["v2_last_iv"]})
        return meta["v2_last_iv"]'''
if old6c not in content:
    print("PATCH 6c pattern not found -- aborting.")
    exit()
content = content.replace(old6c, new6c, 1)

# Update both call sites to pass the gap log
old6d = '''                vol = _get_v2_checkpoint_vol(meta, ticker, timestamp)
            current_option_value'''
new6d = '''                vol = _get_v2_checkpoint_vol(meta, ticker, timestamp, gap_log=v2_checkpoint_gap_log)
            current_option_value'''
if old6d not in content:
    print("PATCH 6d pattern not found -- aborting.")
    exit()
content = content.replace(old6d, new6d, 1)

old6e = '''                    vol = _get_v2_checkpoint_vol(meta, ticker, timestamp)
                val = black_scholes_price'''
new6e = '''                    vol = _get_v2_checkpoint_vol(meta, ticker, timestamp, gap_log=v2_checkpoint_gap_log)
                val = black_scholes_price'''
if old6e not in content:
    print("PATCH 6e pattern not found -- aborting.")
    exit()
content = content.replace(old6e, new6e, 1)

# Add to the final return dict
old6f = '''        "v2_coverage_log": v2_coverage_log,'''
new6f = '''        "v2_coverage_log": v2_coverage_log,
        "v2_checkpoint_gap_log": v2_checkpoint_gap_log,'''
if old6f not in content:
    print("PATCH 6f pattern not found -- aborting.")
    exit()
content = content.replace(old6f, new6f, 1)

with open('portfolio_backtest.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("PATCH 6 (gap logging) applied successfully.")
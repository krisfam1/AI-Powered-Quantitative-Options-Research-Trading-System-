content = open('portfolio_backtest.py', encoding='utf-8').read()

old = '''    v2_coverage_log = []  # records every qualifying signal's V2 IV availability, even when pricing_mode="v1" is unused for this run
    v2_checkpoint_gap_log = []  # records every genuine checkpoint-IV gap under pricing_mode="v2_corrected" -- never silent'''

new = '''    v2_coverage_log = []  # records every qualifying signal's V2 IV availability, even when pricing_mode="v1" is unused for this run
    v2_checkpoint_gap_log = []  # records every genuine checkpoint-IV gap under pricing_mode="v2_corrected" -- never silent
    v1_ground_truth_log = []  # Phase 7: records the REAL underlying price/vol at every entry, regardless of pricing_mode, for reconstruction validation only -- never used in any pricing decision'''

if old not in content:
    print("PATCH A not found -- aborting.")
    exit()
content = content.replace(old, new, 1)

old2 = '''                        v2_coverage_log.append({'''
new2 = '''                        v1_ground_truth_log.append({
                            "ticker": ticker, "entry_date": timestamp.date(), "underlying_price": current_price,
                            "v1_realized_vol": vol, "strike": strike, "entry_premium_final": None,  # filled below after computation
                        })
                        v2_coverage_log.append({'''
if old2 not in content:
    print("PATCH B not found -- aborting.")
    exit()
content = content.replace(old2, new2, 1)

old3 = '''        "v2_coverage_log": v2_coverage_log,
        "v2_checkpoint_gap_log": v2_checkpoint_gap_log,'''
new3 = '''        "v2_coverage_log": v2_coverage_log,
        "v2_checkpoint_gap_log": v2_checkpoint_gap_log,
        "v1_ground_truth_log": v1_ground_truth_log,'''
if old3 not in content:
    print("PATCH C not found -- aborting.")
    exit()
content = content.replace(old3, new3, 1)

with open('portfolio_backtest.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Ground-truth logging patch applied successfully.")
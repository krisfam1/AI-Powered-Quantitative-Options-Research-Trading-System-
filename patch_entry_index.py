content = open('portfolio_backtest.py', encoding='utf-8').read()

old = '''                        v1_ground_truth_log.append({
                            "ticker": ticker, "entry_date": timestamp.date(), "underlying_price": current_price,
                            "v1_realized_vol": vol, "strike": strike, "entry_premium_final": None,  # filled below after computation
                        })'''

new = '''                        v1_ground_truth_log.append({
                            "ticker": ticker, "entry_date": timestamp.date(), "underlying_price": current_price,
                            "v1_realized_vol": vol, "strike": strike, "entry_premium_final": None,  # filled below after computation
                            "entry_index": index,
                        })'''

if old not in content:
    print("Pattern not found -- no changes made.")
else:
    content = content.replace(old, new, 1)
    with open('portfolio_backtest.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Entry-index logging added successfully.")
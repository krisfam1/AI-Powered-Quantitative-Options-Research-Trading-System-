content = open('portfolio_backtest.py', encoding='utf-8').read()

old = '''    else:
        meta["v2_checkpoint_gaps"] = meta.get("v2_checkpoint_gaps", 0) + 1
        if gap_log is not None:
            gap_log.append({"ticker": ticker, "contract": meta["v2_contract"], "checkpoint_date": current_date, "carried_forward_iv": meta["v2_last_iv"]})
        return meta["v2_last_iv"]'''

new = '''    else:
        # HONEST FIX: mark this day as checked even on failure, so a genuine
        # gap is logged ONCE per calendar day, not re-attempted and re-logged
        # on every single intraday bar for the rest of that day.
        meta["v2_last_checkpoint_date"] = current_date
        meta["v2_checkpoint_gaps"] = meta.get("v2_checkpoint_gaps", 0) + 1
        if gap_log is not None:
            gap_log.append({"ticker": ticker, "contract": meta["v2_contract"], "checkpoint_date": current_date, "carried_forward_iv": meta["v2_last_iv"]})
        return meta["v2_last_iv"]'''

if old not in content:
    print("Pattern not found -- no changes made.")
else:
    content = content.replace(old, new, 1)
    with open('portfolio_backtest.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Gap-caching bug fixed: failed lookups now correctly cached per-day, not re-attempted every bar.")
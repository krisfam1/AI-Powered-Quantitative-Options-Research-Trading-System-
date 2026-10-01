content = open('options_exit_monitor.py', encoding='utf-8').read()

old = '''        elif near_close:
            overnight_check = check_overnight_hold_safety(pos["ticker"])
            if not overnight_check["safe"]:
                exit_reason = "overnight_risk -- " + "; ".join(overnight_check["reasons"])'''

new = '''        elif near_close:
            overnight_check = check_overnight_hold_safety(pos["ticker"], option_type=pos["option_type"])
            if not overnight_check["safe"]:
                exit_reason = "overnight_risk -- " + "; ".join(overnight_check["reasons"])

        print("  " + contract_symbol + ": entry=$" + str(entry_premium) + " current=$" + str(round(current_premium, 2)) + " (" + str(round(pct_change*100, 1)) + "%) -- " + (exit_reason if exit_reason else "holding"))'''

if old not in content:
    print("Could not find target -- no changes made.")
else:
    new_content = content.replace(old, new, 1)
    with open('options_exit_monitor.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Fixed option_type passing and added verbose per-position logging.")
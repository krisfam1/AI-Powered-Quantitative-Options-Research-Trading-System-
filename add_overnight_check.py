content = open('options_exit_monitor.py', encoding='utf-8').read()

old_import = "from main import is_market_open\n"
new_import = "from main import is_market_open\nfrom overnight_hold_check import check_overnight_hold_safety\nfrom zoneinfo import ZoneInfo\n"

if old_import not in content:
    print("Could not find import line -- no changes made.")
else:
    content = content.replace(old_import, new_import, 1)
    print("Added imports.")

    old_exit = '''        exit_reason = None
        if pct_change <= -stop_loss_pct:
            exit_reason = "stop_loss"
        elif pct_change >= take_profit_pct:
            exit_reason = "take_profit"
        elif approaching_expiry:
            exit_reason = "expiry_safety_net"'''

    new_exit = '''        ET = ZoneInfo("America/New_York")
        now_et = datetime.now(ET)
        near_close = now_et.hour == 15 and now_et.minute >= 30  # last 30 min of trading

        exit_reason = None
        if pct_change <= -stop_loss_pct:
            exit_reason = "stop_loss"
        elif pct_change >= take_profit_pct:
            exit_reason = "take_profit"
        elif approaching_expiry:
            exit_reason = "expiry_safety_net"
        elif near_close:
            overnight_check = check_overnight_hold_safety(pos["ticker"])
            if not overnight_check["safe"]:
                exit_reason = "overnight_risk -- " + "; ".join(overnight_check["reasons"])'''

    if old_exit not in content:
        print("Could not find exit-reason block -- no changes made to that part.")
    else:
        content = content.replace(old_exit, new_exit, 1)
        print("Wired overnight-hold check into exit-reason logic.")

    with open('options_exit_monitor.py', 'w', encoding='utf-8') as f:
        f.write(content)
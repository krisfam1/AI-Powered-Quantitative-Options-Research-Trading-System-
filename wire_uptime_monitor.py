content = open('daily_price_audit.py', encoding='utf-8').read()

old_func_def = '''def run_daily_price_audit() -> dict:
    """Audit all closed trades AND currently open positions against real Alpaca data."""
    _init_audit_log()
    mismatches = []'''

new_func_def = '''def run_daily_uptime_check() -> dict:
    """Check for real downtime gaps affecting any open or recently-closed position."""
    from automated_uptime_monitor import check_gaps_during_open_positions
    return check_gaps_during_open_positions()


def run_daily_price_audit() -> dict:
    """Audit all closed trades AND currently open positions against real Alpaca data."""
    _init_audit_log()
    mismatches = []'''

if old_func_def not in content:
    print("Could not find function def -- no changes made.")
else:
    content = content.replace(old_func_def, new_func_def, 1)
    print("Added run_daily_uptime_check function.")

    old_return = '    return {"trades_checked": trades_checked, "mismatches_found": len(mismatches), "details": mismatches}'
    new_return = '''    uptime_result = run_daily_uptime_check()
    if uptime_result["flagged_overlaps"]:
        for f in uptime_result["flagged_overlaps"]:
            mismatches.append("UPTIME WARNING: " + f["trade_id"] + " had a " + str(f["gap_minutes"]) + " min monitoring gap")

    return {"trades_checked": trades_checked, "mismatches_found": len(mismatches), "details": mismatches, "uptime_gaps_found": uptime_result["total_real_gaps"]}'''

    if old_return not in content:
        print("Could not find return statement -- no changes made to that part.")
    else:
        content = content.replace(old_return, new_return, 1)
        print("Wired uptime check into the automatic daily audit flow.")

    with open('daily_price_audit.py', 'w', encoding='utf-8') as f:
        f.write(content)
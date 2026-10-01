content = open('check_contract_peak.py', encoding='utf-8').read()

old_import = "from datetime import datetime, timezone\n"
new_import = "from datetime import datetime, timezone\nfrom zoneinfo import ZoneInfo\n"

if old_import not in content:
    print("Could not find import line -- no changes made.")
else:
    content = content.replace(old_import, new_import, 1)

    old_print = '''    peak_pct = (peak_price - entry_premium) / entry_premium * 100
    peak_dt = datetime.fromtimestamp(peak_time / 1000, tz=timezone.utc)

    print("PEAK price: $" + str(round(peak_price, 2)))
    print("Peak gain: " + str(round(peak_pct, 1)) + "%")
    print("Peak time (UTC): " + str(peak_dt))'''

    new_print = '''    peak_pct = (peak_price - entry_premium) / entry_premium * 100
    peak_dt_utc = datetime.fromtimestamp(peak_time / 1000, tz=timezone.utc)
    peak_dt_et = peak_dt_utc.astimezone(ZoneInfo("America/New_York"))

    print("Entry premium: $" + str(entry_premium))
    print("PEAK price: $" + str(round(peak_price, 2)))
    print("Peak gain: " + str(round(peak_pct, 1)) + "%")
    print("Peak time (ET): " + peak_dt_et.strftime("%Y-%m-%d %I:%M %p ET"))
    print("Peak time (UTC): " + str(peak_dt_utc))'''

    if old_print not in content:
        print("Could not find print block -- no changes made to that part.")
    else:
        content = content.replace(old_print, new_print, 1)
        print("Added ET time display and clearer output.")

    with open('check_contract_peak.py', 'w', encoding='utf-8') as f:
        f.write(content)
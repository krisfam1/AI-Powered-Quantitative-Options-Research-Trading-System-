import sqlite3

with sqlite3.connect("iv_correction_diagnostic.db") as conn:
    conn.row_factory = sqlite3.Row
    saved = conn.execute("SELECT * FROM diagnostic WHERE ticker='AMD' AND entry_date='2026-06-24'").fetchone()

print("SAVED (original) selection: contract identity via strike=" + str(saved["real_strike"]) + " expiration=" + str(saved["expiration"]) + " actual_dte=" + str(saved["actual_dte"]) + " historical_iv=" + str(saved["historical_iv"]))

with sqlite3.connect("v2_pricing_log.db") as conn:
    conn.row_factory = sqlite3.Row
    v2_row = conn.execute("SELECT * FROM v2_pricing_log WHERE ticker='AMD' AND signal_date='2026-06-24' ORDER BY id DESC LIMIT 1").fetchone()

if v2_row:
    print("\nV2 (fresh) selection: contract=" + str(v2_row["contract"]) + " real_strike=" + str(v2_row["real_strike"]) + " expiration=" + str(v2_row["expiration"]) + " actual_dte=" + str(v2_row["actual_dte"]) + " volatility_value=" + str(v2_row["volatility_value"]))
    same_contract = (v2_row["real_strike"] == saved["real_strike"]) and (v2_row["expiration"] == saved["expiration"])
    print("\nSame contract selected: " + str(same_contract))
else:
    print("\nNo V2 log entry found for this trade.")
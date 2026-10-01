import sqlite3

conn = sqlite3.connect('gex_data_cache.db')
cur = conn.cursor()

print("--- ticker_day_summary for TSLA 2026-09-08 ---")
cur.execute("SELECT * FROM ticker_day_summary WHERE ticker='TSLA' AND requested_date='2026-09-08'")
row = cur.fetchone()
cols = [d[0] for d in cur.description]
if row:
    for c, v in zip(cols, row):
        print(c, ":", v)
else:
    print("No summary row found at all.")

print("\n--- raw_records count for TSLA 2026-09-08 ---")
cur.execute("SELECT COUNT(*) FROM raw_records WHERE ticker='TSLA' AND requested_date='2026-09-08'")
print("Raw records:", cur.fetchone()[0])

print("\n--- sample raw record, if any ---")
cur.execute("SELECT record_id, id_suffix_date, matches_requested_date FROM raw_records WHERE ticker='TSLA' AND requested_date='2026-09-08' LIMIT 5")
for r in cur.fetchall():
    print(r)

conn.close()
import sqlite3

conn = sqlite3.connect('gex_data_cache.db')
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM ticker_day_summary")
total_ticker_days = cur.fetchone()[0]

cur.execute("SELECT SUM(records_retrieved), SUM(records_retained), SUM(records_excluded), SUM(contracts_retained), SUM(calls), SUM(puts), SUM(multi_record_contracts) FROM ticker_day_summary")
row = cur.fetchone()
total_retrieved, total_retained, total_excluded, total_contracts, total_calls, total_puts, total_multi = row

cur.execute("SELECT COUNT(*) FROM ticker_day_summary WHERE errors IS NOT NULL")
total_errors = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM ticker_day_summary WHERE pagination_complete = 0")
incomplete_pagination = cur.fetchone()[0]

cur.execute("SELECT ticker, COUNT(*) FROM ticker_day_summary GROUP BY ticker")
per_ticker = cur.fetchall()

print("=" * 80)
print("FINAL COMPLETE PHASE 1 AUDIT -- full 90-day dataset")
print("=" * 80)
print("Total ticker-days: " + str(total_ticker_days))
for ticker, count in per_ticker:
    print("  " + ticker + ": " + str(count) + " days")

print("\nTotal raw records retrieved: " + str(total_retrieved))
print("Records retained: " + str(total_retained) + " | Excluded: " + str(total_excluded))
print("Reconciliation: " + str(total_retained + total_excluded == total_retrieved))
print("Total contracts retained: " + str(total_contracts))
print("Calls: " + str(total_calls) + " | Puts: " + str(total_puts))
print("Multi-record contracts: " + str(total_multi))
print("Ticker-days with errors: " + str(total_errors))
print("Ticker-days with incomplete pagination: " + str(incomplete_pagination))

print("\n" + "=" * 80)
if total_errors == 0 and total_retained + total_excluded == total_retrieved and incomplete_pagination == 0:
    print("FINAL PHASE 1: PASS -- full dataset clean, ready for Phase 2 rebuild")
else:
    print("FINAL PHASE 1: issues remain")
print("=" * 80)

conn.close()
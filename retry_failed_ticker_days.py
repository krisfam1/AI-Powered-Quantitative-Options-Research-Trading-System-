from dotenv import load_dotenv
load_dotenv()

"""
Targeted retry for the 9 ticker-days that failed with network timeouts
during the full 378-ticker-day run. gex_data_loader.py's timeout has
been bumped from 30s to 60s (a real, permanent fix -- update that file
first). This script also adds a brief pause between requests to avoid
re-triggering whatever caused the clustered TSLA timeouts.

Does NOT reprocess the 369 ticker-days that already succeeded.
"""

import time
from gex_data_loader import process_ticker_day

FAILED_TICKER_DAYS = [
    ("TSLA", "2026-07-10"),
    ("TSLA", "2026-07-15"),
    ("TSLA", "2026-07-17"),
    ("TSLA", "2026-07-20"),
    ("TSLA", "2026-07-21"),
    ("TSLA", "2026-07-22"),
    ("TSLA", "2026-07-23"),
    ("TSLA", "2026-07-24"),
    ("AMD", "2026-06-17"),
]

print("=" * 80)
print("TARGETED RETRY -- " + str(len(FAILED_TICKER_DAYS)) + " previously-failed ticker-days")
print("=" * 80)

results = []
for ticker, date_str in FAILED_TICKER_DAYS:
    print("Retrying " + ticker + " " + date_str + "...")
    summary = process_ticker_day(ticker, date_str)
    results.append(summary)
    print("  retrieved=" + str(summary["records_retrieved"]) + " pages=" + str(summary["pages_requested"]) + " complete=" + str(summary["pagination_complete"]) + " contracts=" + str(summary["contracts_retained"]) + " errors=" + str(summary["errors"]))
    time.sleep(3)  # brief pause between requests to avoid re-triggering rate limiting

print("\n" + "=" * 80)
print("RETRY SUMMARY")
print("=" * 80)
still_failed = [r for r in results if r["errors"]]
now_succeeded = [r for r in results if not r["errors"]]
print("Now succeeded: " + str(len(now_succeeded)) + " / " + str(len(FAILED_TICKER_DAYS)))
print("Still failed: " + str(len(still_failed)))
for r in still_failed:
    print("  STILL FAILING: " + r["ticker"] + " " + r["date"] + " -- " + str(r["errors"]))

print("\n" + "=" * 80)
if len(still_failed) == 0:
    print("RETRY: ALL PASSED -- dataset now complete, safe to proceed to Phase 2 rebuild")
else:
    print("RETRY: " + str(len(still_failed)) + " ticker-day(s) still failing -- may need a longer pause or manual investigation")
print("=" * 80)
from dotenv import load_dotenv
load_dotenv()

import sqlite3
from datetime import datetime, timedelta

GAP_THRESHOLD_MINUTES = 10

with sqlite3.connect("uptime_log.db") as conn:
    cur = conn.cursor()
    cur.execute("SELECT service, timestamp FROM heartbeats ORDER BY timestamp ASC")
    rows = cur.fetchall()

print("Total heartbeats logged: " + str(len(rows)))
print("Checking for gaps > " + str(GAP_THRESHOLD_MINUTES) + " minutes...\n")

by_service = {}
for service, ts in rows:
    by_service.setdefault(service, []).append(datetime.fromisoformat(ts))

for service, timestamps in by_service.items():
    print("=" * 60)
    print(service + " (" + str(len(timestamps)) + " heartbeats, " + str(timestamps[0].date()) + " to " + str(timestamps[-1].date()) + ")")
    print("=" * 60)

    gaps_found = 0
    for i in range(1, len(timestamps)):
        gap = (timestamps[i] - timestamps[i-1]).total_seconds() / 60
        if gap > GAP_THRESHOLD_MINUTES:
            gaps_found += 1
            print("  GAP: " + str(timestamps[i-1]) + " -> " + str(timestamps[i]) + " (" + str(round(gap, 1)) + " min)")

    if gaps_found == 0:
        print("  No gaps found -- continuous uptime.")
    else:
        print("\n  Total gaps found: " + str(gaps_found))
    print("")
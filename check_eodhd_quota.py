"""
check_eodhd_quota.py

Step 1 of resuming the 59-ticker backfill: a single, cheap, real API call
to confirm the EODHD UnicornBay quota has actually reset -- don't just
trust the calculated ~24h window.

Usage:
    python check_eodhd_quota.py

Set your EODHD API token either as an environment variable:
    export EODHD_API_TOKEN=your_token_here
or by editing API_TOKEN below directly.

This makes exactly ONE lightweight request (end-of-day quote for a single
ticker, one day). If you see "QUOTA OK", you're clear to resume the
backfill with eodhd_quota_safe.py wired in. If you see "STILL BLOCKED",
wait longer and re-run this script again later -- do not resume the full
backfill script until this prints QUOTA OK.
"""

# Added, not in the original pasted file: this project's every other script
# loads the real token via dotenv rather than a bare shell env var -- without
# this the script would always print "EODHD_API_TOKEN not set" on this machine.
from dotenv import load_dotenv
load_dotenv()

import os
import sys
import requests

API_TOKEN = os.environ.get("EODHD_API_TOKEN", "")

# Cheapest possible real call: one day of EOD data for one liquid ticker.
TEST_URL = "https://eodhd.com/api/eod/AAPL.US"
TEST_PARAMS = {
    "api_token": API_TOKEN,
    "fmt": "json",
    "period": "d",
    "from": "2026-09-01",
    "to": "2026-09-02",
}


def main() -> int:
    if not API_TOKEN:
        print("ERROR: EODHD_API_TOKEN not set. Export it or edit API_TOKEN in this file.")
        return 2

    try:
        resp = requests.get(TEST_URL, params=TEST_PARAMS, timeout=15)
    except requests.RequestException as e:
        print(f"ERROR: request failed before getting an HTTP response: {e}")
        return 2

    if resp.status_code == 200:
        print("QUOTA OK -- got a real 200 response. Safe to resume the backfill.")
        print(f"  Sample response (truncated): {resp.text[:200]}")
        return 0
    elif resp.status_code == 429:
        print("STILL BLOCKED -- got HTTP 429 (quota exceeded).")
        print("  Do not resume the full backfill yet. Wait and re-run this check.")
        return 1
    else:
        print(f"UNEXPECTED STATUS: {resp.status_code}")
        print(f"  Body (truncated): {resp.text[:300]}")
        print("  Treat this as NOT confirmed -- investigate before resuming the backfill.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

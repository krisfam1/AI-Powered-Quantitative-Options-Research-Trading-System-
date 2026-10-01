import sys, os, time, json
from datetime import datetime, timezone, timedelta
sys.path.insert(0, r"C:\Users\fmkri\Downloads\Python-Backend\Python-Backend")
os.chdir(r"C:\Users\fmkri\Downloads\Python-Backend\Python-Backend")
from dotenv import load_dotenv
load_dotenv()
import requests

# Same endpoint and filters as gex_data_loader._fetch_raw_chain_paginated()
# (the backfill's real UnicornBay call), but page[limit]=1 and exactly ONE
# request (no pagination): the probe only needs a real 200/429 answer, not
# the ~545-record chain. Changed 2026-10-01 (CLAUDE.md Section 60).
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
TICKER, DATE_STR = "AAPL", "2025-08-26"
obs_date = datetime.strptime(DATE_STR, "%Y-%m-%d").date()
params = {
    "filter[underlying_symbol]": TICKER,
    "filter[tradetime_from]": DATE_STR,
    "filter[tradetime_to]": DATE_STR,
    "filter[exp_date_from]": obs_date.isoformat(),
    "filter[exp_date_to]": (obs_date + timedelta(days=45)).isoformat(),
    "api_token": os.environ.get("EODHD_API_TOKEN"),
    "page[limit]": 1,
    "page[offset]": 0,
}

now = datetime.now(timezone.utc)
t0 = time.time()
resp = None
try:
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    status = f"SUCCESS n_records={len(resp.json().get('data', []))} pages=1"
except Exception as e:
    status = f"FAILED {type(e).__name__}: {str(e)[:150]}"
elapsed = time.time() - t0

result = {"utc_time": now.isoformat(), "status": status, "elapsed_s": round(elapsed, 2)}
print(json.dumps(result))
if resp is not None:
    print(f"request: {resp.url.replace(params['api_token'] or '', 'REDACTED')} -> HTTP {resp.status_code}")

with open("eodhd_quota_probe_log.jsonl", "a") as f:
    f.write(json.dumps(result) + "\n")

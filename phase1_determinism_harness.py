from dotenv import load_dotenv
load_dotenv()

"""
PHASE 1 -- Deterministic-test harness for the ORIGINAL backtest engine.

Uses a FIXED, hardcoded date range (not datetime.now()) to isolate
whether non-determinism exists independent of real-time window drift.
Run this script 5 SEPARATE times (5 fresh `python` invocations) and
compare the outputs.

Captures everything Phase 1 requires: trade count, ordered entry/exit
lists, Python/package versions, full config, input-data checksum,
cache state before/after.
"""

import sys
import hashlib
import platform
import importlib.metadata
import sqlite3
import os
from datetime import datetime, timezone

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKER = "AAPL"

print("=" * 90)
print("PHASE 1 DIAGNOSTIC RUN -- " + datetime.now(timezone.utc).isoformat())
print("=" * 90)

print("\n--- ENVIRONMENT ---")
print("Python version: " + sys.version)
print("Platform: " + platform.platform())
for pkg in ["numpy", "scipy", "pandas", "requests"]:
    try:
        print(pkg + " version: " + importlib.metadata.version(pkg))
    except Exception:
        print(pkg + ": not installed or not found")

print("\n--- RELEVANT ENVIRONMENT VARIABLES ---")
for key in ["TZ", "PYTHONHASHSEED"]:
    print(key + "=" + str(os.environ.get(key, "NOT SET")))

import backtest_engine as be
from options_backtest_engine import run_options_backtest, _volatility_series_cache

print("\n--- VOLATILITY CACHE STATE BEFORE RUN ---")
print("Cache size: " + str(len(_volatility_series_cache)))
print("Cache keys: " + str(list(_volatility_series_cache.keys())))

print("\n--- FIXED CONFIG ---")
config = {
    "ticker": TICKER, "start": FIXED_START.isoformat(), "end": FIXED_END.isoformat(),
    "dte_target": 14, "option_type": "call", "entry_mode": "weighted",
    "entry_score_threshold": 20, "target_delta": 0.30, "apply_spread_cost": True,
    "exit_mode": "reversal_guard",
}
print(config)

print("\n--- INPUT DATA CHECKSUM ---")
bars = be.get_historical_bars(TICKER, FIXED_START, FIXED_END)
bars_repr = "|".join(str(b.timestamp) + "," + str(b.close) for b in bars)
data_hash = hashlib.sha256(bars_repr.encode()).hexdigest()
print("Bars count: " + str(len(bars)))
print("Bars SHA256: " + data_hash)
if bars:
    print("First bar: " + str(bars[0].timestamp) + " close=" + str(bars[0].close))
    print("Last bar: " + str(bars[-1].timestamp) + " close=" + str(bars[-1].close))
else:
    print("NO BARS RETURNED")

print("\n--- RUNNING BACKTEST ---")
result = run_options_backtest(
    TICKER, FIXED_START, FIXED_END, dte_target=14, option_type="call",
    entry_mode="weighted", entry_score_threshold=20, target_delta=0.30,
    apply_spread_cost=True, exit_mode="reversal_guard",
)

print("\n--- RESULTS ---")
print("Total trades: " + str(result.get("total_trades")))
trades = result.get("trades", [])
entry_list = sorted(str(t["entry_date"]) for t in trades)
print("Ordered entry dates: " + str(entry_list))

print("\n--- VOLATILITY CACHE STATE AFTER RUN ---")
print("Cache size: " + str(len(_volatility_series_cache)))
print("Cache keys: " + str(list(_volatility_series_cache.keys())))

print("\n--- DATABASE STATE (options_trades.db, if present) ---")
try:
    with sqlite3.connect("options_trades.db") as conn:
        count = conn.execute("SELECT COUNT(*) FROM options_trades").fetchone()[0]
        print("options_trades row count: " + str(count))
except Exception as e:
    print("Could not check options_trades.db: " + str(e))

print("\nPHASE 1 RUN COMPLETE. Record this ENTIRE output and re-run this exact script in a fresh process 4 more times.")
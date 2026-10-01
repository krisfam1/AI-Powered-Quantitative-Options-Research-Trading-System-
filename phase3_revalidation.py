from dotenv import load_dotenv
load_dotenv()

"""
Phase 3 revalidation against the full, expanded 90-day GEX dataset
(372 ticker-days). Reuses gex_lookup.py's get_gex_for_signal() --
no changes to the lookup logic itself, just comprehensive re-testing
at the new scale, including two REAL market holidays that now fall
within our actual date range:

- Juneteenth (Friday, 2026-06-19) -- confirmed excluded from the real
  trading-day list (jumps 06-18 -> 06-22). Test: Monday 2026-06-22
  signal should resolve T-1 to Thursday 2026-06-18, not Friday.
- Labor Day (Monday, 2026-09-07) -- test: Tuesday 2026-09-08 signal
  should resolve T-1 to Friday 2026-09-04, not the Monday holiday.
"""

import sqlite3
from datetime import datetime
from gex_lookup import get_gex_for_signal
from gex_data_loader import DB_PATH

TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]

named_tests = []

print("=" * 80)
print("NAMED HOLIDAY/CALENDAR TESTS")
print("=" * 80)

# Juneteenth: Monday after a Friday holiday
result = get_gex_for_signal("AAPL", datetime(2026, 6, 22, 10, 30))
expected = "2026-06-18"
passed = result.get("gex_snapshot_date") == expected
named_tests.append(passed)
print("Juneteenth test (Mon 6/22 -> expect Thu 6/18): got=" + str(result.get("gex_snapshot_date")) + " PASS=" + str(passed))

# Labor Day: Tuesday after a Monday holiday
result = get_gex_for_signal("AAPL", datetime(2026, 9, 8, 10, 30))
expected = "2026-09-04"
passed = result.get("gex_snapshot_date") == expected
named_tests.append(passed)
print("Labor Day test (Tue 9/8 -> expect Fri 9/4): got=" + str(result.get("gex_snapshot_date")) + " PASS=" + str(passed))

# Friday -> Thursday (generic)
result = get_gex_for_signal("TSLA", datetime(2026, 7, 24, 14, 0))
expected = "2026-07-23"
passed = result.get("gex_snapshot_date") == expected
named_tests.append(passed)
print("Friday -> Thursday (TSLA 7/24 -> expect 7/23): got=" + str(result.get("gex_snapshot_date")) + " PASS=" + str(passed))

# Monday -> Friday (generic, non-holiday)
result = get_gex_for_signal("NVDA", datetime(2026, 6, 29, 10, 0))
expected = "2026-06-26"
passed = result.get("gex_snapshot_date") == expected
named_tests.append(passed)
print("Monday -> Friday (NVDA 6/29 -> expect 6/26): got=" + str(result.get("gex_snapshot_date")) + " PASS=" + str(passed))

print("\n" + "=" * 80)
print("REPRESENTATIVE SWEEP -- all 6 tickers, dates across the full 90-day period")
print("=" * 80)

representative_dates = ["2026-06-15", "2026-07-01", "2026-07-15", "2026-08-01", "2026-08-15", "2026-09-01", "2026-09-08"]
sweep_results = []
for ticker in TICKERS:
    for date_str in representative_dates:
        signal_ts = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=14, minute=30)
        result = get_gex_for_signal(ticker, signal_ts)
        sweep_results.append(result)

total_tested = len(sweep_results)
available = [r for r in sweep_results if r.get("available")]
unavailable = [r for r in sweep_results if not r.get("available")]
violations = 0
for r in available:
    snap_date = datetime.strptime(r["gex_snapshot_date"], "%Y-%m-%d").date()
    sig_date = datetime.strptime(r["signal_date"], "%Y-%m-%d").date()
    if snap_date >= sig_date:
        violations += 1
        print("VIOLATION: " + r["ticker"] + " " + r["signal_date"] + " -> " + r["gex_snapshot_date"])

print("Ticker/date lookups tested: " + str(total_tested))
print("Successful (available) lookups: " + str(len(available)))
print("Unavailable lookups: " + str(len(unavailable)))
for r in unavailable:
    print("  UNAVAILABLE: " + r["ticker"] + " " + r["signal_date"] + " -- " + str(r.get("reason")))
print("No-lookahead violations: " + str(violations))

print("\n" + "=" * 80)
print("DETERMINISM CHECK")
print("=" * 80)
r1 = get_gex_for_signal("AAPL", datetime(2026, 7, 15, 10, 30))
r2 = get_gex_for_signal("AAPL", datetime(2026, 7, 15, 10, 30))
determinism_pass = r1 == r2
print("Repeated call identical: " + str(determinism_pass))

print("\n" + "=" * 80)
print("READ-ONLY CHECK")
print("=" * 80)
with sqlite3.connect(DB_PATH) as conn:
    before_snapshot = conn.execute("SELECT COUNT(*) FROM cleaned_snapshot").fetchone()[0]
    before_metrics = conn.execute("SELECT COUNT(*) FROM gex_metrics").fetchone()[0]
for ticker in TICKERS:
    get_gex_for_signal(ticker, datetime(2026, 8, 1, 10, 30))
with sqlite3.connect(DB_PATH) as conn:
    after_snapshot = conn.execute("SELECT COUNT(*) FROM cleaned_snapshot").fetchone()[0]
    after_metrics = conn.execute("SELECT COUNT(*) FROM gex_metrics").fetchone()[0]
read_only_pass = (before_snapshot == after_snapshot) and (before_metrics == after_metrics)
print("Row counts unchanged after multiple lookups: " + str(read_only_pass))

print("\n" + "=" * 80)
print("METHOD B AND METRICS SANITY CHECK ON A FEW REAL LOOKUPS")
print("=" * 80)
for r in available[:3]:
    print(r["ticker"] + " " + r["signal_date"] + " (T-1=" + r["gex_snapshot_date"] + "):")
    print("  gamma_flip_distance_pct=" + str(r.get("gamma_flip_distance_pct")) + " gex_regime=" + str(r.get("gex_regime")) + " is_regime_testable=" + str(r.get("is_regime_testable")))

print("\n" + "=" * 80)
all_named_passed = all(named_tests)
overall_pass = all_named_passed and (violations == 0) and determinism_pass and read_only_pass
print("PHASE 3 REVALIDATION: " + ("PASS" if overall_pass else "FAIL"))
print("=" * 80)
print("Named tests passed: " + str(sum(named_tests)) + "/" + str(len(named_tests)))
print("Sweep: " + str(len(available)) + "/" + str(total_tested) + " available, " + str(violations) + " violations")
print("Determinism: " + str(determinism_pass) + " | Read-only: " + str(read_only_pass))
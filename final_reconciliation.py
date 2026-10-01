from dotenv import load_dotenv
load_dotenv()

"""
Final controlled reconciliation, post cache-isolation fix. Uses the
SAME fixed date range as the Phase 1 determinism harness. Runs both
engines in the SAME process (the strictest test of isolation -- if the
fix didn't work, this would still show cache-sharing). Compares full
trade details, not just counts.
"""

from datetime import datetime, timezone
from options_backtest_engine import run_options_backtest, _volatility_series_cache
from portfolio_backtest import run_portfolio_backtest

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)

print("Cache size before any calls: " + str(len(_volatility_series_cache)))

print("\n--- Running ORIGINAL engine ---")
original_result = run_options_backtest(
    "AAPL", FIXED_START, FIXED_END, dte_target=14, option_type="call",
    entry_mode="weighted", entry_score_threshold=20, target_delta=0.30,
    apply_spread_cost=True, exit_mode="reversal_guard",
)
print("Cache size after original engine: " + str(len(_volatility_series_cache)))

print("\n--- Running PORTFOLIO engine ---")
portfolio_result = run_portfolio_backtest(["AAPL"], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call")
print("Cache size after portfolio engine: " + str(len(_volatility_series_cache)))

print("\n" + "=" * 90)
print("CACHE ISOLATION CHECK")
print("=" * 90)
print("Cache keys: " + str(list(_volatility_series_cache.keys())))
namespaces = set(k[0] for k in _volatility_series_cache.keys())
print("Distinct namespaces found: " + str(namespaces))
print("Isolation confirmed (2 separate entries expected): " + str(len(_volatility_series_cache) == 2))

print("\n" + "=" * 90)
print("TRADE COUNT COMPARISON")
print("=" * 90)
print("Original engine: " + str(original_result["total_trades"]) + " trades")
print("Portfolio engine: " + str(portfolio_result["total_trades"]) + " trades")

print("\n" + "=" * 90)
print("FULL TRADE-DETAIL COMPARISON")
print("=" * 90)

orig_trades = sorted(original_result["trades"], key=lambda t: str(t["entry_date"]))
port_trades = sorted(portfolio_result["closed_trades"], key=lambda t: str(t["entry_date"]))

print("\n--- ORIGINAL ENGINE TRADES ---")
for t in orig_trades:
    print(str(t["entry_date"]) + " -> " + str(t["exit_date"]) + " | " + t["option_type"] + " strike=" + str(t["strike"]) + " entry=$" + str(round(t["entry_premium"],3)) + " exit=$" + str(round(t["exit_premium"],3)) + " reason=" + t["exit_reason"])

print("\n--- PORTFOLIO ENGINE TRADES ---")
for t in port_trades:
    print(str(t["entry_date"]) + " -> " + str(t["exit_date"]) + " | " + t["option_type"] + " strike=" + str(t["strike"]) + " entry=$" + str(round(t["entry_premium"],3)) + " exit=$" + str(round(t["exit_premium"],3)) + " reason=" + t["exit_reason"])

print("\n" + "=" * 90)
print("FIELD-BY-FIELD MATCH CHECK")
print("=" * 90)
if len(orig_trades) != len(port_trades):
    print("MISMATCH: different trade counts (" + str(len(orig_trades)) + " vs " + str(len(port_trades)) + ") -- cannot do 1:1 comparison")
else:
    all_match = True
    for i, (o, p) in enumerate(zip(orig_trades, port_trades)):
        mismatches = []
        if str(o["entry_date"]) != str(p["entry_date"]):
            mismatches.append("entry_date")
        if str(o["exit_date"]) != str(p["exit_date"]):
            mismatches.append("exit_date")
        if o["option_type"] != p["option_type"]:
            mismatches.append("option_type")
        if o["strike"] != p["strike"]:
            mismatches.append("strike")
        if abs(o["entry_premium"] - p["entry_premium"]) > 0.01:
            mismatches.append("entry_premium")
        if abs(o["exit_premium"] - p["exit_premium"]) > 0.01:
            mismatches.append("exit_premium")
        if o["exit_reason"] != p["exit_reason"]:
            mismatches.append("exit_reason")
        if mismatches:
            all_match = False
            print("Trade " + str(i) + " MISMATCH in: " + str(mismatches))
    print("\nAll fields match across all trades: " + str(all_match))
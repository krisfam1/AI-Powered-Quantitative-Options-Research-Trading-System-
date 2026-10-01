from dotenv import load_dotenv
load_dotenv()

"""
Phase 7, Steps 1-3 ONLY. No new EODHD calls. Frozen V1 methodology
exactly as-is. New dedicated database -- no existing databases touched.
"""

import sqlite3
import statistics
import json
from datetime import datetime, timezone
from collections import defaultdict
from portfolio_backtest import run_portfolio_backtest
from options_pricing import black_scholes_price, calculate_delta
from options_backtest_engine import _estimated_spread_cost_pct

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
FROZEN_BASELINE_PNL = 20427.64
FROZEN_BASELINE_TRADES = 251
DB_PATH = "phase7_attribution.db"

print("=" * 100)
print("STEP 1a: REPRODUCE FROZEN BASELINE -- MUST MATCH EXACTLY")
print("=" * 100)
v1_results = {}
for ticker in TICKERS:
    v1_results[ticker] = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v1")

all_trades = [t for tk in TICKERS for t in v1_results[tk]["closed_trades"]]
total_pnl = sum(t["pnl_dollars"] for t in all_trades)
total_n = len(all_trades)

print("Reproduced total P&L: $" + str(round(total_pnl, 2)) + " (frozen baseline: $" + str(FROZEN_BASELINE_PNL) + ")")
print("Reproduced trade count: " + str(total_n) + " (frozen baseline: " + str(FROZEN_BASELINE_TRADES) + ")")

pnl_match = abs(total_pnl - FROZEN_BASELINE_PNL) < 0.01
count_match = total_n == FROZEN_BASELINE_TRADES

if not (pnl_match and count_match):
    print("\n*** DISCREPANCY DETECTED -- STOPPING PER INSTRUCTION, NOT PROCEEDING TO ATTRIBUTION ***")
    print("P&L match: " + str(pnl_match) + " | Count match: " + str(count_match))
    print("Difference: $" + str(round(total_pnl - FROZEN_BASELINE_PNL, 2)) + " | Count diff: " + str(total_n - FROZEN_BASELINE_TRADES))
    exit()

print("\nEXACT REPRODUCTION CONFIRMED. Proceeding.")

print("\n" + "=" * 100)
print("STEP 1b: RECONSTRUCT UNDERLYING PRICES (back-solve) AND VALIDATE AGAINST GROUND TRUTH")
print("=" * 100)

def solve_spot_from_price(target_price, strike, dte, vol, option_type="call", risk_free_rate=0.04):
    low, high = 1.0, 5000.0
    for _ in range(100):
        mid = (low + high) / 2
        price = black_scholes_price(mid, strike, dte, vol, risk_free_rate, option_type)
        if price < target_price:
            low = mid
        else:
            high = mid
        if abs(high - low) < 0.001:
            break
    return (low + high) / 2

BRACKETS = [(5.0, 0.02), (2.0, 0.04), (1.0, 0.07), (0.0, 0.12)]
def recover_raw_price(saved_price):
    for threshold, spread_pct in BRACKETS:
        multiplier = 1 + spread_pct / 2
        candidate_raw = saved_price / multiplier
        if candidate_raw >= threshold:
            return candidate_raw
    return saved_price / 1.06

# Match each trade to its ground-truth log entry via (ticker, entry_date, strike)
validation_rows = []
for ticker in TICKERS:
    ground_truth = {(g["ticker"], g["entry_date"], round(g["strike"],2)): g for g in v1_results[ticker]["v1_ground_truth_log"]}
    for t in v1_results[ticker]["closed_trades"]:
        key = (ticker, t["entry_date"], round(t["strike"],2))
        gt = ground_truth.get(key)
        if gt is None:
            continue
        dte_target = 14
        raw_price = recover_raw_price(t["entry_premium"])
        reconstructed_spot = solve_spot_from_price(raw_price, t["strike"], dte_target, gt["v1_realized_vol"])
        actual_spot = gt["underlying_price"]
        abs_diff = abs(reconstructed_spot - actual_spot)
        pct_diff = abs_diff / actual_spot * 100
        validation_rows.append({"ticker": ticker, "date": str(t["entry_date"]), "reconstructed": reconstructed_spot, "actual": actual_spot, "abs_diff": abs_diff, "pct_diff": pct_diff})

print("Validation sample size: " + str(len(validation_rows)) + " (full population, not just a sample)")
pct_diffs = [r["pct_diff"] for r in validation_rows]
abs_diffs = [r["abs_diff"] for r in validation_rows]
print("Median pct diff: " + str(round(statistics.median(pct_diffs), 4)) + "%")
print("Mean pct diff: " + str(round(statistics.mean(pct_diffs), 4)) + "%")
print("Max pct diff: " + str(round(max(pct_diffs), 4)) + "%")
near_exact = len([d for d in pct_diffs if d < 0.5])
print("Near-exact matches (<0.5% diff): " + str(near_exact) + " / " + str(len(validation_rows)) + " (" + str(round(near_exact/len(validation_rows)*100,1)) + "%)")

print("\nSample validation rows (first 10):")
for r in validation_rows[:10]:
    print("  " + r["ticker"] + " " + r["date"] + ": reconstructed=$" + str(round(r["reconstructed"],2)) + " actual=$" + str(round(r["actual"],2)) + " diff=" + str(round(r["pct_diff"],3)) + "%")

median_pct_diff = statistics.median(pct_diffs)
RECONSTRUCTION_VALID = median_pct_diff < 1.0  # tolerance threshold, stated before proceeding

print("\nRECONSTRUCTION VALIDATION: " + ("PASS -- proceeding with attribution using reconstructed prices" if RECONSTRUCTION_VALID else "FAIL -- median error exceeds 1% tolerance, STOPPING per instruction"))

if not RECONSTRUCTION_VALID:
    exit()

print("\nPHASE 7 STEPS 1a-1b COMPLETE. Proceeding to attribution analyses.")
# ============================================================
# BUILD FULL RECONSTRUCTED TRADE DATASET
# ============================================================
full_trades = []
for ticker in TICKERS:
    ground_truth = {(g["ticker"], g["entry_date"], round(g["strike"],2)): g for g in v1_results[ticker]["v1_ground_truth_log"]}
    for t in v1_results[ticker]["closed_trades"]:
        key = (ticker, t["entry_date"], round(t["strike"],2))
        gt = ground_truth.get(key)
        if gt is None:
            continue
        raw_price = recover_raw_price(t["entry_premium"])
        entry_spot = solve_spot_from_price(raw_price, t["strike"], 14, gt["v1_realized_vol"])
        holding_days = (t["exit_date"] - t["entry_date"]).days
        # exit underlying: back-solve similarly using exit_premium (unadjusted, since exit has no spread applied per code review)
        exit_dte = max((t["expiry_date"] - t["exit_date"]).days, 0)
        try:
            exit_spot = solve_spot_from_price(t["exit_premium"], t["strike"], exit_dte, gt["v1_realized_vol"]) if exit_dte > 0 else None
        except Exception:
            exit_spot = None
        underlying_return = ((exit_spot - entry_spot) / entry_spot) if exit_spot else None
        option_return = t["pnl_pct"] / 100
        delta_entry = None
        try:
            delta_entry = calculate_delta(entry_spot, t["strike"], 14, gt["v1_realized_vol"], option_type="call")
        except Exception:
            pass

        full_trades.append({
            **t, "underlying_entry": entry_spot, "underlying_exit": exit_spot,
            "underlying_return": underlying_return, "option_return": option_return,
            "holding_days": holding_days, "delta_entry": delta_entry, "realized_vol": gt["v1_realized_vol"],
        })

print("\n" + "=" * 100)
print("ANALYSIS 2: EXIT ATTRIBUTION")
print("=" * 100)
by_reason = defaultdict(list)
for t in full_trades:
    by_reason[t["exit_reason"]].append(t)
for reason, trades in by_reason.items():
    n = len(trades)
    wins = len([t for t in trades if t["pnl_dollars"] > 0])
    total = sum(t["pnl_dollars"] for t in trades)
    gross_win = sum(t["pnl_dollars"] for t in trades if t["pnl_dollars"] > 0)
    gross_loss = abs(sum(t["pnl_dollars"] for t in trades if t["pnl_dollars"] < 0))
    pf = gross_win/gross_loss if gross_loss else None
    print(reason + ": n=" + str(n) + " win_rate=" + str(round(wins/n*100,1)) + "% total_pnl=$" + str(round(total,2)) + " mean=$" + str(round(total/n,2)) + " median=$" + str(round(statistics.median([t["pnl_dollars"] for t in trades]),2)) + " profit_factor=" + (str(round(pf,2)) if pf else "N/A") + " contribution=" + str(round(total/total_pnl*100,1)) + "%")

print("\n" + "=" * 100)
print("ANALYSIS 5: TICKER CONCENTRATION")
print("=" * 100)
by_ticker = defaultdict(list)
for t in full_trades:
    by_ticker[t["ticker"]].append(t)
ticker_pnls = {}
for tk in TICKERS:
    trades = by_ticker[tk]
    if not trades:
        continue
    n = len(trades)
    total = sum(t["pnl_dollars"] for t in trades)
    ticker_pnls[tk] = total
    wins = len([t for t in trades if t["pnl_dollars"]>0])
    best = max(trades, key=lambda t: t["pnl_dollars"])
    worst = min(trades, key=lambda t: t["pnl_dollars"])
    print(tk + ": n=" + str(n) + " win_rate=" + str(round(wins/n*100,1)) + "% total=$" + str(round(total,2)) + " mean=$" + str(round(total/n,2)) + " contribution=" + str(round(total/total_pnl*100,1)) + "% best=$" + str(round(best["pnl_dollars"],2)) + " worst=$" + str(round(worst["pnl_dollars"],2)))

sorted_tickers = sorted(ticker_pnls.items(), key=lambda x: -x[1])
excl_top1 = total_pnl - sorted_tickers[0][1]
excl_top2 = total_pnl - sorted_tickers[0][1] - sorted_tickers[1][1]
print("\nExcluding top ticker (" + sorted_tickers[0][0] + "): $" + str(round(excl_top1,2)))
print("Excluding top 2 tickers: $" + str(round(excl_top2,2)))
top5_trades = sorted(full_trades, key=lambda t: -t["pnl_dollars"])[:5]
excl_top5 = total_pnl - sum(t["pnl_dollars"] for t in top5_trades)
print("Excluding top 5 individual trades: $" + str(round(excl_top5,2)))

print("\n" + "=" * 100)
print("ANALYSIS 6: POSITION SIZING ATTRIBUTION")
print("=" * 100)
equal_weight_pnl = sum(t["pnl_pct"]/100 * 1000 for t in full_trades)  # normalize: $1000 notional per trade
print("Actual position-sized total P&L: $" + str(round(total_pnl,2)))
print("Equal-$1000-per-trade normalized P&L: $" + str(round(equal_weight_pnl,2)))
print("Difference attributable to position sizing: $" + str(round(total_pnl - equal_weight_pnl,2)))
cheap_trades = [t for t in full_trades if t["entry_premium"] < 2.0]
expensive_trades = [t for t in full_trades if t["entry_premium"] >= 2.0]
if cheap_trades and expensive_trades:
    print("Cheap options (<$2) avg contracts: " + str(round(statistics.mean([t["contracts"] for t in cheap_trades]),2)))
    print("Expensive options (>=$2) avg contracts: " + str(round(statistics.mean([t["contracts"] for t in expensive_trades]),2)))

print("\n" + "=" * 100)
print("ANALYSIS 7: HOLDING PERIOD")
print("=" * 100)
buckets = [(0,0,"same day"), (1,1,"1 day"), (2,3,"2-3 days"), (4,5,"4-5 days"), (6,10,"6-10 days"), (11,999,">10 days")]
for lo, hi, label in buckets:
    bucket_trades = [t for t in full_trades if lo <= t["holding_days"] <= hi]
    if not bucket_trades:
        continue
    n = len(bucket_trades)
    wins = len([t for t in bucket_trades if t["pnl_dollars"]>0])
    total = sum(t["pnl_dollars"] for t in bucket_trades)
    print(label + ": n=" + str(n) + " win_rate=" + str(round(wins/n*100,1)) + "% total_pnl=$" + str(round(total,2)))

print("\n" + "=" * 100)
print("ANALYSIS 3: UNDERLYING VS OPTION RETURN (association, not causal claim)")
print("=" * 100)
paired = [(t["underlying_return"], t["option_return"]) for t in full_trades if t["underlying_return"] is not None]
if len(paired) > 2:
    und_rets = [p[0] for p in paired]
    opt_rets = [p[1] for p in paired]
    try:
        corr = statistics.correlation(und_rets, opt_rets)
        print("Correlation (underlying return, option return): " + str(round(corr,3)) + " (n=" + str(len(paired)) + ")")
    except Exception as e:
        print("Correlation calc failed: " + str(e))
    avg_leverage = statistics.mean([abs(o)/abs(u) for u,o in paired if abs(u) > 0.001])
    print("Average |option_return| / |underlying_return| ratio (leverage/convexity indicator): " + str(round(avg_leverage,2)) + "x")
    print("NOTE: this demonstrates association/leverage magnitude, NOT causal attribution of P&L to any single mechanism.")

print("\nPHASE 7 STEPS 1-3 FULL ATTRIBUTION COMPLETE.")
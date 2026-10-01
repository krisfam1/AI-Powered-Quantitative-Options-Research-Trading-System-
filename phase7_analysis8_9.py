from dotenv import load_dotenv
load_dotenv()

"""
Phase 7, Analyses 8 & 9 (MAE/MFE, path behavior, exit-rule diagnostics)
plus the dedicated 5-trade concentration investigation. Bar-by-bar
reconstruction uses the EXACT frozen V1 formula (calculate_historical_volatility
+ black_scholes_price) against REAL Alpaca bars -- an exact replay,
not an approximation. No future information used to alter any
historical trade; retrospective diagnostics only.
"""

import statistics
from datetime import datetime, timezone
from collections import defaultdict
import backtest_engine as be
from portfolio_backtest import run_portfolio_backtest
from options_backtest_engine import calculate_historical_volatility, black_scholes_price

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]

print("Reproducing frozen V1 baseline (must match: $20,427.64, 251 trades)...\n")
v1_results = {}
all_bars = {}
for ticker in TICKERS:
    v1_results[ticker] = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v1")
    all_bars[ticker] = be.get_historical_bars(ticker, FIXED_START, FIXED_END)

all_trades_raw = [t for tk in TICKERS for t in v1_results[tk]["closed_trades"]]
total_pnl = sum(t["pnl_dollars"] for t in all_trades_raw)
print("Reproduced: $" + str(round(total_pnl,2)) + ", n=" + str(len(all_trades_raw)))
if abs(total_pnl - 20427.64) > 0.01 or len(all_trades_raw) != 251:
    print("*** DISCREPANCY -- STOPPING ***")
    exit()
print("Reproduction confirmed.\n")

# Build ground-truth-matched, index-enriched trade list
enriched_trades = []
for ticker in TICKERS:
    ground_truth = {(g["ticker"], g["entry_date"], round(g["strike"],2)): g for g in v1_results[ticker]["v1_ground_truth_log"]}
    for t in v1_results[ticker]["closed_trades"]:
        key = (ticker, t["entry_date"], round(t["strike"],2))
        gt = ground_truth.get(key)
        if gt is None:
            continue
        enriched_trades.append({**t, "entry_index": gt["entry_index"], "ticker": ticker})

print("Enriched trades with entry_index: " + str(len(enriched_trades)) + "\n")

print("Reconstructing bar-by-bar mark-to-market path for every trade (exact frozen V1 formula)...")
for t in enriched_trades:
    ticker = t["ticker"]
    bars = all_bars[ticker]
    entry_idx = t["entry_index"]
    expiry_date = t["expiry_date"]
    entry_premium = t["entry_premium"]

    path = []
    idx = entry_idx
    while idx < len(bars):
        bar = bars[idx]
        bar_date = bar.timestamp.date()
        if bar_date > t["exit_date"]:
            break
        days_left = (expiry_date - bar_date).days
        vol = calculate_historical_volatility(bars, idx, cache_namespace="phase7_replay")
        current_price = float(bar.close)
        option_value = black_scholes_price(current_price, t["strike"], max(days_left,0), vol, option_type="call")
        pct_change = (option_value - entry_premium) / entry_premium if entry_premium else 0
        path.append({"idx": idx, "bars_since_entry": idx - entry_idx, "option_value": option_value, "pct_change": pct_change})
        idx += 1
        if bar_date >= t["exit_date"] and idx < len(bars) and bars[idx].timestamp.date() > t["exit_date"]:
            break

    t["path"] = path
    if path:
        mfe_point = max(path, key=lambda p: p["pct_change"])
        mae_point = min(path, key=lambda p: p["pct_change"])
        t["mfe_pct"] = mfe_point["pct_change"]
        t["mfe_bars"] = mfe_point["bars_since_entry"]
        t["mae_pct"] = mae_point["pct_change"]
        t["mae_bars"] = mae_point["bars_since_entry"]
        t["reached_plus20"] = any(p["pct_change"] >= 0.20 for p in path)
        t["reached_plus40"] = any(p["pct_change"] >= 0.40 for p in path)
        t["reached_minus20"] = any(p["pct_change"] <= -0.20 for p in path)
        first_plus40 = next((p for p in path if p["pct_change"] >= 0.40), None)
        t["first_plus40_bars"] = first_plus40["bars_since_entry"] if first_plus40 else None
        for h in [1,5,10,20]:
            hp = next((p for p in path if p["bars_since_entry"] == h), None)
            t["ret_at_" + str(h) + "bar"] = hp["pct_change"] if hp else None

print("Reconstruction complete for " + str(len(enriched_trades)) + " trades.\n")

print("=" * 100)
print("ANALYSIS 8: MAE / MFE")
print("=" * 100)
mfes = [t["mfe_pct"] for t in enriched_trades if "mfe_pct" in t]
maes = [t["mae_pct"] for t in enriched_trades if "mae_pct" in t]
print("MFE: median=" + str(round(statistics.median(mfes)*100,2)) + "% mean=" + str(round(statistics.mean(mfes)*100,2)) + "% max=" + str(round(max(mfes)*100,2)) + "%")
print("MAE: median=" + str(round(statistics.median(maes)*100,2)) + "% mean=" + str(round(statistics.mean(maes)*100,2)) + "% min=" + str(round(min(maes)*100,2)) + "%")

by_reason_mfe = defaultdict(list)
by_reason_mae = defaultdict(list)
for t in enriched_trades:
    by_reason_mfe[t["exit_reason"]].append(t.get("mfe_pct"))
    by_reason_mae[t["exit_reason"]].append(t.get("mae_pct"))
for reason in by_reason_mfe:
    print(reason + ": median_MFE=" + str(round(statistics.median(by_reason_mfe[reason])*100,2)) + "% median_MAE=" + str(round(statistics.median(by_reason_mae[reason])*100,2)) + "%")

print("\n" + "=" * 100)
print("ANALYSIS 9: PATH BEHAVIOR / EXIT-RULE DIAGNOSTICS")
print("=" * 100)
reversal_trades = [t for t in enriched_trades if t["exit_reason"] == "reversal_guard"]
reversal_reached40_before = len([t for t in reversal_trades if t.get("reached_plus40")])
print("D1: Reversal-guard winners that reached +40% at some point: " + str(reversal_reached40_before) + " / " + str(len(reversal_trades)))

reached40_trades = [t for t in enriched_trades if t.get("reached_plus40")]
pnl_from_reached40 = sum(t["pnl_dollars"] for t in reached40_trades)
print("D2: Total P&L from trades that reached +40% at some point: $" + str(round(pnl_from_reached40,2)) + " (" + str(round(pnl_from_reached40/total_pnl*100,1)) + "% of total)")

stop_loss_trades = [t for t in enriched_trades if t["exit_reason"] == "stop_loss"]
sl_would_recover = len([t for t in stop_loss_trades if t.get("mfe_pct",0) > 0 and t["mfe_bars"] > t["mae_bars"]])
print("D3: Stop-loss trades where price action AFTER the eventual low showed some recovery (MFE after MAE): " + str(sl_would_recover) + " / " + str(len(stop_loss_trades)))

losing_trades = [t for t in enriched_trades if t["pnl_dollars"] < 0]
losers_with_early_favorable = len([t for t in losing_trades if t.get("mfe_pct",0) > 0.05])
print("D4: Losing trades with meaningful favorable excursion (MFE>5%) before eventual loss: " + str(losers_with_early_favorable) + " / " + str(len(losing_trades)))

large_mfe_trades = [t for t in enriched_trades if t.get("mfe_pct",0) > 0.40]
pnl_large_mfe = sum(t["pnl_dollars"] for t in large_mfe_trades)
print("D5: Total P&L from trades with unusually large MFE (>40%): $" + str(round(pnl_large_mfe,2)) + " (" + str(round(pnl_large_mfe/total_pnl*100,1)) + "% of total, n=" + str(len(large_mfe_trades)) + ")")

print("\n" + "=" * 100)
print("FIXED-HORIZON COUNTERFACTUALS")
print("=" * 100)
for h in [1,5,10,20]:
    vals = [t["ret_at_" + str(h) + "bar"] for t in enriched_trades if t.get("ret_at_" + str(h) + "bar") is not None]
    if vals:
        print(str(h) + "-bar: n=" + str(len(vals)) + " median=" + str(round(statistics.median(vals)*100,2)) + "% mean=" + str(round(statistics.mean(vals)*100,2)) + "%")

print("\n" + "=" * 100)
print("CONCENTRATION ANALYSIS -- TOP N CONTRIBUTION")
print("=" * 100)
sorted_by_pnl = sorted(enriched_trades, key=lambda t: -t["pnl_dollars"])
for n in [1,3,5,10,20]:
    top_n_sum = sum(t["pnl_dollars"] for t in sorted_by_pnl[:n])
    excl_pnl = total_pnl - top_n_sum
    print("Top " + str(n) + ": contributes $" + str(round(top_n_sum,2)) + " (" + str(round(top_n_sum/total_pnl*100,1)) + "%) | excluding: $" + str(round(excl_pnl,2)))

print("\n" + "=" * 100)
print("TOP-5 TRADE CHARACTERISTICS -- ORDINARY OR OUTLIER?")
print("=" * 100)
top5 = sorted_by_pnl[:5]
rest = sorted_by_pnl[5:]

def compare_stat(key, top_list, rest_list, fmt=lambda x: round(x,2)):
    top_vals = [t[key] for t in top_list if key in t and t[key] is not None]
    rest_vals = [t[key] for t in rest_list if key in t and t[key] is not None]
    if top_vals and rest_vals:
        print("  " + key + ": top5_median=" + str(fmt(statistics.median(top_vals))) + " rest_median=" + str(fmt(statistics.median(rest_vals))))

print("Top 5 trades:")
for t in top5:
    holding = (t["exit_date"]-t["entry_date"]).days
    print("  " + t["ticker"] + " " + str(t["entry_date"]) + " pnl=$" + str(round(t["pnl_dollars"],2)) + " holding=" + str(holding) + "d mfe=" + str(round(t.get("mfe_pct",0)*100,1)) + "% exit_reason=" + t["exit_reason"])

print("\nComparison (top 5 vs remaining 246):")
top5_holding = [(t["exit_date"]-t["entry_date"]).days for t in top5]
rest_holding = [(t["exit_date"]-t["entry_date"]).days for t in rest]
print("  holding_days: top5_median=" + str(statistics.median(top5_holding)) + " rest_median=" + str(statistics.median(rest_holding)))
compare_stat("mfe_pct", top5, rest, lambda x: round(x*100,1))
top5_tickers = [t["ticker"] for t in top5]
print("  tickers represented in top 5: " + str(top5_tickers))

print("\nPHASE 7 ANALYSIS 8/9 + CONCENTRATION COMPLETE.")
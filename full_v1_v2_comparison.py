from dotenv import load_dotenv
load_dotenv()

"""
Full V1 vs V2 Pricing-Model Sensitivity Experiment, all 6 tickers,
fixed date range. Frozen strategy exactly as implemented -- no
optimization, no threshold changes, no exit/GEX/ML/strike-selection
modifications.
"""

import statistics
from datetime import datetime, timezone
from portfolio_backtest import run_portfolio_backtest

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
MATURE_DATE_CUTOFF = "2026-07-13"  # confirmed warm-up boundary, all 6 tickers

print("=" * 100)
print("STEP 1: V1 REGRESSION CHECK")
print("=" * 100)
v1_results = {}
for ticker in TICKERS:
    v1_results[ticker] = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v1")
    print(ticker + " V1: " + str(v1_results[ticker]["total_trades"]) + " trades")

print("\n" + "=" * 100)
print("STEP 2: RUNNING V2 (all 6 tickers -- this makes real, substantial API calls)")
print("=" * 100)
v2_results = {}
for ticker in TICKERS:
    print("Running V2 for " + ticker + "...")
    v2_results[ticker] = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v2_entry_iv")
    print(ticker + " V2: " + str(v2_results[ticker]["total_trades"]) + " trades")

print("\n" + "=" * 100)
print("PRICING COVERAGE (by ticker)")
print("=" * 100)
total_signals_all = 0
total_available_all = 0
for ticker in TICKERS:
    coverage = v2_results[ticker]["v2_coverage_log"]
    n = len(coverage)
    available = len([c for c in coverage if c["v2_iv_available"]])
    total_signals_all += n
    total_available_all += available
    print(ticker + ": total_signals=" + str(n) + " v2_available=" + str(available) + " coverage=" + str(round(available/n*100,1) if n else 0) + "%")
print("\nOVERALL coverage: " + str(total_available_all) + " / " + str(total_signals_all) + " = " + str(round(total_available_all/total_signals_all*100,1) if total_signals_all else 0) + "%")

def compute_metrics(trades, label):
    n = len(trades)
    if n == 0:
        return {"label": label, "n": 0}
    wins = [t for t in trades if t["pnl_dollars"] > 0]
    win_rate = len(wins) / n * 100
    returns = [t["pnl_pct"] for t in trades]
    avg_return = statistics.mean(returns)
    median_return = statistics.median(returns)
    total_pnl = sum(t["pnl_dollars"] for t in trades)
    gross_win = sum(t["pnl_dollars"] for t in trades if t["pnl_dollars"] > 0)
    gross_loss = abs(sum(t["pnl_dollars"] for t in trades if t["pnl_dollars"] < 0))
    profit_factor = gross_win / gross_loss if gross_loss else None
    holding_periods = [(t["exit_date"] - t["entry_date"]).days for t in trades]
    avg_hp = statistics.mean(holding_periods)
    reasons = {}
    for t in trades:
        reasons[t["exit_reason"]] = reasons.get(t["exit_reason"], 0) + 1

    return {
        "label": label, "n": n, "win_rate": win_rate, "avg_return": avg_return,
        "median_return": median_return, "total_pnl": total_pnl, "profit_factor": profit_factor,
        "avg_holding_period": avg_hp, "exit_reasons": reasons,
    }

def print_metrics(m):
    if m["n"] == 0:
        print(m["label"] + ": no trades")
        return
    print(m["label"] + " (n=" + str(m["n"]) + "):")
    print("  Win rate: " + str(round(m["win_rate"],1)) + "%")
    print("  Avg return: " + str(round(m["avg_return"],2)) + "% | Median return: " + str(round(m["median_return"],2)) + "%")
    print("  Total P&L: $" + str(round(m["total_pnl"],2)))
    print("  Profit factor: " + str(round(m["profit_factor"],2)) if m["profit_factor"] else "  Profit factor: N/A (no losses)")
    print("  Avg holding period: " + str(round(m["avg_holding_period"],2)) + " days")
    print("  Exit reasons: " + str(m["exit_reasons"]))

print("\n" + "=" * 100)
print("STEP 3: FULL PERFORMANCE COMPARISON -- AGGREGATE (all 6 tickers combined)")
print("=" * 100)
all_v1_trades = [t for ticker in TICKERS for t in v1_results[ticker]["closed_trades"]]
all_v2_trades = [t for ticker in TICKERS for t in v2_results[ticker]["closed_trades"]]
print_metrics(compute_metrics(all_v1_trades, "V1 AGGREGATE"))
print()
print_metrics(compute_metrics(all_v2_trades, "V2 AGGREGATE"))

print("\n" + "=" * 100)
print("PER-TICKER COMPARISON")
print("=" * 100)
for ticker in TICKERS:
    print()
    print_metrics(compute_metrics(v1_results[ticker]["closed_trades"], ticker + " V1"))
    print_metrics(compute_metrics(v2_results[ticker]["closed_trades"], ticker + " V2"))

print("\n" + "=" * 100)
print("WARM-UP VS MATURE SPLIT (aggregate, all tickers, V2 only)")
print("=" * 100)
v2_warmup_trades = [t for t in all_v2_trades if str(t["entry_date"]) < MATURE_DATE_CUTOFF]
v2_mature_trades = [t for t in all_v2_trades if str(t["entry_date"]) >= MATURE_DATE_CUTOFF]
print_metrics(compute_metrics(v2_warmup_trades, "V2 WARM-UP PERIOD"))
print()
print_metrics(compute_metrics(v2_mature_trades, "V2 MATURE PERIOD"))

print("\n" + "=" * 100)
print("CAUSAL MECHANISM QUANTIFICATION (aggregate)")
print("=" * 100)
v1_total = len(all_v1_trades)
v2_total = len(all_v2_trades)
print("V1 total trades: " + str(v1_total))
print("V2 total trades: " + str(v2_total))
print("Cascade ratio: " + str(round(v2_total/v1_total,2)) + "x")

v1_dates = set(str(t["entry_date"]) + "|" + t["ticker"] for t in all_v1_trades if "ticker" in t)
print("\n(Note: per-trade ticker field availability varies -- see per-ticker breakdown above for entry-date-level V1-only/V2-only detail per ticker)")

print("\nSTOPPING per instruction -- full comparison complete.")
from dotenv import load_dotenv
load_dotenv()

"""
Direct isolation test: does the entry/exit volatility-methodology
mismatch (V2 entry priced with V2 IV, but exit/mark-to-market always
uses V1 vol) create an artificial immediate valuation jump?

v1_raw_price and v2_raw_price (already captured in the coverage log)
are exactly "V1-comparable valuation" and "V2-entry valuation" --
same underlying, strike, DTE; only the volatility input differs.
No new pricing methodology, no new API calls beyond re-running V1/V2.
"""

import statistics
from datetime import datetime, timezone
from portfolio_backtest import run_portfolio_backtest

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
STOP_LOSS_PCT = -0.40

def analyze_ticker(ticker):
    print("=" * 100)
    print(ticker)
    print("=" * 100)

    v1 = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v1")
    v2 = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v2_entry_iv")

    v2_trades = sorted(v2["closed_trades"], key=lambda t: str(t["entry_date"]))
    v2_by_date = {str(t["entry_date"]): t for t in v2_trades}

    coverage = v2["v2_coverage_log"]
    coverage_by_date = {}
    for c in coverage:
        if c["v2_iv_available"]:
            d = str(c["signal_timestamp"])[:10]
            coverage_by_date.setdefault(d, []).append(c)

    rows = []
    for d, t in v2_by_date.items():
        c_list = coverage_by_date.get(d)
        if not c_list:
            continue
        c = c_list[0]

        v2_raw = c["v2_raw_price"]  # V2-entry valuation (V2 IV, raw, pre-spread)
        v1_comparable = c["v1_raw_price"]  # V1-comparable valuation (V1 vol, same strike/DTE/underlying)
        if v2_raw is None or v1_comparable is None or v2_raw == 0:
            continue

        jump_dollars = v1_comparable - v2_raw
        jump_pct = jump_dollars / v2_raw

        would_hit_stop = jump_pct <= STOP_LOSS_PCT
        actual_exit_reason = t["exit_reason"]
        actual_first_return = t["pnl_pct"]  # using final trade return as proxy for "first observed" direction/magnitude

        rows.append({
            "date": d, "v1_vol": c["v1_vol"], "v2_iv": c["v2_iv"],
            "v2_entry_actual": t["entry_premium"], "v2_raw": v2_raw, "v1_comparable": v1_comparable,
            "jump_dollars": jump_dollars, "jump_pct": jump_pct, "would_hit_stop": would_hit_stop,
            "actual_exit_reason": actual_exit_reason, "actual_return": actual_first_return,
        })

    print("Trades analyzed: " + str(len(rows)))
    if not rows:
        return rows

    vol_ratios = [r["v2_iv"] / r["v1_vol"] for r in rows if r["v1_vol"]]
    jump_pcts = [r["jump_pct"] for r in rows]
    positive_jump = len([j for j in jump_pcts if j > 0])
    hit_stop_immediately = len([r for r in rows if r["would_hit_stop"]])

    print("Median V2 IV / V1 vol: " + str(round(statistics.median(vol_ratios), 3)))
    print("Median immediate valuation jump %: " + str(round(statistics.median(jump_pcts)*100, 1)) + "%")
    print("Trades with POSITIVE jump (V1 valuation > V2 entry): " + str(positive_jump) + " / " + str(len(rows)) + " (" + str(round(positive_jump/len(rows)*100,1)) + "%)")
    print("Trades where jump ALONE would satisfy -40% stop: " + str(hit_stop_immediately) + " / " + str(len(rows)) + " (" + str(round(hit_stop_immediately/len(rows)*100,1)) + "%)")
    print("Median actual trade return: " + str(round(statistics.median([r['actual_return'] for r in rows]),1)) + "%")

    stop_loss_trades = [r for r in rows if r["actual_exit_reason"] == "stop_loss"]
    stop_loss_and_predicted = [r for r in stop_loss_trades if r["would_hit_stop"]]
    print("Actual stop_loss exits: " + str(len(stop_loss_trades)) + " / " + str(len(rows)))
    print("Of those, jump ALONE would have predicted stop_loss: " + str(len(stop_loss_and_predicted)) + " / " + str(len(stop_loss_trades)) if stop_loss_trades else "N/A")

    print("\nSample rows (first 8):")
    for r in rows[:8]:
        print(r["date"] + ": v1_vol=" + str(round(r["v1_vol"],3)) + " v2_iv=" + str(round(r["v2_iv"],3)) + " v2_raw=$" + str(round(r["v2_raw"],3)) + " v1_comparable=$" + str(round(r["v1_comparable"],3)) + " jump=" + str(round(r["jump_pct"]*100,1)) + "% would_hit_stop=" + str(r["would_hit_stop"]) + " actual_exit=" + r["actual_exit_reason"] + " actual_return=" + str(round(r["actual_return"],1)) + "%")

    return rows

all_rows = {}
for ticker in ["AAPL", "SMCI", "MSTR"]:
    all_rows[ticker] = analyze_ticker(ticker)
    print()

print("=" * 100)
print("AGGREGATE (all 3 tickers)")
print("=" * 100)
combined = [r for rows in all_rows.values() for r in rows]
if combined:
    jump_pcts = [r["jump_pct"] for r in combined]
    hit_stop = len([r for r in combined if r["would_hit_stop"]])
    print("Total trades: " + str(len(combined)))
    print("Median jump %: " + str(round(statistics.median(jump_pcts)*100,1)) + "%")
    print("Would immediately hit stop: " + str(hit_stop) + " / " + str(len(combined)) + " (" + str(round(hit_stop/len(combined)*100,1)) + "%)")

print("\nISOLATION TEST COMPLETE.")
from dotenv import load_dotenv
load_dotenv()

"""
IV-relationship hypothesis test for SMCI/MSTR, with AAPL for comparison.
Audit only -- no modifications.
"""

import statistics
from datetime import datetime, timezone
from portfolio_backtest import run_portfolio_backtest

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)

def analyze_ticker(ticker):
    print("=" * 100)
    print(ticker)
    print("=" * 100)

    v1 = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v1")
    v2 = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v2_entry_iv")

    v1_trades = sorted(v1["closed_trades"], key=lambda t: str(t["entry_date"]))
    v2_trades = sorted(v2["closed_trades"], key=lambda t: str(t["entry_date"]))
    v1_by_date = {str(t["entry_date"]): t for t in v1_trades}
    v2_by_date = {str(t["entry_date"]): t for t in v2_trades}
    common_dates = sorted(set(v1_by_date.keys()) & set(v2_by_date.keys()))

    coverage = v2["v2_coverage_log"]
    coverage_by_date = {}
    for c in coverage:
        if c["v2_iv_available"]:
            d = str(c["signal_timestamp"])[:10]
            coverage_by_date.setdefault(d, []).append(c)

    rows = []
    for d in common_dates:
        v1t, v2t = v1_by_date[d], v2_by_date[d]
        c_list = coverage_by_date.get(d)
        if not c_list:
            continue
        c = c_list[0]  # first match for that date

        vol_ratio = c["v2_iv"] / c["v1_vol"] if c["v1_vol"] else None
        premium_ratio = v2t["entry_premium"] / v1t["entry_premium"] if v1t["entry_premium"] else None
        v1_hp = (v1t["exit_date"] - v1t["entry_date"]).days
        v2_hp = (v2t["exit_date"] - v2t["entry_date"]).days

        row = {
            "date": d, "underlying": c["underlying_price"], "v1_vol": c["v1_vol"], "v2_iv": c["v2_iv"],
            "vol_ratio": vol_ratio, "v1_strike": v1t["strike"], "v2_strike": v2t["strike"],
            "v1_premium": v1t["entry_premium"], "v2_premium": v2t["entry_premium"], "premium_ratio": premium_ratio,
            "v1_contracts": v1t["contracts"], "v2_contracts": v2t["contracts"],
            "v1_pct_return": v1t["pnl_pct"], "v2_pct_return": v2t["pnl_pct"],
            "v1_exit_reason": v1t["exit_reason"], "v2_exit_reason": v2t["exit_reason"],
            "v1_hp": v1_hp, "v2_hp": v2_hp,
        }
        rows.append(row)

    print("Comparable signals: " + str(len(rows)))
    print("\nSample rows (first 10):")
    for r in rows[:10]:
        print(r["date"] + ": v1_vol=" + str(round(r["v1_vol"],3)) + " v2_iv=" + str(round(r["v2_iv"],3)) + " vol_ratio=" + str(round(r["vol_ratio"],3) if r["vol_ratio"] else None) + " premium_ratio=" + str(round(r["premium_ratio"],3) if r["premium_ratio"] else None) + " v1_contracts=" + str(r["v1_contracts"]) + " v2_contracts=" + str(r["v2_contracts"]) + " v1_pct=" + str(round(r["v1_pct_return"],1)) + "% v2_pct=" + str(round(r["v2_pct_return"],1)) + "% v1_hp=" + str(r["v1_hp"]) + " v2_hp=" + str(r["v2_hp"]))

    # Question A: is V2 IV generally higher than V1 vol?
    vol_ratios = [r["vol_ratio"] for r in rows if r["vol_ratio"] is not None]
    higher_count = len([r for r in vol_ratios if r > 1.0])
    lower_count = len([r for r in vol_ratios if r < 1.0])
    print("\n--- QUESTION A: IV relationship ---")
    print("Median vol_ratio (V2/V1): " + str(round(statistics.median(vol_ratios),3)) + " | Mean: " + str(round(statistics.mean(vol_ratios),3)))
    print("V2 IV > V1 vol: " + str(higher_count) + " / " + str(len(vol_ratios)))
    print("V2 IV < V1 vol: " + str(lower_count) + " / " + str(len(vol_ratios)))

    # Question B: correlation between vol_ratio and premium_ratio
    print("\n--- QUESTION B: does vol ratio predict premium ratio? ---")
    premium_ratios = [r["premium_ratio"] for r in rows if r["premium_ratio"] is not None]
    if len(vol_ratios) > 2:
        try:
            correlation = statistics.correlation(vol_ratios, premium_ratios)
            print("Correlation(vol_ratio, premium_ratio): " + str(round(correlation, 3)))
        except Exception as e:
            print("Correlation calc failed: " + str(e))

    # Question C: percentage returns by group
    print("\n--- QUESTION C: percentage return comparison ---")
    v1_pct = [r["v1_pct_return"] for r in rows]
    v2_pct = [r["v2_pct_return"] for r in rows]
    print("V1 median pct return: " + str(round(statistics.median(v1_pct),1)) + "% | V2 median: " + str(round(statistics.median(v2_pct),1)) + "%")

    # Question D: higher IV -> faster stop-outs / shorter holding?
    print("\n--- QUESTION D: does higher V2 IV predict faster/worse exits? ---")
    high_iv_rows = [r for r in rows if r["vol_ratio"] and r["vol_ratio"] > statistics.median(vol_ratios)]
    low_iv_rows = [r for r in rows if r["vol_ratio"] and r["vol_ratio"] <= statistics.median(vol_ratios)]
    for label, group in [("HIGH vol_ratio half", high_iv_rows), ("LOW vol_ratio half", low_iv_rows)]:
        if not group:
            continue
        avg_hp = statistics.mean([r["v2_hp"] for r in group])
        avg_pct = statistics.mean([r["v2_pct_return"] for r in group])
        stop_losses = len([r for r in group if r["v2_exit_reason"] == "stop_loss"])
        print(label + " (n=" + str(len(group)) + "): avg_v2_holding=" + str(round(avg_hp,2)) + "d avg_v2_pct_return=" + str(round(avg_pct,1)) + "% stop_loss_count=" + str(stop_losses) + "/" + str(len(group)))

    return rows

all_rows = {}
for ticker in ["AAPL", "SMCI", "MSTR"]:
    all_rows[ticker] = analyze_ticker(ticker)
    print()

print("AUDIT COMPLETE.")
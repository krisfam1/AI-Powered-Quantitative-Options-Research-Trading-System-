from dotenv import load_dotenv
load_dotenv()

"""
Position-sizing / P&L integrity audit. Does NOT modify any code.
Audits the real, existing formula against real trade data for AAPL,
SMCI, and MSTR -- the primary anomaly and the two opposite-direction
extreme cases.
"""

import statistics
from datetime import datetime, timezone
from portfolio_backtest import run_portfolio_backtest

FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
RISK_PCT = 0.01
STARTING_CAPITAL = 100000.0

def audit_ticker(ticker):
    print("=" * 100)
    print(ticker + " DEEP DIVE")
    print("=" * 100)

    v1 = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=STARTING_CAPITAL, fixed_direction="call", pricing_mode="v1")
    v2 = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=STARTING_CAPITAL, fixed_direction="call", pricing_mode="v2_entry_iv")

    v1_trades = v1["closed_trades"]
    v2_trades = v2["closed_trades"]

    print("\n--- Contract count comparison ---")
    v1_contracts = [t["contracts"] for t in v1_trades]
    v2_contracts = [t["contracts"] for t in v2_trades]
    print("V1 contracts: median=" + str(statistics.median(v1_contracts)) + " mean=" + str(round(statistics.mean(v1_contracts),1)) + " max=" + str(max(v1_contracts)))
    print("V2 contracts: median=" + str(statistics.median(v2_contracts)) + " mean=" + str(round(statistics.mean(v2_contracts),1)) + " max=" + str(max(v2_contracts)))

    print("\n--- P&L identity check (5 sample V2 trades) ---")
    for t in v2_trades[:5]:
        manual_pnl = (t["exit_premium"] - t["entry_premium"]) * t["contracts"] * 100
        matches = abs(manual_pnl - t["pnl_dollars"]) < 0.01
        exposure = t["entry_premium"] * t["contracts"] * 100
        print("  entry=$" + str(round(t["entry_premium"],3)) + " exit=$" + str(round(t["exit_premium"],3)) + " contracts=" + str(t["contracts"]) + " exposure=$" + str(round(exposure,2)) + " code_pnl=$" + str(round(t["pnl_dollars"],2)) + " manual_pnl=$" + str(round(manual_pnl,2)) + " match=" + str(matches) + " exceeds_starting_capital=" + str(exposure > STARTING_CAPITAL))

    print("\n--- Largest winning and losing V2 trades ---")
    sorted_by_pnl = sorted(v2_trades, key=lambda t: t["pnl_dollars"])
    if sorted_by_pnl:
        worst = sorted_by_pnl[0]
        best = sorted_by_pnl[-1]
        print("WORST: entry=$" + str(round(worst["entry_premium"],3)) + " exit=$" + str(round(worst["exit_premium"],3)) + " contracts=" + str(worst["contracts"]) + " exposure=$" + str(round(worst["entry_premium"]*worst["contracts"]*100,2)) + " pnl=$" + str(round(worst["pnl_dollars"],2)) + " reason=" + worst["exit_reason"])
        print("BEST:  entry=$" + str(round(best["entry_premium"],3)) + " exit=$" + str(round(best["exit_premium"],3)) + " contracts=" + str(best["contracts"]) + " exposure=$" + str(round(best["entry_premium"]*best["contracts"]*100,2)) + " pnl=$" + str(round(best["pnl_dollars"],2)) + " reason=" + best["exit_reason"])

    print("\n--- Suspicious trades: exposure > starting capital, or contracts > 3x median ---")
    median_c = statistics.median(v2_contracts)
    suspicious = [t for t in v2_trades if (t["entry_premium"]*t["contracts"]*100 > STARTING_CAPITAL) or (t["contracts"] > median_c * 3)]
    print("Count: " + str(len(suspicious)) + " / " + str(len(v2_trades)))
    for t in suspicious[:5]:
        print("  entry=$" + str(round(t["entry_premium"],3)) + " contracts=" + str(t["contracts"]) + " exposure=$" + str(round(t["entry_premium"]*t["contracts"]*100,2)) + " pnl=$" + str(round(t["pnl_dollars"],2)))

    print("\n--- Separate % vs $ performance ---")
    v1_pct = [t["pnl_pct"] for t in v1_trades]
    v2_pct = [t["pnl_pct"] for t in v2_trades]
    print("V1: median_pct_return=" + str(round(statistics.median(v1_pct),2)) + "% median_$pnl=" + str(round(statistics.median([t['pnl_dollars'] for t in v1_trades]),2)))
    print("V2: median_pct_return=" + str(round(statistics.median(v2_pct),2)) + "% median_$pnl=" + str(round(statistics.median([t['pnl_dollars'] for t in v2_trades]),2)))
    print("Total contracts traded: V1=" + str(sum(v1_contracts)) + " V2=" + str(sum(v2_contracts)))

    return {"ticker": ticker, "v1_trades": v1_trades, "v2_trades": v2_trades}

results = {}
for ticker in ["AAPL", "SMCI", "MSTR"]:
    results[ticker] = audit_ticker(ticker)
    print()

print("AUDIT COMPLETE.")
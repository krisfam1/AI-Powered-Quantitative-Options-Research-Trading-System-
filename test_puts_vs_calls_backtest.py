from dotenv import load_dotenv
load_dotenv()

"""
CRITICAL DISCOVERY TEST: tonight's entire backtest validation session
only ever tested CALL options (option_type defaults to "call" and was
never explicitly overridden in any script run tonight). This tests the
exact same validated strategy explicitly on PUTS, to see whether real
backtest evidence confirms what real, live account data has been
showing (puts meaningfully underperforming calls).
"""

from options_backtest_engine import run_options_backtest
from datetime import datetime, timezone, timedelta

end = datetime.now(timezone.utc)
start = end - timedelta(days=30)
tickers = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]


def run_batch(option_type, label):
    totals = {"trades": 0, "pnl": 0.0, "wins": 0}
    for ticker in tickers:
        result = run_options_backtest(
            ticker, start, end, dte_target=14, option_type=option_type,
            entry_mode="weighted", entry_score_threshold=20,
            target_delta=0.30, apply_spread_cost=True, exit_mode="reversal_guard",
        )
        totals["trades"] += result.get("total_trades", 0)
        totals["pnl"] += result.get("net_pnl_dollars", 0)
        totals["wins"] += result.get("total_trades", 0) * result.get("win_rate", 0) / 100
    wr = (totals["wins"] / totals["trades"] * 100) if totals["trades"] else 0
    print("\n" + label + ": " + str(totals["trades"]) + " trades, " + "{:.1f}".format(wr) + "% win rate, $" + "{:.2f}".format(totals["pnl"]))
    return totals


print("=" * 70)
print("CALLS (this is what ALL of tonight's prior validation actually tested)")
print("=" * 70)
call_results = run_batch("call", "CALLS")

print("\n" + "=" * 70)
print("PUTS (never tested until now)")
print("=" * 70)
put_results = run_batch("put", "PUTS")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("Calls: $" + "{:.2f}".format(call_results["pnl"]) + " (" + str(call_results["trades"]) + " trades)")
print("Puts:  $" + "{:.2f}".format(put_results["pnl"]) + " (" + str(put_results["trades"]) + " trades)")
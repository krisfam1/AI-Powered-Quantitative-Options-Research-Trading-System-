from dotenv import load_dotenv
load_dotenv()

"""
Complete re-validation of the core reversal_guard vs. baseline comparison,
this time genuinely including BOTH calls and puts -- closing the real gap
discovered tonight where every prior backtest only ever tested calls
(option_type defaults to "call" and was never overridden).
"""

from options_backtest_engine import run_options_backtest
from datetime import datetime, timezone, timedelta

end = datetime.now(timezone.utc)
train_start = end - timedelta(days=90)
train_end = end - timedelta(days=30)
holdout_start = train_end
holdout_end = end

tickers = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]


def run_batch(start, end, exit_mode, label):
    totals = {"trades": 0, "pnl": 0.0, "wins": 0}
    for ticker in tickers:
        for option_type in ["call", "put"]:
            result = run_options_backtest(
                ticker, start, end, dte_target=14, option_type=option_type,
                entry_mode="weighted", entry_score_threshold=20,
                target_delta=0.30, apply_spread_cost=True, exit_mode=exit_mode,
            )
            totals["trades"] += result.get("total_trades", 0)
            totals["pnl"] += result.get("net_pnl_dollars", 0)
            totals["wins"] += result.get("total_trades", 0) * result.get("win_rate", 0) / 100
    wr = (totals["wins"] / totals["trades"] * 100) if totals["trades"] else 0
    print(label + ": " + str(totals["trades"]) + " trades, " + "{:.1f}".format(wr) + "% win rate, $" + "{:.2f}".format(totals["pnl"]))
    return totals


print("=" * 70)
print("TRAINING PERIOD (calls + puts combined)")
print("=" * 70)
baseline_train = run_batch(train_start, train_end, "auto", "Baseline (flat exit) train")
reversal_train = run_batch(train_start, train_end, "reversal_guard", "Reversal_guard train")

print("\n" + "=" * 70)
print("HOLDOUT PERIOD (calls + puts combined)")
print("=" * 70)
baseline_holdout = run_batch(holdout_start, holdout_end, "auto", "Baseline (flat exit) holdout")
reversal_holdout = run_batch(holdout_start, holdout_end, "reversal_guard", "Reversal_guard holdout")

print("\n" + "=" * 70)
print("SUMMARY (this is the honest, complete picture -- calls AND puts)")
print("=" * 70)
print("Baseline:        train=$" + "{:.2f}".format(baseline_train["pnl"]) + " holdout=$" + "{:.2f}".format(baseline_holdout["pnl"]))
print("Reversal_guard:  train=$" + "{:.2f}".format(reversal_train["pnl"]) + " holdout=$" + "{:.2f}".format(reversal_holdout["pnl"]))
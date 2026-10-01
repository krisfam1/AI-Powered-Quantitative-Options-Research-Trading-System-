from dotenv import load_dotenv
load_dotenv()

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
        result = run_options_backtest(
            ticker, start, end, dte_target=14,
            entry_mode="weighted", entry_score_threshold=20,
            target_delta=0.30, apply_spread_cost=True, exit_mode=exit_mode,
        )
        totals["trades"] += result.get("total_trades", 0)
        totals["pnl"] += result.get("net_pnl_dollars", 0)
        totals["wins"] += result.get("total_trades", 0) * result.get("win_rate", 0) / 100
    wr = (totals["wins"] / totals["trades"] * 100) if totals["trades"] else 0
    print(label + ": " + str(totals["trades"]) + " trades, " + "{:.1f}".format(wr) + "% win rate, $" + "{:.2f}".format(totals["pnl"]))
    return totals


print("TRAINING PERIOD")
baseline_train = run_batch(train_start, train_end, "reversal_guard", "Baseline (reversal_guard alone) train")
combined_train = run_batch(train_start, train_end, "reversal_guard_plus_decay", "Reversal_guard + time_decay train")

print("")
print("HOLDOUT PERIOD")
baseline_holdout = run_batch(holdout_start, holdout_end, "reversal_guard", "Baseline (reversal_guard alone) holdout")
combined_holdout = run_batch(holdout_start, holdout_end, "reversal_guard_plus_decay", "Reversal_guard + time_decay holdout")

print("")
print("SUMMARY")
print("Baseline (live):            train=$" + "{:.2f}".format(baseline_train["pnl"]) + " holdout=$" + "{:.2f}".format(baseline_holdout["pnl"]))
print("+ time_decay (fair test):   train=$" + "{:.2f}".format(combined_train["pnl"]) + " holdout=$" + "{:.2f}".format(combined_holdout["pnl"]))
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


def run_batch(start, end, entry_mode, label):
    totals = {"trades": 0, "pnl": 0.0, "wins": 0}
    for ticker in tickers:
        result = run_options_backtest(
            ticker, start, end, dte_target=14,
            exit_mode="reversal_guard", entry_mode=entry_mode,
        )
        totals["trades"] += result.get("total_trades", 0)
        totals["pnl"] += result.get("net_pnl_dollars", 0)
        totals["wins"] += result.get("total_trades", 0) * result.get("win_rate", 0) / 100
    wr = (totals["wins"] / totals["trades"] * 100) if totals["trades"] else 0
    print(label + ": " + str(totals["trades"]) + " trades, " + "{:.1f}".format(wr) + "% win rate, $" + "{:.2f}".format(totals["pnl"]))
    return totals


print("TRAINING PERIOD")
binary_train = run_batch(train_start, train_end, "binary", "Binary train")
weighted_train = run_batch(train_start, train_end, "weighted", "Weighted train")

print("")
print("HOLDOUT PERIOD")
binary_holdout = run_batch(holdout_start, holdout_end, "binary", "Binary holdout")
weighted_holdout = run_batch(holdout_start, holdout_end, "weighted", "Weighted holdout")

print("")
print("SUMMARY")
print("Binary:   train=$" + "{:.2f}".format(binary_train["pnl"]) + " holdout=$" + "{:.2f}".format(binary_holdout["pnl"]))
print("Weighted: train=$" + "{:.2f}".format(weighted_train["pnl"]) + " holdout=$" + "{:.2f}".format(weighted_holdout["pnl"]))
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


def run_batch(start, end, target_delta, label):
    totals = {"trades": 0, "pnl": 0.0, "wins": 0}
    for ticker in tickers:
        result = run_options_backtest(
            ticker, start, end, dte_target=14,
            exit_mode="reversal_guard", entry_mode="weighted",
            entry_score_threshold=20, target_delta=target_delta,
            apply_spread_cost=True,
        )
        totals["trades"] += result.get("total_trades", 0)
        totals["pnl"] += result.get("net_pnl_dollars", 0)
        totals["wins"] += result.get("total_trades", 0) * result.get("win_rate", 0) / 100
    wr = (totals["wins"] / totals["trades"] * 100) if totals["trades"] else 0
    print(label + ": " + str(totals["trades"]) + " trades, " + "{:.1f}".format(wr) + "% win rate, $" + "{:.2f}".format(totals["pnl"]))
    return totals


configs = [
    (None, "ATM"),
    (0.50, "Delta 0.50"),
    (0.40, "Delta 0.40"),
    (0.30, "Delta 0.30"),
]

print("WITH ESTIMATED SPREAD COST APPLIED")
print("")
print("TRAINING PERIOD")
train_results = {}
for delta, label in configs:
    train_results[label] = run_batch(train_start, train_end, delta, label + " train")

print("")
print("HOLDOUT PERIOD")
holdout_results = {}
for delta, label in configs:
    holdout_results[label] = run_batch(holdout_start, holdout_end, delta, label + " holdout")

print("")
print("SUMMARY (with spread cost)")
for delta, label in configs:
    print(label + ": train=$" + "{:.2f}".format(train_results[label]["pnl"]) + " holdout=$" + "{:.2f}".format(holdout_results[label]["pnl"]))
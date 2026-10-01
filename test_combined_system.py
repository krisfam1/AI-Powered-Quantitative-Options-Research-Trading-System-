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


def run_batch(start, end, label, **kwargs):
    totals = {"trades": 0, "pnl": 0.0, "wins": 0}
    for ticker in tickers:
        result = run_options_backtest(ticker, start, end, dte_target=14, **kwargs)
        totals["trades"] += result.get("total_trades", 0)
        totals["pnl"] += result.get("net_pnl_dollars", 0)
        totals["wins"] += result.get("total_trades", 0) * result.get("win_rate", 0) / 100
    wr = (totals["wins"] / totals["trades"] * 100) if totals["trades"] else 0
    print(label + ": " + str(totals["trades"]) + " trades, " + "{:.1f}".format(wr) + "% win rate, $" + "{:.2f}".format(totals["pnl"]))
    return totals


print("=" * 60)
print("ORIGINAL BASELINE (before tonight's changes)")
print("=" * 60)
orig_train = run_batch(train_start, train_end, "Original train", exit_mode="auto", entry_mode="binary")
orig_holdout = run_batch(holdout_start, holdout_end, "Original holdout", exit_mode="auto", entry_mode="binary")

print("")
print("=" * 60)
print("FULL COMBINED SYSTEM (reversal_guard + weighted entry + delta 0.30 + spread cost)")
print("=" * 60)
combined_train = run_batch(
    train_start, train_end, "Combined train",
    exit_mode="reversal_guard", entry_mode="weighted",
    entry_score_threshold=20, target_delta=0.30, apply_spread_cost=True,
)
combined_holdout = run_batch(
    holdout_start, holdout_end, "Combined holdout",
    exit_mode="reversal_guard", entry_mode="weighted",
    entry_score_threshold=20, target_delta=0.30, apply_spread_cost=True,
)

print("")
print("=" * 60)
print("FINAL SUMMARY")
print("=" * 60)
print("Original:  train=$" + "{:.2f}".format(orig_train["pnl"]) + " holdout=$" + "{:.2f}".format(orig_holdout["pnl"]))
print("Combined:  train=$" + "{:.2f}".format(combined_train["pnl"]) + " holdout=$" + "{:.2f}".format(combined_holdout["pnl"]))

if orig_holdout["pnl"] != 0:
    improvement = (combined_holdout["pnl"] - orig_holdout["pnl"]) / abs(orig_holdout["pnl"]) * 100
    print("Holdout improvement: " + "{:.1f}".format(improvement) + "%")
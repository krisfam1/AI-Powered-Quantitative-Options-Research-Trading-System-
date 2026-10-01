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


common_kwargs = dict(
    exit_mode="reversal_guard", entry_mode="weighted", entry_score_threshold=20,
    target_delta=0.30, apply_spread_cost=True,
)

print("TRAINING PERIOD")
no_filter_train = run_batch(train_start, train_end, "No close-strength train", require_close_strength=False, **common_kwargs)
filter_train = run_batch(train_start, train_end, "Close-strength train", require_close_strength=True, **common_kwargs)

print("")
print("HOLDOUT PERIOD")
no_filter_holdout = run_batch(holdout_start, holdout_end, "No close-strength holdout", require_close_strength=False, **common_kwargs)
filter_holdout = run_batch(holdout_start, holdout_end, "Close-strength holdout", require_close_strength=True, **common_kwargs)

print("")
print("SUMMARY")
print("No filter:      train=$" + "{:.2f}".format(no_filter_train["pnl"]) + " holdout=$" + "{:.2f}".format(no_filter_holdout["pnl"]))
print("Close-strength:  train=$" + "{:.2f}".format(filter_train["pnl"]) + " holdout=$" + "{:.2f}".format(filter_holdout["pnl"]))
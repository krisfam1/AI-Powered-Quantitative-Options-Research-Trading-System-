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


common_kwargs = dict(exit_mode="reversal_guard", entry_mode="weighted", entry_score_threshold=20, apply_spread_cost=True)

print("TRAINING PERIOD")
fixed_train = run_batch(train_start, train_end, "Fixed 0.30 train", target_delta=0.30, **common_kwargs)
adaptive_train = run_batch(train_start, train_end, "Adaptive train", adaptive_delta=True, **common_kwargs)

print("")
print("HOLDOUT PERIOD")
fixed_holdout = run_batch(holdout_start, holdout_end, "Fixed 0.30 holdout", target_delta=0.30, **common_kwargs)
adaptive_holdout = run_batch(holdout_start, holdout_end, "Adaptive holdout", adaptive_delta=True, **common_kwargs)

print("")
print("SUMMARY")
print("Fixed 0.30: train=$" + "{:.2f}".format(fixed_train["pnl"]) + " holdout=$" + "{:.2f}".format(fixed_holdout["pnl"]))
print("Adaptive:   train=$" + "{:.2f}".format(adaptive_train["pnl"]) + " holdout=$" + "{:.2f}".format(adaptive_holdout["pnl"]))
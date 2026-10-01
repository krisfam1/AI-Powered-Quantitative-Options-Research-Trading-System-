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


def run_single_tranche(start, end, take_profit_pct, exit_mode="auto"):
    totals = {"pnl": 0.0}
    for ticker in tickers:
        kwargs = dict(
            ticker=ticker, start_date=start, end_date=end, dte_target=14,
            entry_mode="weighted", entry_score_threshold=20,
            target_delta=0.30, apply_spread_cost=True, exit_mode=exit_mode,
        )
        if exit_mode == "auto":
            kwargs["take_profit_pct"] = take_profit_pct
        result = run_options_backtest(**kwargs)
        totals["pnl"] += result.get("net_pnl_dollars", 0)
    return totals


def run_config(start, end, weights, label):
    a = run_single_tranche(start, end, take_profit_pct=0.20)
    runner = run_single_tranche(start, end, take_profit_pct=None, exit_mode="reversal_guard")
    blended = a["pnl"] * weights["A"] + runner["pnl"] * weights["RUNNER"]
    print(label + ": $" + "{:.2f}".format(blended) + "  (A weight=" + str(weights["A"]) + ", RUNNER weight=" + str(weights["RUNNER"]) + ")")
    return blended


configs = [
    ({"A": 0.10, "RUNNER": 0.90}, "10% locked at 20%, 90% runner"),
    ({"A": 0.05, "RUNNER": 0.95}, "5% locked at 20%, 95% runner"),
]

print("TRAINING PERIOD")
for weights, label in configs:
    run_config(train_start, train_end, weights, label + " train")

print("\nHOLDOUT PERIOD")
for weights, label in configs:
    run_config(holdout_start, holdout_end, weights, label + " holdout")

print("\nFor reference, pure reversal_guard baseline (100% runner):")
baseline_train = run_single_tranche(train_start, train_end, None, "reversal_guard")
baseline_holdout = run_single_tranche(holdout_start, holdout_end, None, "reversal_guard")
print("  train=$" + "{:.2f}".format(baseline_train["pnl"]) + " holdout=$" + "{:.2f}".format(baseline_holdout["pnl"]))
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

TRANCHE_WEIGHTS = {"A": 0.20, "B": 0.20, "C": 0.20, "RUNNER": 0.40}


def run_single_tranche(start, end, take_profit_pct, exit_mode="auto"):
    """Run a backtest for ONE tranche's exit rule, using already-validated code paths."""
    totals = {"trades": 0, "pnl": 0.0, "wins": 0}
    for ticker in tickers:
        kwargs = dict(
            ticker=ticker, start_date=start, end_date=end, dte_target=14,
            entry_mode="weighted", entry_score_threshold=20,
            target_delta=0.30, apply_spread_cost=True, exit_mode=exit_mode,
        )
        if exit_mode == "auto":
            kwargs["take_profit_pct"] = take_profit_pct
        result = run_options_backtest(**kwargs)
        totals["trades"] += result.get("total_trades", 0)
        totals["pnl"] += result.get("net_pnl_dollars", 0)
    return totals


def run_blended_scaleout(start, end, label):
    """Runs all 4 tranches separately, weights each by its real allocation, sums for the true blended result."""
    a = run_single_tranche(start, end, take_profit_pct=0.20)
    b = run_single_tranche(start, end, take_profit_pct=0.40)
    c = run_single_tranche(start, end, take_profit_pct=0.75)
    runner = run_single_tranche(start, end, take_profit_pct=None, exit_mode="reversal_guard")

    blended_pnl = (
        a["pnl"] * TRANCHE_WEIGHTS["A"] +
        b["pnl"] * TRANCHE_WEIGHTS["B"] +
        c["pnl"] * TRANCHE_WEIGHTS["C"] +
        runner["pnl"] * TRANCHE_WEIGHTS["RUNNER"]
    )
    print(label + " (blended scale-out): $" + "{:.2f}".format(blended_pnl))
    print("  (A@20%: $" + "{:.2f}".format(a["pnl"]) + ", B@40%: $" + "{:.2f}".format(b["pnl"]) + ", C@75%: $" + "{:.2f}".format(c["pnl"]) + ", RUNNER: $" + "{:.2f}".format(runner["pnl"]) + ")")
    return blended_pnl


def run_baseline(start, end, label):
    """The already-validated single-position reversal_guard-only baseline."""
    result = run_single_tranche(start, end, take_profit_pct=None, exit_mode="reversal_guard")
    print(label + " (single-position reversal_guard baseline): $" + "{:.2f}".format(result["pnl"]))
    return result["pnl"]


print("=" * 70)
print("TRAINING PERIOD")
print("=" * 70)
baseline_train = run_baseline(train_start, train_end, "Baseline train")
scaleout_train = run_blended_scaleout(train_start, train_end, "Scale-out train")

print("")
print("=" * 70)
print("HOLDOUT PERIOD")
print("=" * 70)
baseline_holdout = run_baseline(holdout_start, holdout_end, "Baseline holdout")
scaleout_holdout = run_blended_scaleout(holdout_start, holdout_end, "Scale-out holdout")

print("")
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print("Baseline (current, live):  train=$" + "{:.2f}".format(baseline_train) + " holdout=$" + "{:.2f}".format(baseline_holdout))
print("Scale-out (proposed):      train=$" + "{:.2f}".format(scaleout_train) + " holdout=$" + "{:.2f}".format(scaleout_holdout))
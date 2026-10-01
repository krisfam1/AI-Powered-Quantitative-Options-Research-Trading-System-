from dotenv import load_dotenv
load_dotenv()

"""
Re-validates scale-out (A@20%/B@40%/C@75%/RUNNER@reversal_guard,
20/20/20/40 weighted blend) against pure reversal_guard, with calls+puts
genuinely combined, on the corrected, validated volatility/pricing
methodology, using the now-confirmed 0.30 delta targeting as the base
config for both.
"""

from options_backtest_engine import run_options_backtest
from datetime import datetime, timezone, timedelta

end = datetime.now(timezone.utc)
train_start = end - timedelta(days=90)
train_end = end - timedelta(days=30)
holdout_start = train_end
holdout_end = end

tickers = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
TRANCHE_WEIGHTS = {"A": 0.20, "B": 0.20, "C": 0.20, "RUNNER": 0.40}


def run_single_config(start, end, take_profit_pct, exit_mode="auto"):
    totals = {"pnl": 0.0}
    for ticker in tickers:
        for option_type in ["call", "put"]:
            kwargs = dict(
                ticker=ticker, start_date=start, end_date=end, dte_target=14, option_type=option_type,
                entry_mode="weighted", entry_score_threshold=20, target_delta=0.30,
                apply_spread_cost=True, exit_mode=exit_mode,
            )
            if exit_mode == "auto":
                kwargs["take_profit_pct"] = take_profit_pct
            result = run_options_backtest(**kwargs)
            totals["pnl"] += result.get("net_pnl_dollars", 0)
    return totals


def run_baseline(start, end, label):
    result = run_single_config(start, end, None, exit_mode="reversal_guard")
    print(label + " (pure reversal_guard baseline): $" + "{:.2f}".format(result["pnl"]))
    return result["pnl"]


def run_scaleout(start, end, label):
    a = run_single_config(start, end, 0.20)
    b = run_single_config(start, end, 0.40)
    c = run_single_config(start, end, 0.75)
    runner = run_single_config(start, end, None, exit_mode="reversal_guard")
    blended = a["pnl"]*TRANCHE_WEIGHTS["A"] + b["pnl"]*TRANCHE_WEIGHTS["B"] + c["pnl"]*TRANCHE_WEIGHTS["C"] + runner["pnl"]*TRANCHE_WEIGHTS["RUNNER"]
    print(label + " (blended scale-out): $" + "{:.2f}".format(blended))
    return blended


print("=" * 70)
print("TRAINING PERIOD")
print("=" * 70)
baseline_train = run_baseline(train_start, train_end, "Baseline train")
scaleout_train = run_scaleout(train_start, train_end, "Scale-out train")

print("\n" + "=" * 70)
print("HOLDOUT PERIOD")
print("=" * 70)
baseline_holdout = run_baseline(holdout_start, holdout_end, "Baseline holdout")
scaleout_holdout = run_scaleout(holdout_start, holdout_end, "Scale-out holdout")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("Baseline (pure reversal_guard):  train=$" + "{:.2f}".format(baseline_train) + " holdout=$" + "{:.2f}".format(baseline_holdout))
print("Scale-out:                        train=$" + "{:.2f}".format(scaleout_train) + " holdout=$" + "{:.2f}".format(scaleout_holdout))
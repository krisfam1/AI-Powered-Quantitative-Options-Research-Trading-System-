from dotenv import load_dotenv
load_dotenv()

"""
Re-validates delta-targeting (0.30 delta vs ATM) with calls+puts
genuinely combined, on the corrected, validated volatility/pricing
methodology.
"""

from options_backtest_engine import run_options_backtest
from datetime import datetime, timezone, timedelta

end = datetime.now(timezone.utc)
train_start = end - timedelta(days=90)
train_end = end - timedelta(days=30)
holdout_start = train_end
holdout_end = end

tickers = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]


def run_batch(start, end, use_delta_targeting, label):
    totals = {"trades": 0, "pnl": 0.0, "wins": 0}
    for ticker in tickers:
        for option_type in ["call", "put"]:
            kwargs = dict(
                ticker=ticker, start_date=start, end_date=end, dte_target=14, option_type=option_type,
                entry_mode="weighted", entry_score_threshold=20,
                apply_spread_cost=True, exit_mode="reversal_guard",
            )
            if use_delta_targeting:
                kwargs["target_delta"] = 0.30
            result = run_options_backtest(**kwargs)
            totals["trades"] += result.get("total_trades", 0)
            totals["pnl"] += result.get("net_pnl_dollars", 0)
            totals["wins"] += result.get("total_trades", 0) * result.get("win_rate", 0) / 100
    wr = (totals["wins"] / totals["trades"] * 100) if totals["trades"] else 0
    print(label + ": " + str(totals["trades"]) + " trades, " + "{:.1f}".format(wr) + "% win rate, $" + "{:.2f}".format(totals["pnl"]))
    return totals


print("=" * 70)
print("TRAINING PERIOD (calls + puts combined, corrected pricing)")
print("=" * 70)
atm_train = run_batch(train_start, train_end, False, "ATM (no delta targeting) train")
delta_train = run_batch(train_start, train_end, True, "0.30 delta targeting train")

print("\n" + "=" * 70)
print("HOLDOUT PERIOD (calls + puts combined, corrected pricing)")
print("=" * 70)
atm_holdout = run_batch(holdout_start, holdout_end, False, "ATM (no delta targeting) holdout")
delta_holdout = run_batch(holdout_start, holdout_end, True, "0.30 delta targeting holdout")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("ATM:            train=$" + "{:.2f}".format(atm_train["pnl"]) + " holdout=$" + "{:.2f}".format(atm_holdout["pnl"]))
print("0.30 delta:     train=$" + "{:.2f}".format(delta_train["pnl"]) + " holdout=$" + "{:.2f}".format(delta_holdout["pnl"]))
from dotenv import load_dotenv
load_dotenv()

from options_backtest_engine import run_options_backtest
from datetime import datetime, timezone, timedelta

end = datetime.now(timezone.utc)
train_start = end - timedelta(days=90)
train_end = end - timedelta(days=30)
holdout_start = train_end
holdout_end = end


def run_batch(start, end, option_type, label):
    result = run_options_backtest(
        "SPY", start, end, dte_target=14,
        option_type=option_type, use_dynamic_thresholds=False
    )
    trades = result.get("total_trades", 0)
    wr = result.get("win_rate", 0)
    pnl = result.get("net_pnl_dollars", 0)
    print(label + ": " + str(trades) + " trades, " + "{:.1f}".format(wr) + "% win rate, $" + "{:.2f}".format(pnl))
    return result


print("=" * 60)
print("SPY OPTIONS -- TRAINING (60 days)")
print("=" * 60)
calls_train = run_batch(train_start, train_end, "call", "Calls train")
puts_train = run_batch(train_start, train_end, "put", "Puts train")

print("\n" + "=" * 60)
print("SPY OPTIONS -- HOLDOUT (30 days)")
print("=" * 60)
calls_holdout = run_batch(holdout_start, holdout_end, "call", "Calls holdout")
puts_holdout = run_batch(holdout_start, holdout_end, "put", "Puts holdout")

print("\n" + "=" * 60)
print("COMBINED")
print("=" * 60)

train_trades = calls_train["total_trades"] + puts_train["total_trades"]
train_pnl = calls_train["net_pnl_dollars"] + puts_train["net_pnl_dollars"]
train_wins_calls = calls_train["total_trades"] * calls_train["win_rate"] / 100
train_wins_puts = puts_train["total_trades"] * puts_train["win_rate"] / 100
train_wins = train_wins_calls + train_wins_puts
train_wr = (train_wins / train_trades * 100) if train_trades else 0
print("Combined train: " + str(train_trades) + " trades, " + "{:.1f}".format(train_wr) + "% win rate, $" + "{:.2f}".format(train_pnl))

holdout_trades = calls_holdout["total_trades"] + puts_holdout["total_trades"]
holdout_pnl = calls_holdout["net_pnl_dollars"] + puts_holdout["net_pnl_dollars"]
holdout_wins_calls = calls_holdout["total_trades"] * calls_holdout["win_rate"] / 100
holdout_wins_puts = puts_holdout["total_trades"] * puts_holdout["win_rate"] / 100
holdout_wins = holdout_wins_calls + holdout_wins_puts
holdout_wr = (holdout_wins / holdout_trades * 100) if holdout_trades else 0
print("Combined holdout: " + str(holdout_trades) + " trades, " + "{:.1f}".format(holdout_wr) + "% win rate, $" + "{:.2f}".format(holdout_pnl))
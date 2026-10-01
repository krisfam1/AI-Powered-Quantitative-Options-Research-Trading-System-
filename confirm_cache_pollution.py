from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timezone, timedelta
from options_backtest_engine import run_options_backtest, _volatility_series_cache
from portfolio_backtest import run_portfolio_backtest

end = datetime.now(timezone.utc)
start = end - timedelta(days=90)

print("Cache size BEFORE any calls: " + str(len(_volatility_series_cache)))

print("\nCalling run_options_backtest (original engine)...")
run_options_backtest(
    "AAPL", start, end, dte_target=14, option_type="call",
    entry_mode="weighted", entry_score_threshold=20,
    target_delta=0.30, apply_spread_cost=True, exit_mode="reversal_guard",
)
print("Cache size AFTER original engine call: " + str(len(_volatility_series_cache)))
cache_keys_after_first = list(_volatility_series_cache.keys())

print("\nCalling run_portfolio_backtest (portfolio engine)...")
result = run_portfolio_backtest(["AAPL"], start, end, starting_capital=100000.0, fixed_direction="call")
print("Cache size AFTER portfolio engine call: " + str(len(_volatility_series_cache)))
cache_keys_after_second = list(_volatility_series_cache.keys())

print("\nNew cache keys added by portfolio engine call: " + str(len(cache_keys_after_second) - len(cache_keys_after_first)))
print("(0 = portfolio engine REUSED the original engine's cached volatility series -- confirms cache pollution)")
print("(1 = portfolio engine computed its own, independent series -- cache sharing was NOT the cause)")

print("\nPortfolio engine trade count in THIS sequence: " + str(result["total_trades"]))
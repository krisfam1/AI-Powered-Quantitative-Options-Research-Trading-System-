from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timezone, timedelta

import backtest_engine as be
_orig_get_daily_regime = be.get_daily_regime

_exception_log = []

# Wrap get_daily_regime to detect silent failures -- the entry block in
# run_portfolio_backtest wraps the whole entry attempt in try/except
# Exception: pass, so if get_daily_regime (or anything downstream) throws,
# it's currently invisible. We want to know if that's happening.
def logged_get_daily_regime(*args, **kwargs):
    try:
        return _orig_get_daily_regime(*args, **kwargs)
    except Exception as e:
        _exception_log.append(("get_daily_regime", args, kwargs, str(e)))
        raise

be.get_daily_regime = logged_get_daily_regime

import portfolio_backtest as pbt
# portfolio_backtest.py does `from backtest_engine import get_daily_regime`
# (a separate binding) -- patch that too so our wrapper is actually used.
pbt.get_daily_regime = logged_get_daily_regime

end = datetime.now(timezone.utc)
start = end - timedelta(days=45)
TICKERS = ["AAPL", "MSFT", "NVDA", "SMCI", "MSTR", "AMD"]

print("=" * 70)
print("DYNAMIC REGIME TEST -- fixed_direction=None (never tested before)")
print("=" * 70)
result = pbt.run_portfolio_backtest(
    TICKERS, start, end, starting_capital=100000.0, fixed_direction=None
)
trades = result["closed_trades"]
print(f"Total trades: {result['total_trades']}")

print("\n" + "=" * 70)
print("DIRECTION BREAKDOWN")
print("=" * 70)
calls = [t for t in trades if t.get("option_type") == "call"]
puts = [t for t in trades if t.get("option_type") == "put"]
other = [t for t in trades if t.get("option_type") not in ("call", "put")]
print(f"  Calls: {len(calls)}")
print(f"  Puts:  {len(puts)}")
if other:
    print(f"  [!] Unexpected option_type values: {[t.get('option_type') for t in other]}")

print("\n" + "=" * 70)
print("REGIME CONSISTENCY CHECK")
print("=" * 70)
print("Re-checking each trade's direction against the regime that would")
print("have been computed at its entry timestamp -- flagging any mismatch")
print("(e.g. a 'call' entered during a bearish regime).\n")

mismatches = 0
checked = 0
for t in trades:
    ticker = t.get("ticker")
    entry_date = t.get("entry_date")
    option_type = t.get("option_type")
    if ticker is None or entry_date is None:
        continue
    # Reconstruct an approximate timestamp for the regime check (midday UTC
    # on the entry date -- close enough since regime is date-based with a
    # 50-day lookback, not intraday-sensitive).
    approx_ts = datetime(entry_date.year, entry_date.month, entry_date.day, 15, 0, tzinfo=timezone.utc)
    try:
        regime = _orig_get_daily_regime(ticker, approx_ts, period=50)
    except Exception as e:
        print(f"  [!] {ticker} {entry_date}: regime recheck failed -- {e}")
        continue
    checked += 1
    expected = "call" if regime == "bullish" else "put" if regime == "bearish" else "call"
    if expected != option_type:
        mismatches += 1
        print(f"  {ticker} {entry_date}: traded={option_type} regime={regime} expected={expected}  [MISMATCH]")

print(f"\n  Checked {checked} trades, {mismatches} direction/regime mismatches.")
print("  (Some mismatch is possible if regime shifted between the bar's exact")
print("  timestamp and our approximate midday recheck -- a handful is normal,")
print("  many would suggest a real bug.)")

print("\n" + "=" * 70)
print("SILENT EXCEPTION CHECK")
print("=" * 70)
if _exception_log:
    print(f"  [!] {len(_exception_log)} exception(s) occurred inside get_daily_regime")
    print("  during the run -- these are currently swallowed by the entry")
    print("  block's try/except Exception: pass, so they'd normally be invisible:")
    for name, args, kwargs, err in _exception_log[:10]:
        print(f"    {name}{args} {kwargs} -> {err}")
else:
    print("  No exceptions occurred in get_daily_regime during this run.")
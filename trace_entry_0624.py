from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timezone, timedelta, date

TARGET_DATE = date(2026, 6, 24)
TICKER = "AAPL"

end = datetime.now(timezone.utc)
start = end - timedelta(days=75)

# --- Set up logging monkey-patches BEFORE importing the engines, so both ---
# --- options_backtest_engine.py and portfolio_backtest.py pick up the    ---
# --- patched versions via their `import backtest_engine as be` / etc.   ---
import backtest_engine as be
import entry_scorer

_orig_check_breakout = be.check_breakout
_orig_check_breakdown = be.check_breakdown
_orig_calculate_entry_score = entry_scorer.calculate_entry_score

log = []

def _bar_date(bars, index):
    try:
        ts = bars[index].timestamp
        return ts.date() if hasattr(ts, "date") else ts
    except Exception:
        return None

def logged_check_breakout(bars, index, lookback=20):
    result = _orig_check_breakout(bars, index, lookback=lookback)
    d = _bar_date(bars, index)
    if d == TARGET_DATE:
        log.append(("check_breakout", index, d, result))
    return result

def logged_check_breakdown(bars, index, lookback=20):
    result = _orig_check_breakdown(bars, index, lookback=lookback)
    d = _bar_date(bars, index)
    if d == TARGET_DATE:
        log.append(("check_breakdown", index, d, result))
    return result

def logged_calculate_entry_score(ticker, bars, index, option_type, spy_regime=None):
    result = _orig_calculate_entry_score(ticker, bars, index, option_type, spy_regime=spy_regime)
    d = _bar_date(bars, index)
    if d == TARGET_DATE:
        log.append(("calculate_entry_score", index, d, option_type, spy_regime, result))
    return result

be.check_breakout = logged_check_breakout
be.check_breakdown = logged_check_breakdown
entry_scorer.calculate_entry_score = logged_calculate_entry_score

# Now import the engines -- they do `import backtest_engine as be` /
# `from entry_scorer import calculate_entry_score`, so we need to patch
# entry_scorer.calculate_entry_score BEFORE these modules cache a direct
# reference to it via `from ... import ...`.
import options_backtest_engine as obe
import portfolio_backtest as pbt

# Also patch the direct references each engine holds if they imported via
# `from entry_scorer import calculate_entry_score` (creates a separate binding).
if hasattr(obe, "calculate_entry_score"):
    obe.calculate_entry_score = logged_calculate_entry_score
if hasattr(pbt, "calculate_entry_score"):
    pbt.calculate_entry_score = logged_calculate_entry_score

print("=" * 70)
print(f"TRACING ENTRY DECISION ON {TARGET_DATE} -- {TICKER} PUTS")
print("=" * 70)

log.clear()
print("\nRunning ORIGINAL engine...")
original_result = obe.run_options_backtest(
    TICKER, start, end, dte_target=14, option_type="put",
    entry_mode="weighted", entry_score_threshold=20,
    target_delta=0.30, apply_spread_cost=True, exit_mode="reversal_guard",
)
original_log = list(log)

log.clear()
print("Running PORTFOLIO engine...")
portfolio_result = pbt.run_portfolio_backtest(
    [TICKER], start, end, starting_capital=100000.0, fixed_direction="put"
)
portfolio_log = list(log)

print("\n" + "=" * 70)
print(f"ORIGINAL ENGINE -- calls logged on {TARGET_DATE}")
print("=" * 70)
if not original_log:
    print("  (no logged calls on this date -- engine may not have reached this bar at all)")
for entry in original_log:
    print(f"  {entry}")

print("\n" + "=" * 70)
print(f"PORTFOLIO ENGINE -- calls logged on {TARGET_DATE}")
print("=" * 70)
if not portfolio_log:
    print("  (no logged calls on this date -- engine may not have reached this bar at all)")
for entry in portfolio_log:
    print(f"  {entry}")

print("\n" + "=" * 70)
print("INTERPRETATION")
print("=" * 70)
print("If ORIGINAL shows check_breakdown=True and calculate_entry_score with a")
print("passing score, but PORTFOLIO shows check_breakdown=False or no entries")
print("logged at all, that pinpoints exactly which gate diverged on this date.")
print("If PORTFOLIO never reached this bar (empty log) while ORIGINAL did,")
print("that suggests a bar-count/window/index difference between the two")
print("engines' data fetching, not a difference in the decision logic itself.")
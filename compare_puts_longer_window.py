from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timezone, timedelta
from options_backtest_engine import run_options_backtest
from portfolio_backtest import run_portfolio_backtest

end = datetime.now(timezone.utc)
start = end - timedelta(days=75)  # longer window than the 30-day tests so far
TICKER = "AAPL"

print("=" * 70)
print("ORIGINAL, VALIDATED ENGINE -- " + TICKER + " (PUTS, 75-day window)")
print("=" * 70)
original_result = run_options_backtest(
    TICKER, start, end, dte_target=14, option_type="put",
    entry_mode="weighted", entry_score_threshold=20,
    target_delta=0.30, apply_spread_cost=True, exit_mode="reversal_guard",
)
original_trades = original_result.get("trades", [])
print("Total trades: " + str(original_result["total_trades"]))
original_dates = sorted(str(t["entry_date"]) for t in original_trades)
print("Entry dates: " + str(original_dates))

print("\n" + "=" * 70)
print("NEW PORTFOLIO ENGINE -- " + TICKER + " (PUTS, 75-day window)")
print("=" * 70)
portfolio_result = run_portfolio_backtest([TICKER], start, end, starting_capital=100000.0, fixed_direction="put")
portfolio_trades = portfolio_result["closed_trades"]
print("Total trades: " + str(portfolio_result["total_trades"]))
portfolio_dates = sorted(str(t["entry_date"]) for t in portfolio_trades)
print("Entry dates: " + str(portfolio_dates))

# --- Entry date diff ---
print("\n" + "=" * 70)
print("ENTRY DATE DIFFERENCE")
print("=" * 70)
from collections import Counter
orig_counts = Counter(original_dates)
port_counts = Counter(portfolio_dates)
all_dates = sorted(set(original_dates) | set(portfolio_dates))
entry_mismatch = False
for d in all_dates:
    o = orig_counts.get(d, 0)
    p = port_counts.get(d, 0)
    if o != p:
        entry_mismatch = True
        print("  " + d + ": original=" + str(o) + " portfolio=" + str(p))
if not entry_mismatch:
    print("  No entry date/count mismatches.")

# --- Exit-level diff, matched by entry_date ---
print("\n" + "=" * 70)
print("EXIT-LEVEL DIFFERENCE (matched by entry_date)")
print("=" * 70)

def index_by_entry_date(trades):
    idx = {}
    for t in trades:
        d = str(t.get("entry_date"))
        idx.setdefault(d, []).append(t)
    return idx

orig_idx = index_by_entry_date(original_trades)
port_idx = index_by_entry_date(portfolio_trades)

CANDIDATE_FIELDS = ["exit_date", "exit_reason", "pnl_dollars", "pnl_pct"]
mismatches_found = False
for d in all_dates:
    o_list = orig_idx.get(d, [])
    p_list = port_idx.get(d, [])
    if len(o_list) != len(p_list):
        print(f"  {d}: trade COUNT differs -- original={len(o_list)} portfolio={len(p_list)}")
        mismatches_found = True
        continue
    for o, p in zip(o_list, p_list):
        row_diffs = []
        for field in CANDIDATE_FIELDS:
            if field not in o or field not in p:
                continue
            o_val, p_val = o[field], p[field]
            if isinstance(o_val, (int, float)) and isinstance(p_val, (int, float)):
                if abs(o_val - p_val) > 0.01:
                    row_diffs.append(f"{field}: original={o_val} portfolio={p_val}")
            else:
                if o_val != p_val:
                    row_diffs.append(f"{field}: original={o_val} portfolio={p_val}")
        if row_diffs:
            mismatches_found = True
            print(f"  {d}:")
            for diff in row_diffs:
                print(f"      {diff}")
if not mismatches_found:
    print("  No exit-level mismatches found.")

# --- Net P&L totals ---
print("\n" + "=" * 70)
print("NET P&L TOTALS")
print("=" * 70)
orig_total_pnl = sum(t.get("pnl_dollars", 0) for t in original_trades)
port_total_pnl = sum(t.get("pnl_dollars", 0) for t in portfolio_trades)
print(f"  Original engine total pnl_dollars:  ${orig_total_pnl:,.2f}")
print(f"  Portfolio engine total pnl_dollars: ${port_total_pnl:,.2f}")
print(f"  Difference: ${port_total_pnl - orig_total_pnl:,.2f}")

# --- Check whether any position is still open at the end of the window ---
# (i.e. did reversal_guard actually resolve every position given 75 days,
# or does something stay open indefinitely even with more runway?)
print("\n" + "=" * 70)
print("OPEN-POSITION CHECK (does everything resolve within 75 days?)")
print("=" * 70)
print(f"  Original engine reported {len(original_trades)} CLOSED trades.")
print(f"  Portfolio engine reported {len(portfolio_trades)} CLOSED trades.")
print("  (If the underlying engines track open positions at window-end")
print("  separately from closed_trades/trades, that count isn't visible")
print("  here -- but a much longer window should reduce how often")
print("  reversal_guard positions are still pending when the backtest ends.)")
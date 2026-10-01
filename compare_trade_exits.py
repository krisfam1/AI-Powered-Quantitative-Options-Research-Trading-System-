from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timezone, timedelta
from options_backtest_engine import run_options_backtest
from portfolio_backtest import run_portfolio_backtest

end = datetime.now(timezone.utc)
start = end - timedelta(days=30)
TICKER = "AAPL"

print("=" * 70)
print("ORIGINAL, VALIDATED ENGINE -- " + TICKER)
print("=" * 70)
original_result = run_options_backtest(
    TICKER, start, end, dte_target=14, option_type="call",
    entry_mode="weighted", entry_score_threshold=20,
    target_delta=0.30, apply_spread_cost=True, exit_mode="reversal_guard",
)
original_trades = original_result.get("trades", [])
print("Total trades: " + str(original_result["total_trades"]))

print("\n" + "=" * 70)
print("NEW PORTFOLIO ENGINE -- " + TICKER)
print("=" * 70)
portfolio_result = run_portfolio_backtest([TICKER], start, end, starting_capital=100000.0, fixed_direction="call")
portfolio_trades = portfolio_result["closed_trades"]
print("Total trades: " + str(portfolio_result["total_trades"]))

# --- Sanity check: show what fields are actually available on each trade record ---
print("\n" + "=" * 70)
print("AVAILABLE FIELDS ON EACH TRADE RECORD (sanity check)")
print("=" * 70)
if original_trades:
    print("Original engine trade keys: " + str(sorted(original_trades[0].keys())))
else:
    print("Original engine: no trades to inspect")
if portfolio_trades:
    print("Portfolio engine trade keys: " + str(sorted(portfolio_trades[0].keys())))
else:
    print("Portfolio engine: no trades to inspect")

# --- Try to match trades by entry_date and compare exit-level fields ---
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

all_dates = sorted(set(orig_idx.keys()) | set(port_idx.keys()))

# Fields we WANT to compare -- adjust these names once you confirm actual keys
# from the "AVAILABLE FIELDS" printout above.
CANDIDATE_FIELDS = ["exit_date", "exit_premium", "exit_reason", "pnl_dollars", "pnl_pct", "entry_premium", "contracts", "strike"]

mismatches_found = False
missing_fields_warned = set()

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
            o_has = field in o
            p_has = field in p
            if not o_has or not p_has:
                if field not in missing_fields_warned:
                    missing_fields_warned.add(field)
                continue
            o_val = o[field]
            p_val = p[field]
            # numeric fields get a tolerance, everything else exact match
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
    print("  No exit-level mismatches found across comparable fields.")

if missing_fields_warned:
    print("\n  NOTE: these candidate fields were missing from one or both trade")
    print("  records and were SKIPPED (not compared):")
    for f in sorted(missing_fields_warned):
        print(f"    - {f}")
    print("  Check the 'AVAILABLE FIELDS' printout above and update")
    print("  CANDIDATE_FIELDS in this script with the correct key names.")

print("\n" + "=" * 70)
print("FORMULA-BASED CONTRACTS CHECK (independent of stored pnl_dollars)")
print("=" * 70)
print("Both engines use: contracts = max(int(risk_dollars / (entry_premium * 100)), 1)")
print("with risk_dollars = 100000.0 * 0.01 = 1000.0 by default in both.\n")

RISK_DOLLARS = 100000.0 * 0.01

for d in all_dates:
    o_list = orig_idx.get(d, [])
    p_list = port_idx.get(d, [])
    if len(o_list) != len(p_list):
        continue
    for o, p in zip(o_list, p_list):
        o_entry = o.get("entry_premium")
        o_exit = o.get("exit_premium")
        o_pnl = o.get("pnl_dollars")
        p_entry = p.get("entry_premium")
        p_exit = p.get("exit_premium")
        p_contracts = p.get("contracts")
        p_pnl = p.get("pnl_dollars")
        if o_entry is None or o_exit is None:
            continue

        expected_contracts = max(int(RISK_DOLLARS / (o_entry * 100)), 1)
        naive_pnl_from_stored = (o_exit - o_entry) * expected_contracts * 100

        print(f"  {d}:")
        print(f"      entry_premium: original={o_entry:.4f} portfolio={p_entry:.4f}")
        print(f"      exit_premium (stored): original={o_exit:.4f} portfolio={p_exit:.4f}")
        print(f"      expected_contracts (formula, from entry_premium)={expected_contracts}  portfolio_actual_contracts={p_contracts}")
        print(f"      naive_pnl_from_stored_fields (entry/exit * expected_contracts * 100)={naive_pnl_from_stored:.2f}")
        print(f"      original_actual_pnl_dollars={o_pnl:.2f}  portfolio_actual_pnl_dollars={p_pnl:.2f}")
        print()
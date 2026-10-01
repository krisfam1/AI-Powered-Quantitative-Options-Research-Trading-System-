from dotenv import load_dotenv
load_dotenv()

"""
Record-ID snapshot-date verification for the 105 "matched" trades in
combined_iv_spread_correction.py.

Background: this project already established and validated (in
v2_iv_pricing_model.py, at 8.8% median pricing error) that EODHD's
`tradetime` field is NOT reliable for identifying which calendar day a
record actually belongs to -- the record's own `id` field has a date
suffix (format: "<contract>-<YYYY-MM-DD>") that is the authoritative
snapshot date, and every reliable EODHD lookup in this project checks
`id_date == obs_date` explicitly before accepting a record.

fetch_exact_contract_quote() in combined_iv_spread_correction.py does
NOT do this check -- it only filters by tradetime_from/to and
exp_date_from/to, then picks nearest strike. Check 1 (already run)
confirmed exp_date is correct 100% of the time for the 105 matched
trades. This script checks whether the DATE is also correct, using the
exact same id-date rule already validated in v2_iv_pricing_model.py's
_select_real_contract() and get_v2_checkpoint_iv().

This script does NOT:
    - modify combined_iv_spread_correction.py or v2_iv_pricing_model.py
    - rerun the combined correction
    - substitute a corrected value
    - draw a conclusion about V1's real economics
It only reports whether the id-date invariant holds for the quotes
already used to produce the -$11,472 combined result.
"""

import os
import requests
from datetime import datetime, timezone
from portfolio_backtest import run_portfolio_backtest

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]

print("Reproducing frozen V1 baseline (must match: $20,427.64, 251 trades)...\n")
v1_results = {}
for ticker in TICKERS:
    v1_results[ticker] = run_portfolio_backtest(
        [ticker], FIXED_START, FIXED_END, starting_capital=100000.0,
        fixed_direction="call", pricing_mode="v1"
    )
all_trades = [{**t, "ticker": tk} for tk in TICKERS for t in v1_results[tk]["closed_trades"]]
total_pnl_check = sum(t["pnl_dollars"] for t in all_trades)
print("Reproduced: $" + str(round(total_pnl_check, 2)) + ", n=" + str(len(all_trades)))
if abs(total_pnl_check - 20427.64) > 0.01 or len(all_trades) != 251:
    print("*** DISCREPANCY -- STOPPING ***")
    exit()
print("Reproduction confirmed.\n")


def fetch_exact_contract_quote_with_id(ticker, quote_date, strike, exp_date):
    """
    Same request/selection logic as fetch_exact_contract_quote() in
    combined_iv_spread_correction.py (UNMODIFIED), but this copy also
    keeps the raw record `id` field alongside the selected attributes,
    purely so we can apply the id-date check AFTER selection -- the
    selection logic itself (which record gets chosen as "nearest
    strike") is byte-for-byte identical to the original.
    """
    params = {
        "filter[underlying_symbol]": ticker, "filter[tradetime_from]": quote_date.isoformat(), "filter[tradetime_to]": quote_date.isoformat(),
        "filter[exp_date_from]": exp_date.isoformat(), "filter[exp_date_to]": exp_date.isoformat(),
        "api_token": EODHD_API_TOKEN, "page[limit]": 1000,
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=60)
        resp.raise_for_status()
        raw = resp.json().get("data", [])
    except Exception:
        return None
    records = [(r.get("id", ""), r["attributes"]) for r in raw if r["attributes"].get("type") == "call"]
    if not records:
        return None
    nearest_id, nearest_attrs = min(records, key=lambda pair: abs(pair[1].get("strike", 1e9) - strike))
    return nearest_id, nearest_attrs


def id_date_from_record_id(record_id):
    parts = record_id.split("-", 1)
    if len(parts) != 2:
        return None
    try:
        return datetime.strptime(parts[1], "%Y-%m-%d").date()
    except ValueError:
        return None


print("Re-selecting the same 105 matched trades' quotes and checking the")
print("authoritative record-ID snapshot date against the requested entry/exit date...\n")

rows = []
for i, t in enumerate(all_trades):
    entry_result = fetch_exact_contract_quote_with_id(t["ticker"], t["entry_date"], t["strike"], t["expiry_date"])
    exit_result = fetch_exact_contract_quote_with_id(t["ticker"], t["exit_date"], t["strike"], t["expiry_date"])

    if entry_result is None or exit_result is None:
        continue  # this trade was excluded originally -- not part of the 105, skip
    entry_id, entry_attrs = entry_result
    exit_id, exit_attrs = exit_result
    if entry_attrs.get("ask") is None or exit_attrs.get("bid") is None or entry_attrs.get("ask", 0) <= 0:
        continue  # excluded for a different reason, not part of the matched 105

    entry_id_date = id_date_from_record_id(entry_id)
    exit_id_date = id_date_from_record_id(exit_id)

    entry_requested_date = t["entry_date"].date() if hasattr(t["entry_date"], "date") else t["entry_date"]
    exit_requested_date = t["exit_date"].date() if hasattr(t["exit_date"], "date") else t["exit_date"]

    rows.append({
        "ticker": t["ticker"],
        "entry_requested_date": entry_requested_date,
        "entry_id_date": entry_id_date,
        "entry_date_matches": entry_id_date == entry_requested_date,
        "exit_requested_date": exit_requested_date,
        "exit_id_date": exit_id_date,
        "exit_date_matches": exit_id_date == exit_requested_date,
        "combined_pnl": (exit_attrs["bid"] - entry_attrs["ask"]) * t["contracts"] * 100,
    })

    if (i + 1) % 50 == 0:
        print(f"  ... {i+1} / {len(all_trades)} processed")

print(f"\nMatched trades re-identified: {len(rows)} (compare against 105 from the original run)\n")

print("=" * 100)
print("ID-DATE INVARIANT CHECK")
print("=" * 100)
entry_pass = sum(1 for r in rows if r["entry_date_matches"])
exit_pass = sum(1 for r in rows if r["exit_date_matches"])
both_pass = sum(1 for r in rows if r["entry_date_matches"] and r["exit_date_matches"])
print(f"Entry-side id_date == requested entry_date:  {entry_pass} / {len(rows)} ({entry_pass/len(rows)*100:.1f}%)" if rows else "no rows")
print(f"Exit-side  id_date == requested exit_date:   {exit_pass} / {len(rows)} ({exit_pass/len(rows)*100:.1f}%)" if rows else "")
print(f"BOTH sides pass:                              {both_pass} / {len(rows)} ({both_pass/len(rows)*100:.1f}%)" if rows else "")

print("\n" + "=" * 100)
print("SAMPLE OF FAILURES (if any) -- requested date vs actual record-ID snapshot date")
print("=" * 100)
failures = [r for r in rows if not (r["entry_date_matches"] and r["exit_date_matches"])]
if not failures:
    print("No failures -- every matched trade's quotes carry the correct record-ID snapshot date.")
for r in failures[:15]:
    print(f"  {r['ticker']}  entry: requested={r['entry_requested_date']} actual_id_date={r['entry_id_date']} "
          f"match={r['entry_date_matches']}  |  exit: requested={r['exit_requested_date']} "
          f"actual_id_date={r['exit_id_date']} match={r['exit_date_matches']}")

print("\n" + "=" * 100)
print("IMPACT ON COMBINED P&L IF DATE-MISMATCHED TRADES WERE EXCLUDED")
print("=" * 100)
if rows:
    clean_rows = [r for r in rows if r["entry_date_matches"] and r["exit_date_matches"]]
    dirty_rows = [r for r in rows if not (r["entry_date_matches"] and r["exit_date_matches"])]
    print(f"Date-clean trades: n={len(clean_rows)}  combined P&L sum=${sum(r['combined_pnl'] for r in clean_rows):,.2f}")
    print(f"Date-mismatched trades: n={len(dirty_rows)}  combined P&L sum=${sum(r['combined_pnl'] for r in dirty_rows):,.2f}")
    print(f"(Original full matched-105 combined total was -$11,472.00 for comparison)")

print("\nID-DATE VERIFICATION COMPLETE. No production code modified, no correction rerun,")
print("no conclusion asserted about V1's real economics.")
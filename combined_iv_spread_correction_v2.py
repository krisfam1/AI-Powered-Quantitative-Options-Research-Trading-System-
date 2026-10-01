from dotenv import load_dotenv
load_dotenv()

"""
Combined IV + spread correction, v2 -- reuses ALREADY-VALIDATED
methodology instead of the naive approach in combined_iv_spread_correction.py.

WHY THIS FILE EXISTS (do not merge into or overwrite the original):
Following this project's established pattern (V1 stays frozen, V2 is
built alongside it, never in place), combined_iv_spread_correction.py is
left untouched. This is a separate, corrected version.

Two real bugs were found in combined_iv_spread_correction.py tonight,
and BOTH turned out to already have validated fixes elsewhere in this
codebase that combined_iv_spread_correction.py simply never adopted:

1. fetch_exact_contract_quote() filtered only by tradetime + exact
   exp_date, with no check that the returned record's authoritative
   record-ID date actually matched the requested day. Real result: 17
   of 105 "matched" trades used a quote from the WRONG day (always
   LATER than requested -- a lookahead-relevant forward-fill artifact).
   ALREADY FIXED in v2_iv_pricing_model.py's _select_real_contract() /
   get_v2_checkpoint_iv(), which query a WIDE exp_date range and then
   hard-filter on `id_date == obs_date` (record["id"].split("-",1)[1]).
   This file imports _select_real_contract() directly rather than
   re-deriving the fix.

2. combined_iv_spread_correction.py re-selects "nearest strike"
   independently at entry AND exit, risking a different real contract
   at each side. ALREADY FIXED in the intent (if not literal reuse) of
   get_v2_checkpoint_iv(), which fixes the contract symbol at entry and
   looks up that SAME symbol at exit, never re-selecting. This file's
   fetch_fixed_contract_quote() is modeled directly on
   get_v2_checkpoint_iv(), extended to return bid (execution price),
   not just IV.

Also incorporates the lesson from fix_real_expiration_bug.py: the REAL
matched contract's actual expiration is recorded and compared against
V1's synthetic flat-14-day target, rather than assuming they're the same.

Does NOT touch: V1, combined_iv_spread_correction.py, v2_iv_pricing_model.py,
portfolio_backtest.py, any signal/strike/exit logic.
"""

import os
import requests
from datetime import datetime, timezone
from portfolio_backtest import run_portfolio_backtest
from v2_iv_pricing_model import _select_real_contract  # REUSED, not re-derived

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
TARGET_DTE = 14  # matches V1's synthetic convention, for contract SELECTION at entry only

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


def fetch_fixed_contract_quote(ticker, contract_symbol, exp_date_str, quote_date_str):
    """
    Modeled directly on get_v2_checkpoint_iv() in v2_iv_pricing_model.py,
    extended to return bid (execution price) instead of just IV.
    Looks up the SAME contract symbol fixed at entry -- never re-selects
    nearest-strike independently. Applies the authoritative record-ID
    snapshot-date rule (never tradetime). Returns None if genuinely
    unavailable -- never fabricates, never falls back.
    """
    obs_date = datetime.strptime(quote_date_str, "%Y-%m-%d").date()
    params = {
        "filter[underlying_symbol]": ticker,
        "filter[tradetime_from]": quote_date_str, "filter[tradetime_to]": quote_date_str,
        "filter[exp_date_from]": exp_date_str, "filter[exp_date_to]": exp_date_str,
        "api_token": EODHD_API_TOKEN, "page[limit]": 1000,
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=60)
        resp.raise_for_status()
        records = resp.json().get("data", [])
    except Exception:
        return None
    for r in records:
        a = r.get("attributes", {})
        if a.get("contract") != contract_symbol:
            continue
        parts = r.get("id", "").split("-", 1)
        if len(parts) != 2:
            continue
        try:
            id_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
        except ValueError:
            continue
        if id_date != obs_date:
            continue
        if a.get("bid") is None:
            return None
        return a
    return None


print("Selecting real, id-date-verified entry contracts, then fetching the")
print("SAME fixed contract's exit quote (this will take a while)...\n")

results = []
excluded = []

for i, t in enumerate(all_trades):
    entry_date_str = (t["entry_date"].date() if hasattr(t["entry_date"], "date") else t["entry_date"]).isoformat()
    exit_date_str = (t["exit_date"].date() if hasattr(t["exit_date"], "date") else t["exit_date"]).isoformat()
    option_type = t.get("option_type", "call")

    entry_contract = _select_real_contract(t["ticker"], entry_date_str, t["strike"], option_type, TARGET_DTE)
    if entry_contract is None:
        excluded.append({"ticker": t["ticker"], "entry_date": entry_date_str, "stage": "entry_selection",
                          "reason": "no id-date-verified real contract with bid/ask/IV on entry date (wide DTE range)"})
        continue

    exit_quote = fetch_fixed_contract_quote(t["ticker"], entry_contract["contract"], entry_contract["exp_date"], exit_date_str)
    if exit_quote is None:
        excluded.append({"ticker": t["ticker"], "entry_date": entry_date_str, "stage": "exit_lookup",
                          "reason": "same fixed contract has no id-date-verified bid on exit date"})
        continue

    real_entry_execution = entry_contract["ask"]
    real_exit_execution = exit_quote["bid"]
    if real_entry_execution is None or real_entry_execution <= 0:
        excluded.append({"ticker": t["ticker"], "entry_date": entry_date_str, "stage": "entry_selection",
                          "reason": "invalid (zero/negative/missing) entry ask"})
        continue

    combined_pnl = (real_exit_execution - real_entry_execution) * t["contracts"] * 100
    real_expiration_matches_synthetic = (entry_contract["exp_date"] == t["expiry_date"].date().isoformat()
                                          if hasattr(t["expiry_date"], "date") else entry_contract["exp_date"] == str(t["expiry_date"]))

    results.append({
        "ticker": t["ticker"], "entry_date": entry_date_str, "exit_date": exit_date_str,
        "original_pnl": t["pnl_dollars"],
        "real_entry_ask": real_entry_execution, "real_exit_bid": real_exit_execution,
        "combined_pnl": combined_pnl, "contracts": t["contracts"],
        "real_contract": entry_contract["contract"], "real_expiration": entry_contract["exp_date"],
        "actual_dte_at_entry": entry_contract["_actual_dte"],
        "real_expiration_matches_synthetic_target": real_expiration_matches_synthetic,
    })

    if (i + 1) % 25 == 0:
        print(f"  ... {i+1} / {len(all_trades)} processed")

print(f"\nMatched with id-date-verified, fixed-contract-identity pricing: {len(results)} | Excluded: {len(excluded)}")

from collections import Counter
if excluded:
    print("\nExclusion breakdown by stage:")
    for stage, count in Counter(e["stage"] for e in excluded).items():
        print(f"  {stage}: {count}")
    print("\nExclusion breakdown by ticker:")
    for tk in TICKERS:
        n_excl = sum(1 for e in excluded if e["ticker"] == tk)
        n_total = sum(1 for t in all_trades if t["ticker"] == tk)
        print(f"  {tk}: {n_excl}/{n_total} excluded ({n_excl/n_total*100:.1f}%)")

import statistics

print("\n" + "=" * 100)
print("RESULTS -- id-date-verified, fixed-contract-identity combined correction")
print("=" * 100)
original_total = sum(r["original_pnl"] for r in results)
combined_total = sum(r["combined_pnl"] for r in results)
coverage_pct = len(results) / len(all_trades) * 100 if all_trades else 0

print(f"Original synthetic P&L (matched subset): ${original_total:,.2f}")
print(f"Corrected combined P&L (matched subset): ${combined_total:,.2f}")
print(f"Coverage: {len(results)}/{len(all_trades)} ({coverage_pct:.1f}%)")

print("\nFor comparison against prior figures in the research record:")
print("  Original naive combined correction (105 trades, contains 17 wrong-day quotes): -$11,472.00")
print("  Date-clean subset of that same run (88 trades, diagnostic only, not a rerun): -$15,417.00")
print("  IV-only correction, full 251-trade population: -$1,874.37")
print("  Spread-only correction, full 251-trade population: -$27,307.36")

if results:
    wins_before = sum(1 for r in results if r["original_pnl"] > 0)
    wins_after = sum(1 for r in results if r["combined_pnl"] > 0)
    print(f"\nWin rate BEFORE: {wins_before/len(results)*100:.1f}% | AFTER: {wins_after/len(results)*100:.1f}%")

    gross_win_after = sum(r["combined_pnl"] for r in results if r["combined_pnl"] > 0)
    gross_loss_after = abs(sum(r["combined_pnl"] for r in results if r["combined_pnl"] < 0))
    pf_after = gross_win_after / gross_loss_after if gross_loss_after else None
    print(f"Profit factor AFTER: {pf_after:.2f}" if pf_after else "Profit factor AFTER: N/A")

    mismatch_count = sum(1 for r in results if not r["real_expiration_matches_synthetic_target"])
    print(f"\nReal expiration != V1's synthetic 14-day target: {mismatch_count}/{len(results)} "
          f"({mismatch_count/len(results)*100:.1f}%) -- expected per fix_real_expiration_bug.py's finding")
    dtes = [r["actual_dte_at_entry"] for r in results]
    print(f"Actual DTE at entry: mean={statistics.mean(dtes):.1f}  median={statistics.median(dtes):.1f}  "
          f"min={min(dtes)}  max={max(dtes)}  (target was {TARGET_DTE})")

print("\n" + "=" * 100)
print("SAMPLE (first 10 matched trades)")
print("=" * 100)
for r in results[:10]:
    print(f"  {r['ticker']} {r['entry_date']}: original=${r['original_pnl']:.2f} corrected=${r['combined_pnl']:.2f} "
          f"contract={r['real_contract']} actual_dte={r['actual_dte_at_entry']} "
          f"exp_matches_synthetic={r['real_expiration_matches_synthetic_target']}")

print("\nCORRECTED COMBINED CORRECTION COMPLETE.")
print("No V1 changes. No changes to combined_iv_spread_correction.py or v2_iv_pricing_model.py.")
print("No signal/strike/exit changes. Reused _select_real_contract() unchanged;")
print("fetch_fixed_contract_quote() is new but modeled directly on get_v2_checkpoint_iv().")
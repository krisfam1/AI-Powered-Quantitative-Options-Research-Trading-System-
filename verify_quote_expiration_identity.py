from dotenv import load_dotenv
load_dotenv()

"""
Contract-identity verification for fetch_exact_contract_quote().

Purpose: determine whether the "matched" 105 trades in
combined_iv_spread_correction.py actually received a quote for the
synthetic expiration V1 specified, or whether EODHD's exp_date_from ==
exp_date_to filter silently returns quotes from a DIFFERENT expiration
when the requested date isn't a real listed expiration.

This script performs ONLY the three verification checks below.
It does NOT:
    - modify fetch_exact_contract_quote() or any production file
    - apply a nearest-expiration substitution
    - rerun the combined correction
    - draw a conclusion about V1's real economics

Check 1: For all 251 trades, call fetch_exact_contract_quote() (VERBATIM,
         unmodified) and inspect the RETURNED quote's own exp_date field
         (source of truth) against the requested synthetic expiry, for
         both entry and exit.
Check 2: For a sample of trades where the synthetic expiry is confirmed
         absent from the real listed calendar (via the unfiltered chain
         query), dump the full returned quote object so we can see
         exactly what expiration/strike came back.
Check 3: Bypass fetch_exact_contract_quote() entirely and hit the raw
         EODHD endpoint with a known-absent exp_date_from==exp_date_to,
         printing the raw response, to see whether EODHD itself is
         respecting or loosening the degenerate date range.
"""

import os
import requests
from datetime import datetime, timezone
from collections import Counter
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


def fetch_exact_contract_quote(ticker, quote_date, strike, exp_date):
    """VERBATIM copy from combined_iv_spread_correction.py -- UNMODIFIED.
    We are testing this function's actual behavior, not a rewritten one."""
    params = {
        "filter[underlying_symbol]": ticker, "filter[tradetime_from]": quote_date.isoformat(), "filter[tradetime_to]": quote_date.isoformat(),
        "filter[exp_date_from]": exp_date.isoformat(), "filter[exp_date_to]": exp_date.isoformat(),
        "api_token": EODHD_API_TOKEN, "page[limit]": 1000,
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=60)
        resp.raise_for_status()
        records = [r["attributes"] for r in resp.json().get("data", []) if r["attributes"].get("type") == "call"]
    except Exception:
        return None
    if not records:
        return None
    nearest = min(records, key=lambda r: abs(r.get("strike", 1e9) - strike))
    return nearest


def parse_exp_date(v):
    if v is None:
        return None
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


print("=" * 100)
print("CHECK 1: for every trade, compare the RETURNED quote's own exp_date field")
print("against the requested synthetic expiry (fetch_exact_contract_quote left unmodified)")
print("=" * 100)

check1_rows = []
for i, t in enumerate(all_trades):
    synthetic_expiry = t["expiry_date"]
    if hasattr(synthetic_expiry, "date"):
        synthetic_expiry = synthetic_expiry.date()

    entry_quote = fetch_exact_contract_quote(t["ticker"], t["entry_date"], t["strike"], t["expiry_date"])
    exit_quote = fetch_exact_contract_quote(t["ticker"], t["exit_date"], t["strike"], t["expiry_date"])

    matched = entry_quote is not None and exit_quote is not None and \
        entry_quote.get("ask") is not None and exit_quote.get("bid") is not None and \
        entry_quote.get("ask") > 0

    entry_returned_exp = parse_exp_date(entry_quote.get("exp_date")) if entry_quote else None
    exit_returned_exp = parse_exp_date(exit_quote.get("exp_date")) if exit_quote else None

    check1_rows.append({
        "ticker": t["ticker"],
        "entry_date": t["entry_date"],
        "exit_date": t["exit_date"],
        "requested_strike": t["strike"],
        "synthetic_expiry": synthetic_expiry,
        "matched": matched,
        "entry_returned_exp": entry_returned_exp,
        "exit_returned_exp": exit_returned_exp,
        "entry_returned_strike": entry_quote.get("strike") if entry_quote else None,
        "exit_returned_strike": exit_quote.get("strike") if exit_quote else None,
    })

    if (i + 1) % 50 == 0:
        print(f"  ... {i+1} / {len(all_trades)} processed")

matched_rows = [r for r in check1_rows if r["matched"]]
print(f"\nMatched trades: {len(matched_rows)}\n")

print(f"{'Result':<40}{'Entry side':>12}{'Exit side':>12}")


def classify(rows, side):
    exact, mismatch, missing = 0, 0, 0
    for r in rows:
        returned = r[f"{side}_returned_exp"]
        if returned is None:
            missing += 1
        elif returned == r["synthetic_expiry"]:
            exact += 1
        else:
            mismatch += 1
    return exact, mismatch, missing


entry_exact, entry_mismatch, entry_missing = classify(matched_rows, "entry")
exit_exact, exit_mismatch, exit_missing = classify(matched_rows, "exit")
print(f"{'Returned expiry == synthetic expiry':<40}{entry_exact:>12}{exit_exact:>12}")
print(f"{'Returned expiry != synthetic expiry':<40}{entry_mismatch:>12}{exit_mismatch:>12}")
print(f"{'Returned expiry field missing':<40}{entry_missing:>12}{exit_missing:>12}")

invariant_fail = sum(1 for r in matched_rows
                      if r["entry_returned_exp"] != r["synthetic_expiry"]
                      or r["exit_returned_exp"] != r["synthetic_expiry"])
print(f"\nMatched trades where the contract-identity invariant "
      f"(returned_exp_date == requested synthetic_expiry, BOTH sides) FAILS: "
      f"{invariant_fail} / {len(matched_rows)} ({invariant_fail/len(matched_rows)*100:.1f}%)"
      if matched_rows else "\nNo matched trades.")

entry_vs_exit_differ = sum(1 for r in matched_rows
                            if r["entry_returned_exp"] is not None and r["exit_returned_exp"] is not None
                            and r["entry_returned_exp"] != r["exit_returned_exp"])
print(f"Matched trades where entry-side and exit-side returned DIFFERENT expirations "
      f"from EACH OTHER (contract identity broken across the trade's own lifecycle): "
      f"{entry_vs_exit_differ} / {len(matched_rows)}"
      if matched_rows else "")

print("\n" + "=" * 100)
print("CHECK 2: sample dump -- matched trades whose returned expiry != synthetic expiry")
print("=" * 100)
mismatched_sample = [r for r in matched_rows if r["entry_returned_exp"] != r["synthetic_expiry"]][:10]
if not mismatched_sample:
    print("No mismatched matched trades found (unexpected given Check 1 -- re-inspect Check 1 output).")
for r in mismatched_sample:
    print(f"  {r['ticker']} entry_date={r['entry_date']} synthetic_expiry={r['synthetic_expiry']} "
          f"requested_strike={r['requested_strike']}")
    print(f"      ENTRY side -> returned_exp={r['entry_returned_exp']} returned_strike={r['entry_returned_strike']}")
    print(f"      EXIT  side -> returned_exp={r['exit_returned_exp']} returned_strike={r['exit_returned_strike']}")

print("\n" + "=" * 100)
print("CHECK 3: raw EODHD request, bypassing fetch_exact_contract_quote entirely,")
print("for a known-absent exp_date_from == exp_date_to")
print("=" * 100)
raw_test_cases = mismatched_sample[:2]
if not raw_test_cases:
    print("No mismatched cases available to build a raw test from.")
for r in raw_test_cases:
    ticker = r["ticker"]
    quote_date = r["entry_date"]
    exp_target = r["synthetic_expiry"]
    print(f"\n--- Raw request: ticker={ticker}, tradetime={quote_date.date() if hasattr(quote_date,'date') else quote_date}, "
          f"exp_date_from=exp_date_to={exp_target.isoformat()} ---")
    params = {
        "filter[underlying_symbol]": ticker,
        "filter[tradetime_from]": quote_date.isoformat(),
        "filter[tradetime_to]": quote_date.isoformat(),
        "filter[exp_date_from]": exp_target.isoformat(),
        "filter[exp_date_to]": exp_target.isoformat(),
        "api_token": EODHD_API_TOKEN,
        "page[limit]": 1000,
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except Exception as e:
        print(f"  Request failed: {e}")
        continue
    print(f"  Raw record count returned: {len(data)}")
    exp_dates_seen = Counter(rec["attributes"].get("exp_date") for rec in data)
    print(f"  Distinct exp_date values in the raw response: {dict(exp_dates_seen)}")
    if exp_dates_seen:
        only_requested = set(exp_dates_seen.keys()) == {exp_target.isoformat()}
        print(f"  ALL returned records have exp_date == requested date: {only_requested}")
        if not only_requested:
            print("  ==> EODHD is returning records for expirations OTHER than the requested exact date.")
            print("  ==> This confirms the degenerate exp_date_from==exp_date_to filter is NOT being")
            print("      treated as an exact filter by the API (or by how we're calling it).")
    else:
        print("  Raw response is empty for this exact date (filter appears to be honored here).")

print("\n" + "=" * 100)
print("SUMMARY -- NO CONCLUSION ASSERTED, NO PRODUCTION CODE MODIFIED")
print("=" * 100)
print("This script only reports what fetch_exact_contract_quote() and the raw EODHD")
print("endpoint actually do. The invariant 'returned_exp_date == requested synthetic_expiry'")
print("should be enforced in fetch_exact_contract_quote() ONLY after this diagnosis is")
print("reviewed and a decision is made about what to do with the current 105/146/-$11,472 result.")
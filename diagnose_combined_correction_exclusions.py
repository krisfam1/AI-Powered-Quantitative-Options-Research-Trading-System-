from dotenv import load_dotenv
load_dotenv()

"""
Exclusion diagnostic for combined_iv_spread_correction.py.

Purpose: determine whether the 146 trades excluded from the combined
IV+spread correction (out of 251 total V1 trades) are randomly distributed
or systematically different from the 105 matched trades -- by ticker,
original P&L sign/magnitude, top-N concentration, and whatever liquidity
fields already exist on the original trade record.

METHODOLOGY DISCIPLINE:
- fetch_exact_contract_quote() below is copied VERBATIM from
  combined_iv_spread_correction.py. Do not modify it here. If that
  function ever changes, this copy must be updated to match, or this
  diagnostic is analyzing a different population than the real run.
- No liquidity field is fabricated. If a field (volume, open_interest,
  delta, dte, strike distance) is not present on the original V1 trade
  record, this script reports that explicitly instead of estimating it.
- No V1 code, no combined_iv_spread_correction.py, no signal/strike/exit
  logic is modified. This is a read-only diagnostic layer.
- No thresholds are optimized and no trading conclusion is drawn here --
  only a description of whether exclusion looks broadly distributed,
  liquidity-concentrated, or directionally biased in original P&L.
"""

import os
import requests
from datetime import datetime, timezone
from collections import Counter, defaultdict
import statistics
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

# Report exactly which fields exist on the original trade record, so the
# liquidity-characteristics section below never guesses.
_sample_keys = sorted(all_trades[0].keys())
print("Fields available on original V1 trade record: " + ", ".join(_sample_keys))
CANDIDATE_LIQUIDITY_FIELDS = ["volume", "open_interest", "delta", "dte", "strike", "iv", "implied_volatility"]
AVAILABLE_LIQUIDITY_FIELDS = [f for f in CANDIDATE_LIQUIDITY_FIELDS if f in _sample_keys]
MISSING_LIQUIDITY_FIELDS = [f for f in CANDIDATE_LIQUIDITY_FIELDS if f not in _sample_keys]
print("Liquidity-relevant fields PRESENT on original record: " + (", ".join(AVAILABLE_LIQUIDITY_FIELDS) or "NONE"))
print("Liquidity-relevant fields NOT present (will not be fabricated): " + (", ".join(MISSING_LIQUIDITY_FIELDS) or "NONE"))
print()


def fetch_exact_contract_quote(ticker, quote_date, strike, exp_date):
    """VERBATIM copy from combined_iv_spread_correction.py -- do not edit
    independently of that file."""
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


print("Re-running quote lookups for all 251 trades to classify matched/excluded")
print("with fine-grained reasons (this mirrors combined_iv_spread_correction.py exactly,")
print("but separates entry-missing from exit-missing rather than collapsing them)...\n")

records = []
for i, t in enumerate(all_trades):
    entry_quote = fetch_exact_contract_quote(t["ticker"], t["entry_date"], t["strike"], t["expiry_date"])
    exit_quote = fetch_exact_contract_quote(t["ticker"], t["exit_date"], t["strike"], t["expiry_date"])

    entry_missing = entry_quote is None
    exit_missing = exit_quote is None

    matched = False
    fine_reason = None
    combined_pnl = None

    if entry_missing and exit_missing:
        fine_reason = "both_missing"
    elif entry_missing:
        fine_reason = "entry_missing_only"
    elif exit_missing:
        fine_reason = "exit_missing_only"
    else:
        entry_ask = entry_quote.get("ask")
        exit_bid = exit_quote.get("bid")
        if entry_ask is None or exit_bid is None:
            fine_reason = "bid_ask_field_missing"
        elif entry_ask <= 0:
            fine_reason = "invalid_entry_ask"
        else:
            matched = True
            combined_pnl = (exit_bid - entry_ask) * t["contracts"] * 100

    rec = {
        "ticker": t["ticker"],
        "entry_date": str(t["entry_date"]),
        "exit_date": str(t["exit_date"]),
        "original_pnl": t["pnl_dollars"],
        "contracts": t["contracts"],
        "matched": matched,
        "fine_reason": fine_reason if not matched else None,
        "combined_pnl": combined_pnl,
    }
    for f in AVAILABLE_LIQUIDITY_FIELDS:
        rec[f] = t.get(f)
    records.append(rec)

    if (i + 1) % 50 == 0:
        print("  ... " + str(i + 1) + " / " + str(len(all_trades)) + " processed")

matched_records = [r for r in records if r["matched"]]
excluded_records = [r for r in records if not r["matched"]]

print("\n" + "=" * 100)
print("1. RECONCILIATION")
print("=" * 100)
print(f"Total trades:    {len(records)}")
print(f"Matched:         {len(matched_records)}")
print(f"Excluded:        {len(excluded_records)}")
print(f"Matched + Excluded == Total: {len(matched_records) + len(excluded_records) == len(records)}")
if len(matched_records) != 105 or len(excluded_records) != 146:
    print(f"*** NOTE: split differs from the original run's 105/146. This can happen if EODHD data ***")
    print(f"*** availability changed between runs, or a network/timeout hiccup occurred. Investigate ***")
    print(f"*** before comparing this diagnostic's numbers 1:1 against the original -$11,472 figure. ***")

print("\n" + "=" * 100)
print("2. TICKER BREAKDOWN")
print("=" * 100)
print(f"{'Ticker':<8}{'Total':>8}{'Matched':>10}{'Excluded':>10}{'Excl %':>10}")
by_ticker = defaultdict(lambda: {"total": 0, "matched": 0, "excluded": 0})
for r in records:
    by_ticker[r["ticker"]]["total"] += 1
    by_ticker[r["ticker"]]["matched" if r["matched"] else "excluded"] += 1
for tk in TICKERS:
    d = by_ticker[tk]
    excl_pct = d["excluded"] / d["total"] * 100 if d["total"] else 0
    print(f"{tk:<8}{d['total']:>8}{d['matched']:>10}{d['excluded']:>10}{excl_pct:>9.1f}%")

print("\n" + "=" * 100)
print("3. MATCHED vs EXCLUDED -- ORIGINAL (synthetic) P&L")
print("=" * 100)


def pnl_stats(group, label):
    if not group:
        print(f"{label}: n=0")
        return
    pnls = [r["original_pnl"] for r in group]
    wins = [p for p in pnls if p > 0]
    print(f"{label}: n={len(group)}  sum=${sum(pnls):,.2f}  mean=${statistics.mean(pnls):,.2f}  "
          f"median=${statistics.median(pnls):,.2f}  win_rate={len(wins)/len(pnls)*100:.1f}%")


pnl_stats(matched_records, "Matched  ")
pnl_stats(excluded_records, "Excluded ")
pnl_stats(records, "All      ")

print("\n" + "=" * 100)
print("4. TOP-5 / TOP-20 ORIGINAL-P&L CONCENTRATION -- matched vs excluded")
print("=" * 100)
sorted_by_original = sorted(records, key=lambda r: -r["original_pnl"])
for n in (5, 20):
    top_n = sorted_by_original[:n]
    top_n_matched = [r for r in top_n if r["matched"]]
    top_n_excluded = [r for r in top_n if not r["matched"]]
    top_n_total_pnl = sum(r["original_pnl"] for r in top_n)
    print(f"Top {n} by original P&L: {len(top_n_matched)} matched / {len(top_n_excluded)} excluded "
          f"(original P&L sum of these {n}: ${top_n_total_pnl:,.2f})")

print("\n" + "=" * 100)
print("5. FINE-GRAINED EXCLUSION REASON BREAKDOWN")
print("=" * 100)
reason_counts = Counter(r["fine_reason"] for r in excluded_records)
for reason, count in reason_counts.most_common():
    print(f"  {reason}: {count}")

print("\n" + "=" * 100)
print("6. LIQUIDITY CHARACTERISTICS -- matched vs excluded (fields actually present only)")
print("=" * 100)
if not AVAILABLE_LIQUIDITY_FIELDS:
    print("No liquidity-relevant fields (volume, open_interest, delta, dte, strike, iv) are present")
    print("on the original V1 trade record. This diagnostic will NOT fabricate estimates for these.")
    print("Coverage limitation: matched-vs-excluded liquidity comparison is not possible with the")
    print("data currently captured in the trade record.")
else:
    for f in AVAILABLE_LIQUIDITY_FIELDS:
        m_vals = [r[f] for r in matched_records if r.get(f) is not None]
        e_vals = [r[f] for r in excluded_records if r.get(f) is not None]
        if m_vals and e_vals:
            print(f"  {f}: matched mean={statistics.mean(m_vals):.4g} (n={len(m_vals)})  "
                  f"excluded mean={statistics.mean(e_vals):.4g} (n={len(e_vals)})")
        else:
            print(f"  {f}: insufficient non-null values to compare (matched n={len(m_vals)}, excluded n={len(e_vals)})")

print("\n" + "=" * 100)
print("7. -115.1%-STYLE ARITHMETIC RECONCILIATION (top-5 vs remaining, on THIS run's matched set)")
print("=" * 100)
if matched_records:
    combined_total = sum(r["combined_pnl"] for r in matched_records)
    sorted_by_combined = sorted(matched_records, key=lambda r: -r["combined_pnl"])
    top5 = sorted_by_combined[:5]
    top5_sum = sum(r["combined_pnl"] for r in top5)
    remaining = sorted_by_combined[5:]
    remaining_sum = sum(r["combined_pnl"] for r in remaining)
    print(f"Combined total (matched, n={len(matched_records)}): ${combined_total:,.2f}")
    print(f"Top-5 combined P&L sum:                              ${top5_sum:,.2f}")
    print(f"Remaining {len(remaining)} trades combined P&L sum:                ${remaining_sum:,.2f}")
    print(f"Identity check (top5 + remaining == total): "
          f"{abs((top5_sum + remaining_sum) - combined_total) < 0.01}")
    if combined_total != 0:
        print(f"Top-5 as % of total (signed, correct denominator): {top5_sum / combined_total * 100:.1f}%")
    else:
        print("Combined total is exactly $0 -- percentage of total is undefined.")
else:
    print("No matched trades -- cannot compute.")

print("\n" + "=" * 100)
print("8. DESCRIPTIVE FLAGS (not a conclusion -- for human classification into the three buckets)")
print("=" * 100)
excl_rates = [by_ticker[tk]["excluded"] / by_ticker[tk]["total"] for tk in TICKERS if by_ticker[tk]["total"] > 0]
if excl_rates:
    print(f"Exclusion rate range across tickers: {min(excl_rates)*100:.1f}% to {max(excl_rates)*100:.1f}%")
if matched_records and excluded_records:
    m_mean = statistics.mean(r["original_pnl"] for r in matched_records)
    e_mean = statistics.mean(r["original_pnl"] for r in excluded_records)
    print(f"Mean original P&L -- matched: ${m_mean:,.2f}  excluded: ${e_mean:,.2f}  "
          f"difference: ${m_mean - e_mean:,.2f}")
print("\nNo statistical test is run here (this is a diagnostic, not a hypothesis test).")
print("Use section 2 for ticker concentration, section 3-4 for P&L-direction bias,")
print("and section 6 for liquidity-based explanation, to classify this exclusion as")
print("broadly-distributed / liquidity-concentrated / directionally-biased.")

print("\nEXCLUSION DIAGNOSTIC COMPLETE. No V1, no combined_iv_spread_correction.py,")
print("no signal/strike/exit logic modified. Read-only diagnostic layer only.")
from dotenv import load_dotenv
load_dotenv()

"""
Expiration-existence diagnostic (narrow, single-hypothesis test).

Hypothesis under test:
    The high exclusion rate in combined_iv_spread_correction.py is primarily
    caused by V1's synthetic "entry_date + 14 calendar days" expiry NOT
    corresponding to an actually-listed option expiration for that
    ticker/date -- rather than by missing quotes for an otherwise-valid,
    really-listed contract.

This script does NOT:
    - choose or apply a "nearest expiration" substitution
    - rerun the combined correction
    - modify V1, combined_iv_spread_correction.py, or any signal/strike/exit logic
    - draw a final conclusion (it reports facts only)

It DOES:
    - recompute matched/excluded classification using the VERBATIM
      fetch_exact_contract_quote() logic from combined_iv_spread_correction.py,
      so this diagnostic is checking the same 105/146 population.
    - for EVERY one of the 251 trades (matched AND excluded, as a control
      group), query EODHD WITHOUT an exp_date filter, for both the entry
      date and exit date, and determine:
        * every real listed expiration for that ticker on that date
        * whether the synthetic expiry (entry_date+14d) exists exactly
        * if not, the nearest real expiration on each side and its distance

ASSUMPTION FLAGGED FOR VERIFICATION:
    Pagination uses "page[offset]" (JSON:API convention) alongside the
    already-confirmed "page[limit]": 1000. This has NOT been independently
    re-confirmed against EODHD in this session (the working script that
    established page[limit]=1000 is not currently available to read). If
    two consecutive pages come back identical, the script prints an
    explicit warning rather than silently trusting the pagination -- take
    that warning seriously before trusting the "expiration does not exist"
    conclusion for the affected ticker/date.
"""

import os
import requests
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter
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


def fetch_all_real_expirations(ticker, quote_date):
    """
    No exp_date filter. Returns (sorted list of unique real expiration
    dates as date objects, pagination_suspect: bool).
    Filters to type=='call' client-side only to reduce payload -- does not
    affect which expirations exist (puts and calls share expirations on
    listed equity/index options).
    """
    seen_exp_dates = set()
    offset = 0
    limit = 1000
    prior_page_signature = None
    pagination_suspect = False
    max_pages = 6  # safety cap: 6000 records for a single ticker/day would be extreme

    for page_num in range(max_pages):
        params = {
            "filter[underlying_symbol]": ticker,
            "filter[tradetime_from]": quote_date.isoformat(),
            "filter[tradetime_to]": quote_date.isoformat(),
            "api_token": EODHD_API_TOKEN,
            "page[limit]": limit,
            "page[offset]": offset,
        }
        try:
            resp = requests.get(BASE_URL, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json().get("data", [])
        except Exception:
            break

        page_records = [r["attributes"] for r in data if r["attributes"].get("type") == "call"]
        page_exp_dates = frozenset(r.get("exp_date") for r in page_records if r.get("exp_date"))

        if page_num > 0 and page_exp_dates and page_exp_dates == prior_page_signature:
            pagination_suspect = True
            break

        for e in page_exp_dates:
            seen_exp_dates.add(e)

        prior_page_signature = page_exp_dates

        if len(page_records) < limit:
            break
        offset += limit

    parsed = []
    for e in seen_exp_dates:
        try:
            parsed.append(datetime.strptime(str(e)[:10], "%Y-%m-%d").date())
        except Exception:
            continue
    return sorted(parsed), pagination_suspect


print("Step 1/2: classifying matched vs excluded (verbatim logic, control group tag)...\n")
trade_records = []
for i, t in enumerate(all_trades):
    entry_quote = fetch_exact_contract_quote(t["ticker"], t["entry_date"], t["strike"], t["expiry_date"])
    exit_quote = fetch_exact_contract_quote(t["ticker"], t["exit_date"], t["strike"], t["expiry_date"])
    matched = entry_quote is not None and exit_quote is not None and \
        entry_quote.get("ask") is not None and exit_quote.get("bid") is not None and \
        entry_quote.get("ask") > 0
    trade_records.append({"trade": t, "matched": matched})
    if (i + 1) % 50 == 0:
        print("  ... " + str(i + 1) + " / " + str(len(all_trades)) + " classified")

n_matched = sum(1 for r in trade_records if r["matched"])
n_excluded = len(trade_records) - n_matched
print(f"\nClassified: matched={n_matched}, excluded={n_excluded} "
      f"(compare against prior run's 105/146 -- should match if EODHD data hasn't shifted)\n")

print("Step 2/2: for every trade, checking real listed expirations at entry_date and exit_date...\n")


def expiry_facts(ticker, quote_date, synthetic_expiry):
    real_exps, pagination_suspect = fetch_all_real_expirations(ticker, quote_date)
    exists = synthetic_expiry in real_exps
    earlier = [e for e in real_exps if e < synthetic_expiry]
    later = [e for e in real_exps if e > synthetic_expiry]
    nearest_earlier = max(earlier) if earlier else None
    nearest_later = min(later) if later else None
    dist_earlier = (synthetic_expiry - nearest_earlier).days if nearest_earlier else None
    dist_later = (nearest_later - synthetic_expiry).days if nearest_later else None
    return {
        "exists": exists,
        "num_real_expirations_seen": len(real_exps),
        "nearest_earlier": nearest_earlier.isoformat() if nearest_earlier else None,
        "nearest_later": nearest_later.isoformat() if nearest_later else None,
        "dist_earlier_days": dist_earlier,
        "dist_later_days": dist_later,
        "pagination_suspect": pagination_suspect,
    }


results = []
pagination_warnings = 0
for i, r in enumerate(trade_records):
    t = r["trade"]
    synthetic_expiry = t["expiry_date"]
    if hasattr(synthetic_expiry, "date"):
        synthetic_expiry = synthetic_expiry.date()

    entry_facts = expiry_facts(t["ticker"], t["entry_date"], synthetic_expiry)
    exit_facts = expiry_facts(t["ticker"], t["exit_date"], synthetic_expiry)
    if entry_facts["pagination_suspect"] or exit_facts["pagination_suspect"]:
        pagination_warnings += 1

    results.append({
        "ticker": t["ticker"],
        "matched": r["matched"],
        "synthetic_expiry": synthetic_expiry.isoformat(),
        "entry_exists": entry_facts["exists"],
        "entry_dist_earlier": entry_facts["dist_earlier_days"],
        "entry_dist_later": entry_facts["dist_later_days"],
        "exit_exists": exit_facts["exists"],
        "exit_dist_earlier": exit_facts["dist_earlier_days"],
        "exit_dist_later": exit_facts["dist_later_days"],
    })

    if (i + 1) % 25 == 0:
        print("  ... " + str(i + 1) + " / " + str(len(trade_records)) + " expiration-checked")

print(f"\nPagination-suspect ticker/date lookups encountered: {pagination_warnings}")
if pagination_warnings > 0:
    print("*** Some 'expiration does not exist' results above may be unreliable if the ***")
    print("*** underlying chain query's pagination did not work as assumed. Treat any  ***")
    print("*** ticker/date flagged this way with extra caution.                        ***")

print("\n" + "=" * 100)
print("1. OVERALL: DOES THE SYNTHETIC EXPIRY EXIST, MATCHED vs EXCLUDED (control comparison)")
print("=" * 100)
for group_name, group_filter in [("Matched", True), ("Excluded", False)]:
    group = [r for r in results if r["matched"] == group_filter]
    if not group:
        continue
    entry_exists_pct = sum(1 for r in group if r["entry_exists"]) / len(group) * 100
    exit_exists_pct = sum(1 for r in group if r["exit_exists"]) / len(group) * 100
    print(f"{group_name} (n={len(group)}): synthetic expiry exists at entry_date={entry_exists_pct:.1f}%, "
          f"at exit_date={exit_exists_pct:.1f}%")

print("\n" + "=" * 100)
print("2. CROSS-TAB: TICKER x MATCHED/EXCLUDED x SYNTHETIC-EXPIRY-EXISTS-AT-ENTRY")
print("=" * 100)
print(f"{'Ticker':<8}{'Group':<10}{'N':>6}{'Exists':>10}{'Absent':>10}{'% Absent':>10}")
for tk in TICKERS:
    for group_name, group_filter in [("Matched", True), ("Excluded", False)]:
        group = [r for r in results if r["ticker"] == tk and r["matched"] == group_filter]
        if not group:
            continue
        exists_n = sum(1 for r in group if r["entry_exists"])
        absent_n = len(group) - exists_n
        pct_absent = absent_n / len(group) * 100
        print(f"{tk:<8}{group_name:<10}{len(group):>6}{exists_n:>10}{absent_n:>10}{pct_absent:>9.1f}%")

print("\n" + "=" * 100)
print("3. DISTANCE TO NEAREST REAL EXPIRATION -- for trades where synthetic expiry is ABSENT at entry_date")
print("=" * 100)
absent_group = [r for r in results if not r["entry_exists"]]
if absent_group:
    min_dists = []
    for r in absent_group:
        candidates = [d for d in (r["entry_dist_earlier"], r["entry_dist_later"]) if d is not None]
        if candidates:
            min_dists.append(min(candidates))
    if min_dists:
        print(f"n={len(min_dists)}  mean={statistics.mean(min_dists):.1f} days  "
              f"median={statistics.median(min_dists):.1f} days  "
              f"min={min(min_dists)}  max={max(min_dists)}")
        within_3 = sum(1 for d in min_dists if d <= 3)
        within_7 = sum(1 for d in min_dists if d <= 7)
        print(f"Within 3 calendar days of a real expiration: {within_3}/{len(min_dists)} "
              f"({within_3/len(min_dists)*100:.1f}%)")
        print(f"Within 7 calendar days of a real expiration: {within_7}/{len(min_dists)} "
              f"({within_7/len(min_dists)*100:.1f}%)")
    else:
        print("No real expirations found on either side for any absent case (unexpected -- check pagination warnings above).")
else:
    print("No trades had an absent synthetic expiry at entry_date.")

print("\n" + "=" * 100)
print("4. RAW SAMPLE (first 15 rows) FOR MANUAL SPOT-CHECK")
print("=" * 100)
for r in results[:15]:
    print(f"  {r['ticker']} matched={r['matched']} synthetic_expiry={r['synthetic_expiry']} "
          f"entry_exists={r['entry_exists']} (earlier -{r['entry_dist_earlier']}d / later +{r['entry_dist_later']}d) "
          f"exit_exists={r['exit_exists']}")

print("\nEXPIRATION-EXISTENCE DIAGNOSTIC COMPLETE.")
print("No conclusion is asserted here. No nearest-expiration substitution was applied.")
print("No V1, no combined_iv_spread_correction.py, no signal/strike/exit logic modified.")
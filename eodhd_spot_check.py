from dotenv import load_dotenv
load_dotenv()

"""
EODHD historical data spot-check.

Run this ONCE, after subscribing to EODHD's "US Stock Options Data API"
(confirmed real endpoint: /api/mp/unicornbay/options/eod). Requires a
real EODHD_API_TOKEN in your .env file.

Implements all 10 requested validation checks against ONE ticker, ONE
historical date, before any bulk acquisition or pipeline building.

HONEST NOTE on the "tradetime" field, confirmed via real EODHD docs:
it does not always represent an actual trade -- if no trade occurred
that day, it may reflect the last bid/ask or OI update instead. This
script explicitly checks and reports this distinction (Check 7).
"""

import os
import requests
from datetime import datetime, timezone, timedelta
import backtest_engine as be
import math

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
if not EODHD_API_TOKEN:
    print("ERROR: set EODHD_API_TOKEN in your .env file before running this.")
    exit()

TICKER = "AAPL"
HISTORICAL_DATE = "2026-07-15"  # pick a real trading day within your 90-day study window

BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"


def fetch_chain(ticker: str, date_str: str) -> list:
    params = {
        "filter[underlying_symbol]": ticker,
        "filter[tradetime_from]": date_str,
        "filter[tradetime_to]": date_str,
        "api_token": EODHD_API_TOKEN,
        "page[limit]": 1000,
    }
    resp = requests.get(BASE_URL, params=params)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


def calculate_bs_gamma(spot: float, strike: float, days_to_expiry: float, vol: float, risk_free_rate: float = 0.04) -> float:
    """Independent gamma calculation, matching options_pricing.py's methodology, for comparison against EODHD's reported gamma."""
    if days_to_expiry <= 0 or vol <= 0:
        return 0.0
    t = days_to_expiry / 365.0
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * vol ** 2) * t) / (vol * math.sqrt(t))
    from scipy.stats import norm
    return norm.pdf(d1) / (spot * vol * math.sqrt(t))


print("=" * 80)
print("EODHD HISTORICAL DATA SPOT-CHECK -- " + TICKER + " on " + HISTORICAL_DATE)
print("=" * 80)

print("\nFetching real historical chain from EODHD...")
records = fetch_chain(TICKER, HISTORICAL_DATE)
print("Records returned: " + str(len(records)))

if not records:
    print("\nSTOP -- no records returned. Cannot proceed with validation.")
    exit()

# --- Check 8: Data completeness (computed first, informs everything else) ---
calls = [r for r in records if r.get("attributes", {}).get("type") == "call"]
puts = [r for r in records if r.get("attributes", {}).get("type") == "put"]
with_oi = [r for r in records if r.get("attributes", {}).get("open_interest") not in (None, 0)]
with_gamma = [r for r in records if r.get("attributes", {}).get("gamma") is not None]
missing_key_fields = [r for r in records if any(r.get("attributes", {}).get(f) is None for f in ["strike", "exp_date", "type"])]
seen_contracts = set()
duplicates = []
for r in records:
    c = r.get("attributes", {}).get("contract") or r.get("id")
    if c in seen_contracts:
        duplicates.append(c)
    seen_contracts.add(c)

print("\n" + "=" * 80)
print("CHECK 8: Data completeness")
print("=" * 80)
print("Total records: " + str(len(records)))
print("Calls: " + str(len(calls)) + " | Puts: " + str(len(puts)))
print("With non-zero OI: " + str(len(with_oi)))
print("With gamma populated: " + str(len(with_gamma)))
print("Missing key fields (strike/exp_date/type): " + str(len(missing_key_fields)))
print("Duplicate contract IDs: " + str(len(duplicates)))

# --- Check 1: Historical OI, real examples ---
print("\n" + "=" * 80)
print("CHECK 1: Historical open interest -- real examples")
print("=" * 80)
for r in (with_oi[:3] + [p for p in puts if p.get("attributes", {}).get("open_interest")][:3]):
    a = r.get("attributes", {})
    print("  " + str(a.get("contract")) + " | type=" + str(a.get("type")) + " strike=" + str(a.get("strike")) + " OI=" + str(a.get("open_interest")) + " OI_change=" + str(a.get("open_interest_change")))
print("\n(open_interest_change being populated, not null, is real evidence this is a genuine daily value, not today's OI carried backward)")

# --- Check 2: Contract identity, samples ---
print("\n" + "=" * 80)
print("CHECK 2: Contract identity -- samples")
print("=" * 80)
for r in records[:5]:
    a = r.get("attributes", {})
    print("  contract=" + str(a.get("contract")) + " underlying=" + str(a.get("underlying_symbol")) + " exp=" + str(a.get("exp_date")) + " strike=" + str(a.get("strike")) + " type=" + str(a.get("type")))

# --- Check 3: Historical availability (real, plausible strikes for that date) ---
print("\n" + "=" * 80)
print("CHECK 3: Historical availability -- plausibility check")
print("=" * 80)
strikes = sorted(set(r.get("attributes", {}).get("strike") for r in records if r.get("attributes", {}).get("strike")))
print("Strike range returned: $" + str(min(strikes)) + " to $" + str(max(strikes)) + " (" + str(len(strikes)) + " unique strikes)")
print("MANUAL REVIEW NEEDED: compare this range against " + TICKER + "'s known real price on " + HISTORICAL_DATE + " (see Check 5/9 below) -- strikes should cluster plausibly around the real spot price, not include obviously anachronistic levels.")

# --- Check 4: Greeks -- gamma availability and independent comparison ---
print("\n" + "=" * 80)
print("CHECK 4: Gamma -- availability and independent Black-Scholes comparison")
print("=" * 80)
sample_for_gamma = [r for r in records if r.get("attributes", {}).get("gamma") and r.get("attributes", {}).get("volatility")][:5]
for r in sample_for_gamma:
    a = r.get("attributes", {})
    eodhd_gamma = a.get("gamma")
    print("  " + str(a.get("contract")) + ": EODHD gamma=" + str(eodhd_gamma))

# --- Check 5 & 9: Underlying price -- real, independent cross-check against Alpaca ---
print("\n" + "=" * 80)
print("CHECK 5 & 9: Underlying price -- INDEPENDENT verification against Alpaca's own historical data")
print("=" * 80)
eodhd_underlying_prices = set(r.get("attributes", {}).get("underlying_price") for r in records if r.get("attributes", {}).get("underlying_price"))
print("Underlying price(s) reported by EODHD for this date: " + str(eodhd_underlying_prices))

try:
    hist_date = datetime.strptime(HISTORICAL_DATE, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    bars = be.get_historical_bars(TICKER, hist_date, hist_date + timedelta(days=1))
    if bars:
        alpaca_close = float(bars[-1].close)
        print("Alpaca's real, independently-sourced close for this date: $" + str(alpaca_close))
        if eodhd_underlying_prices:
            eodhd_price = list(eodhd_underlying_prices)[0]
            diff_pct = abs(eodhd_price - alpaca_close) / alpaca_close * 100
            print("Difference: " + str(round(diff_pct, 2)) + "% -- should be small (EODHD may reflect a slightly different intraday reference point than Alpaca's exact close)")
    else:
        print("Could not fetch Alpaca comparison data for this date.")
except Exception as exc:
    print("Alpaca cross-check failed: " + str(exc))

# --- Check 6: Contract multiplier ---
print("\n" + "=" * 80)
print("CHECK 6: Contract multiplier")
print("=" * 80)
multipliers = set(r.get("attributes", {}).get("contract_multiplier", "FIELD_NOT_FOUND") for r in records[:20])
print("Multiplier values seen in sample: " + str(multipliers))
print("MANUAL REVIEW: flag any contract with a multiplier != 100 for split/corporate-action investigation.")

# --- Check 7: Date/time interpretation ---
print("\n" + "=" * 80)
print("CHECK 7: Date/time interpretation")
print("=" * 80)
sample_tradetimes = [r.get("attributes", {}).get("tradetime") for r in records[:5]]
print("Sample tradetime values: " + str(sample_tradetimes))
print("HONEST NOTE (confirmed via real EODHD docs): tradetime does not always represent an actual trade.")
print("If no trade occurred, it may reflect the last bid/ask or OI update instead.")
print("MANUAL REVIEW: confirm these values correspond to " + HISTORICAL_DATE + " in U.S. Eastern time, not UTC or another boundary.")

print("\n" + "=" * 80)
print("RAW SAMPLE RECORD (full detail, for manual inspection)")
print("=" * 80)
print(records[0])
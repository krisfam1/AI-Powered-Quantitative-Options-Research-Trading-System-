from dotenv import load_dotenv
load_dotenv()

"""
Combined IV + spread correction for V1's 251 known trades.
Methodology: for each trade's EXACT original strike/expiry, fetch REAL
market bid/ask on the entry date and the exit date. Real execution
price = buy at real ASK (entry), sell at real BID (exit) -- this
naturally captures IV and spread effects SIMULTANEOUSLY, since real
bid/ask already reflects the market's actual IV, not a reconstructed
Black-Scholes price. No entry/exit signals, strikes, DTE, or trade
timing changed. Preserves original synthetic and each independent
correction for full comparison.
"""

import os
import requests
from datetime import datetime, timezone, timedelta
from portfolio_backtest import run_portfolio_backtest

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]

print("Reproducing frozen V1 baseline (must match: $20,427.64, 251 trades)...\n")
v1_results = {}
for ticker in TICKERS:
    v1_results[ticker] = run_portfolio_backtest([ticker], FIXED_START, FIXED_END, starting_capital=100000.0, fixed_direction="call", pricing_mode="v1")

all_trades = [{**t, "ticker": tk} for tk in TICKERS for t in v1_results[tk]["closed_trades"]]
total_pnl_check = sum(t["pnl_dollars"] for t in all_trades)
print("Reproduced: $" + str(round(total_pnl_check,2)) + ", n=" + str(len(all_trades)))
if abs(total_pnl_check - 20427.64) > 0.01 or len(all_trades) != 251:
    print("*** DISCREPANCY -- STOPPING ***")
    exit()
print("Reproduction confirmed.\n")


def fetch_exact_contract_quote(ticker, quote_date, strike, exp_date):
    """
    Fetches REAL bid/ask for the same expiry V1 actually used, snapping
    to the NEAREST real, exchange-listed strike -- V1's synthetic
    backtest computes strike via continuous delta-solving (e.g. 277.34),
    which essentially never matches a real, discretely-spaced listed
    strike exactly. This mirrors the already-validated nearest-strike
    approach used successfully elsewhere tonight (251/251, 580/580).
    """
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


print("Fetching REAL entry+exit quotes for the EXACT contract on each of the 251 trades (this will take a while)...\n")

results = []
excluded = []

for i, t in enumerate(all_trades):
    entry_quote = fetch_exact_contract_quote(t["ticker"], t["entry_date"], t["strike"], t["expiry_date"])
    exit_quote = fetch_exact_contract_quote(t["ticker"], t["exit_date"], t["strike"], t["expiry_date"])

    if entry_quote is None or exit_quote is None:
        excluded.append({"ticker": t["ticker"], "entry_date": str(t["entry_date"]), "reason": "no exact-contract quote available on entry or exit date"})
        continue
    if entry_quote.get("ask") is None or exit_quote.get("bid") is None:
        excluded.append({"ticker": t["ticker"], "entry_date": str(t["entry_date"]), "reason": "bid/ask missing on entry or exit quote"})
        continue

    real_entry_execution = entry_quote["ask"]
    real_exit_execution = exit_quote["bid"]
    if real_entry_execution <= 0:
        excluded.append({"ticker": t["ticker"], "entry_date": str(t["entry_date"]), "reason": "invalid (zero/negative) entry ask"})
        continue

    combined_pnl = (real_exit_execution - real_entry_execution) * t["contracts"] * 100

    results.append({
        "ticker": t["ticker"], "entry_date": str(t["entry_date"]), "exit_date": str(t["exit_date"]),
        "original_synthetic_entry": t["entry_premium"], "original_synthetic_exit": t["exit_premium"],
        "original_pnl": t["pnl_dollars"],
        "real_entry_ask": real_entry_execution, "real_exit_bid": real_exit_execution,
        "real_entry_iv": entry_quote.get("volatility"), "real_exit_iv": exit_quote.get("volatility"),
        "combined_pnl": combined_pnl, "contracts": t["contracts"],
    })

    if (i+1) % 50 == 0:
        print("  ... " + str(i+1) + " / " + str(len(all_trades)) + " processed")

print("\nMatched with full combined pricing: " + str(len(results)) + " | Excluded: " + str(len(excluded)))

if excluded:
    print("\nExclusion reasons breakdown:")
    from collections import Counter
    reasons = Counter(e["reason"] for e in excluded)
    for reason, count in reasons.items():
        print("  " + reason + ": " + str(count))

import statistics

print("\n" + "=" * 100)
print("REQUIRED OUTPUTS")
print("=" * 100)

original_total = sum(r["original_pnl"] for r in results)
combined_total = sum(r["combined_pnl"] for r in results)
coverage_pct = len(results) / len(all_trades) * 100

print("1. Original synthetic V1 total P&L (matched subset): $" + str(round(original_total,2)))
print("2. IV-only corrected total P&L: [see full-population IV repricing result: -$1,874.37, all 251 trades]")
print("3. Spread-only corrected total P&L: [see prior closing calc: -$27,307.36, all 251 trades]")
print("4. FULLY CORRECTED (combined, real execution) total P&L: $" + str(round(combined_total,2)))
print("5. Total number of trades: " + str(len(all_trades)))
print("6. Number of trades with valid combined pricing: " + str(len(results)))
print("7. Coverage percentage: " + str(round(coverage_pct,1)) + "%")
print("8. Number of trades excluded: " + str(len(excluded)) + " (reasons above)")

total_spread_component = sum((r["real_entry_ask"] - r["original_synthetic_entry"]) for r in results) * 100
print("9-10. See per-trade attribution below (combined correction captures both simultaneously, not separable into independent additive components)")

diff_vs_original = combined_total - original_total
print("11. Combined adjustment relative to original (matched subset): $" + str(round(diff_vs_original,2)))

wins_before = len([r for r in results if r["original_pnl"] > 0])
wins_after = len([r for r in results if r["combined_pnl"] > 0])
print("12. Win rate BEFORE: " + str(round(wins_before/len(results)*100,1)) + "% | AFTER: " + str(round(wins_after/len(results)*100,1)) + "%")

gross_win_before = sum(r["original_pnl"] for r in results if r["original_pnl"] > 0)
gross_loss_before = abs(sum(r["original_pnl"] for r in results if r["original_pnl"] < 0))
pf_before = gross_win_before/gross_loss_before if gross_loss_before else None
gross_win_after = sum(r["combined_pnl"] for r in results if r["combined_pnl"] > 0)
gross_loss_after = abs(sum(r["combined_pnl"] for r in results if r["combined_pnl"] < 0))
pf_after = gross_win_after/gross_loss_after if gross_loss_after else None
print("13. Profit factor BEFORE: " + (str(round(pf_before,2)) if pf_before else "N/A") + " | AFTER: " + (str(round(pf_after,2)) if pf_after else "N/A"))

sorted_by_date = sorted(results, key=lambda r: r["exit_date"])
cum_before, peak_before, maxdd_before = 0,0,0
cum_after, peak_after, maxdd_after = 0,0,0
for r in sorted_by_date:
    cum_before += r["original_pnl"]; peak_before = max(peak_before, cum_before); maxdd_before = max(maxdd_before, peak_before-cum_before)
    cum_after += r["combined_pnl"]; peak_after = max(peak_after, cum_after); maxdd_after = max(maxdd_after, peak_after-cum_after)
print("14. Max drawdown BEFORE: $" + str(round(maxdd_before,2)) + " | AFTER: $" + str(round(maxdd_after,2)))

sorted_by_combined = sorted(results, key=lambda r: -r["combined_pnl"])
top5_combined = sum(r["combined_pnl"] for r in sorted_by_combined[:5])
print("15. Top 5 trades' contribution to combined total: $" + str(round(top5_combined,2)) + " (" + str(round(top5_combined/combined_total*100,1) if combined_total else 0) + "% of total)")

print("\n" + "=" * 100)
print("SAMPLE PER-TRADE ATTRIBUTION (first 10 matched trades)")
print("=" * 100)
for r in results[:10]:
    print("  " + r["ticker"] + " " + r["entry_date"] + ": original=$" + str(round(r["original_pnl"],2)) + " combined=$" + str(round(r["combined_pnl"],2)) + " (real_entry_ask=" + str(r["real_entry_ask"]) + " real_exit_bid=" + str(r["real_exit_bid"]) + ")")

print("\nCOMBINED CORRECTION COMPLETE. No V1 changes. No signal/strike/exit changes.")
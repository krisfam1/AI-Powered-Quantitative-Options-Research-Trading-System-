from dotenv import load_dotenv
load_dotenv()

"""
Step 1 ONLY, per explicit instruction: a read-only data-feasibility audit for
a genuinely new, broader-universe volatility-prediction hypothesis. Does NOT
select a target, train a model, write a preregistration, or touch any of the
four permanently-closed experiments (RF v1/v2, XGBoost v1, regularized
XGBoost v2 -- CLAUDE.md Section 58).

Measures actual data depth/coverage for a candidate ~55-ticker universe
beyond the current 6 (AAPL, AMD, MSTR, NVDA, SMCI, TSLA), using ONLY the
project's own already-validated fetch methods:
  - Alpaca underlying bars: backtest_engine-style StockHistoricalDataClient
    call (RAW, matching every other script's spot_price convention).
  - EODHD options chains: gex_data_loader.py's _fetch_raw_chain_paginated(),
    the SAME validated, full-pagination method used throughout this
    project's real data-generation scripts (SPY backfill, OI-skew variants,
    the volatility-dataset builds) -- NOT a naive single-page query. Every
    single call in this audit explicitly checks and reports
    `pagination_complete`/`pages_requested`, not just "returned without
    error," per explicit instruction (referencing the manifest's documented
    fetch_all_real_expirations() pagination-undercount bug -- this project's
    own local, already-fixed analog is the GEX JSON:API pagination fix,
    CLAUDE.md Section 4/8).

Writes the full report to broader_universe_feasibility_report.md.
Prints only short progress lines to the console.
"""

import json
import math
import time
from datetime import datetime, timezone

import numpy as np
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
import os

from gex_data_loader import _fetch_raw_chain_paginated

api_key = os.environ["ALPACA_API_KEY"]
secret_key = os.environ["ALPACA_SECRET_KEY"]
client = StockHistoricalDataClient(api_key, secret_key)

EXISTING_SIX = ["AAPL", "AMD", "MSTR", "NVDA", "SMCI", "TSLA"]

# A deliberately broad, diverse candidate list -- large/liquid, optionable
# US equities spanning multiple sectors, NOT hand-picked for favorable
# results (no volatility-prediction outcome has been examined at any point
# in choosing this list).
CANDIDATES = [
    # megacap tech
    "MSFT", "GOOGL", "AMZN", "META",
    # semis
    "AVGO", "INTC", "MU", "QCOM", "TXN", "LRCX", "AMAT", "ASML", "ARM",
    # EV / auto
    "F", "GM", "RIVN", "LCID", "NIO",
    # consumer / retail
    "WMT", "COST", "TGT", "NKE", "SBUX", "MCD", "HD", "DIS",
    # financials / payments
    "JPM", "BAC", "GS", "MS", "V", "MA", "PYPL", "SOFI",
    # healthcare / pharma
    "UNH", "JNJ", "PFE", "LLY", "MRNA",
    # energy / industrial
    "XOM", "CVX", "OXY", "BA", "CAT", "GE",
    # crypto-adjacent (matching MSTR's existing category)
    "COIN", "RIOT", "MARA",
    # high-vol / momentum names, comparable vol profile to SMCI
    "PLTR", "SNAP", "ROKU", "DKNG", "AFRM",
]

STAGE1_PROBE_DATES = ["2023-10-02", "2024-06-03", "2025-06-02", "2026-09-01"]
KNOWN_CLIFF_BEFORE = "2023-09-29"  # confirmed zero-record real Friday, per Section 44's original bisection


def log(msg):
    print(f"[{datetime.now().isoformat()}] {msg}", flush=True)


def fetch_alpaca_underlying(ticker):
    try:
        req = StockBarsRequest(
            symbol_or_symbols=ticker, timeframe=TimeFrame(1, TimeFrameUnit.Day),
            start=datetime(2015, 1, 1, tzinfo=timezone.utc), end=datetime.now(timezone.utc),
            feed=DataFeed.IEX, adjustment=Adjustment.RAW,
        )
        bars = list(client.get_stock_bars(req)[ticker])
        if not bars:
            return {"ok": False, "reason": "zero bars returned"}
        dates = sorted(set(b.timestamp.date() for b in bars))
        gaps = []
        for i in range(1, len(dates)):
            delta = (dates[i] - dates[i - 1]).days
            if delta > 4:
                gaps.append((str(dates[i - 1]), str(dates[i]), delta))
        return {
            "ok": True, "n_bars": len(bars), "n_distinct_days": len(dates),
            "earliest": str(dates[0]), "latest": str(dates[-1]),
            "n_gaps_gt4d": len(gaps), "gap_detail": gaps[:5],
        }
    except Exception as exc:
        return {"ok": False, "reason": f"exception: {exc}"}


def eodhd_options_probe(ticker, date_str):
    """One id-date-safe, fully-paginated probe at a specific date. Returns
    real counts, distinguishing raw contract rows from usable (id-date-
    matched, volatility+strike+exp_date present) records, and explicitly
    reports pagination_complete/pages_requested for this exact call."""
    try:
        fetch_result = _fetch_raw_chain_paginated(ticker, date_str)
    except Exception as exc:
        return {"ok": False, "reason": f"exception: {exc}", "pagination_complete": None, "pages_requested": None}

    pages_requested = fetch_result["pages_requested"]
    pagination_complete = fetch_result["pagination_complete"]
    raw_records = fetch_result["records"]
    id_matched = [r.get("attributes", {}) for r in raw_records if str(r.get("id", "")).endswith("-" + date_str)]
    usable = [a for a in id_matched if a.get("volatility") is not None and a.get("volatility", 0) > 0
              and a.get("strike") is not None and a.get("exp_date") is not None]
    calls = [a for a in usable if a.get("type") == "call"]
    puts = [a for a in usable if a.get("type") == "put"]
    return {
        "ok": True,
        "pagination_complete": pagination_complete, "pages_requested": pages_requested,
        "n_raw_records": len(raw_records), "n_id_matched": len(id_matched),
        "n_usable": len(usable), "n_usable_calls": len(calls), "n_usable_puts": len(puts),
        "has_both_sides": len(calls) > 0 and len(puts) > 0,
    }


def bisect_earliest_options_date(ticker, lo_str, hi_str, max_iter=12):
    """Confirms (or refutes) the known 2023-10-02 cliff for a NEW candidate
    via real bisection, not assumption. lo=known-empty date, hi=known-
    populated date."""
    lo = datetime.strptime(lo_str, "%Y-%m-%d").date()
    hi = datetime.strptime(hi_str, "%Y-%m-%d").date()
    history = []
    for _ in range(max_iter):
        if (hi - lo).days <= 1:
            break
        mid = lo + (hi - lo) // 2
        mid_str = mid.isoformat()
        r = eodhd_options_probe(ticker, mid_str)
        populated = r["ok"] and r["n_usable"] > 0
        history.append((mid_str, populated, r.get("n_usable")))
        if populated:
            hi = mid
        else:
            lo = mid
    return hi.isoformat(), history


def main():
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "candidates": {}}

    log(f"=== Phase A: Alpaca underlying-price feasibility, {len(CANDIDATES)} candidates ===")
    for i, t in enumerate(CANDIDATES):
        r = fetch_alpaca_underlying(t)
        report["candidates"].setdefault(t, {})["alpaca"] = r
        status = "OK" if r["ok"] else f"FAIL ({r.get('reason')})"
        log(f"  [{i+1}/{len(CANDIDATES)}] {t}: {status}" + (f" earliest={r.get('earliest')} n_days={r.get('n_distinct_days')}" if r["ok"] else ""))

    alpaca_survivors = [t for t in CANDIDATES if report["candidates"][t]["alpaca"]["ok"]]
    log(f"\nAlpaca survivors: {len(alpaca_survivors)}/{len(CANDIDATES)}")

    log(f"\n=== Phase B: EODHD options existence probe at {STAGE1_PROBE_DATES} for {len(alpaca_survivors)} Alpaca survivors ===")
    for i, t in enumerate(alpaca_survivors):
        probes = {}
        for d in STAGE1_PROBE_DATES:
            probes[d] = eodhd_options_probe(t, d)
            time.sleep(0.05)
        report["candidates"][t]["eodhd_probes"] = probes
        summary = " | ".join(f"{d}:{probes[d].get('n_usable', 'ERR')}({'complete' if probes[d].get('pagination_complete') else 'INCOMPLETE' if probes[d].get('pagination_complete') is False else '?'})" for d in STAGE1_PROBE_DATES)
        log(f"  [{i+1}/{len(alpaca_survivors)}] {t}: {summary}")

    # Tickers usable at the ORIGINAL 2023-10-02 cliff AND still populated in 2026
    cliff_confirmed = []
    for t in alpaca_survivors:
        probes = report["candidates"][t]["eodhd_probes"]
        if all(probes[d]["ok"] and probes[d]["n_usable"] > 0 for d in STAGE1_PROBE_DATES):
            cliff_confirmed.append(t)
    log(f"\nTickers with usable EODHD options data at ALL 4 probe dates (2023-10-02 through 2026-09-01): {len(cliff_confirmed)}/{len(alpaca_survivors)}")

    # For tickers that FAILED at 2023-10-02 specifically but passed later dates, bisect their real start
    log("\n=== Phase C: bisection for candidates that failed the 2023-10-02 probe but passed later ones (real IPO/options-listing lag, not assumed) ===")
    late_starters = []
    for t in alpaca_survivors:
        probes = report["candidates"][t]["eodhd_probes"]
        failed_2023 = not (probes["2023-10-02"]["ok"] and probes["2023-10-02"]["n_usable"] > 0)
        passed_later = probes["2026-09-01"]["ok"] and probes["2026-09-01"]["n_usable"] > 0
        if failed_2023 and passed_later:
            late_starters.append(t)
    log(f"Late-starter candidates needing bisection: {late_starters}")
    for t in late_starters:
        hi, history = bisect_earliest_options_date(t, "2023-01-01", "2026-09-01")
        report["candidates"][t]["bisected_earliest_options_date"] = hi
        report["candidates"][t]["bisection_history"] = history
        log(f"  {t}: bisected earliest usable options date ~= {hi}")

    log("\n=== Phase D: cross-sectional coverage at each of the 4 probe dates, across ALL Alpaca survivors + the existing 6 ===")
    full_universe = EXISTING_SIX + alpaca_survivors
    cross_sectional = {}
    for d in STAGE1_PROBE_DATES:
        n_available = 0
        available_tickers = []
        for t in full_universe:
            if t in EXISTING_SIX:
                # already confirmed populated at these exact dates in earlier sessions; probe fresh anyway, cheap
                r = eodhd_options_probe(t, d)
                report["candidates"].setdefault(t, {}).setdefault("eodhd_probes", {})[d] = r
            else:
                r = report["candidates"][t]["eodhd_probes"][d]
            if r["ok"] and r["n_usable"] > 0 and r.get("has_both_sides"):
                n_available += 1
                available_tickers.append(t)
        cross_sectional[d] = {"n_available": n_available, "n_total_universe": len(full_universe), "available_tickers": available_tickers}
        log(f"  {d}: {n_available}/{len(full_universe)} tickers have usable (both-sides) options data")

    report["cross_sectional_coverage"] = cross_sectional
    report["alpaca_survivors"] = alpaca_survivors
    report["cliff_confirmed_all_4_dates"] = cliff_confirmed
    report["late_starters"] = late_starters
    report["full_universe_considered"] = full_universe

    with open("broader_universe_feasibility_raw.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log("\nRaw data written to broader_universe_feasibility_raw.json")


if __name__ == "__main__":
    main()

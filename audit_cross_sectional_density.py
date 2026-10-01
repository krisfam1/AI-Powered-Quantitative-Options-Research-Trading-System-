from dotenv import load_dotenv
load_dotenv()

"""
Supplementary pass to audit_broader_universe_feasibility.py: the original
4-date cross-sectional check (100% coverage at all 4) is too sparse to
report a genuine empirical distribution (median/min tickers-per-date,
% of dates meeting a threshold) as explicitly requested. This adds 12 more
evenly-spaced real calendar dates across the ~2023-10-02 to 2026-09-01
common window, for the full 59-ticker candidate universe (existing 6 +
53 new candidates), using the SAME validated, fully-paginated
_fetch_raw_chain_paginated() method, with the same pagination_complete
check on every call.
"""

import json
import time
from datetime import datetime, timezone

from gex_data_loader import _fetch_raw_chain_paginated

EXISTING_SIX = ["AAPL", "AMD", "MSTR", "NVDA", "SMCI", "TSLA"]
with open("broader_universe_feasibility_raw.json", encoding="utf-8") as f:
    prior = json.load(f)
ALPACA_SURVIVORS = prior["alpaca_survivors"]
FULL_UNIVERSE = EXISTING_SIX + ALPACA_SURVIVORS

ADDITIONAL_DATES = [
    "2023-12-15", "2024-02-15", "2024-04-15", "2024-08-15", "2024-10-15",
    "2024-12-16", "2025-02-18", "2025-04-15", "2025-08-15", "2025-10-15",
    "2025-12-15", "2026-06-15",
]


def log(msg):
    print(f"[{datetime.now().isoformat()}] {msg}", flush=True)


def eodhd_options_probe(ticker, date_str):
    try:
        fetch_result = _fetch_raw_chain_paginated(ticker, date_str)
    except Exception as exc:
        return {"ok": False, "reason": f"exception: {exc}", "pagination_complete": None}
    pages_requested = fetch_result["pages_requested"]
    pagination_complete = fetch_result["pagination_complete"]
    raw_records = fetch_result["records"]
    id_matched = [r.get("attributes", {}) for r in raw_records if str(r.get("id", "")).endswith("-" + date_str)]
    usable = [a for a in id_matched if a.get("volatility") is not None and a.get("volatility", 0) > 0
              and a.get("strike") is not None and a.get("exp_date") is not None]
    calls = [a for a in usable if a.get("type") == "call"]
    puts = [a for a in usable if a.get("type") == "put"]
    return {"ok": True, "pagination_complete": pagination_complete, "pages_requested": pages_requested,
            "n_usable": len(usable), "has_both_sides": len(calls) > 0 and len(puts) > 0}


def main():
    log(f"Universe size: {len(FULL_UNIVERSE)}. Additional dates: {len(ADDITIONAL_DATES)}.")
    density_results = {}
    incomplete_pagination_events = []
    for d in ADDITIONAL_DATES:
        n_available = 0
        available = []
        for t in FULL_UNIVERSE:
            r = eodhd_options_probe(t, d)
            if r["ok"] and r.get("pagination_complete") is False:
                incomplete_pagination_events.append((t, d, r))
            if r["ok"] and r["n_usable"] > 0 and r.get("has_both_sides"):
                n_available += 1
                available.append(t)
            time.sleep(0.03)
        density_results[d] = {"n_available": n_available, "n_total": len(FULL_UNIVERSE), "missing": sorted(set(FULL_UNIVERSE) - set(available))}
        log(f"  {d}: {n_available}/{len(FULL_UNIVERSE)} available" + (f" -- MISSING: {density_results[d]['missing']}" if density_results[d]["missing"] else ""))

    log(f"\nIncomplete-pagination events across this whole pass: {len(incomplete_pagination_events)}")
    for ev in incomplete_pagination_events[:20]:
        log(f"  {ev}")

    with open("cross_sectional_density_raw.json", "w", encoding="utf-8") as f:
        json.dump({"density_results": density_results, "incomplete_pagination_events": incomplete_pagination_events, "universe": FULL_UNIVERSE}, f, indent=2, default=str)
    log("Written to cross_sectional_density_raw.json")


if __name__ == "__main__":
    main()

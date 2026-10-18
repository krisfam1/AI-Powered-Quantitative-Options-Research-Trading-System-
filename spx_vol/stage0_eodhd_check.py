"""Stage 0: one read-only EODHD coverage check (approved 2026-10-17).

Does EODHD's options add-on carry SPX, SPXW or VIX options, and from what date?
Hard budget of 20 requests; stops at the first 429 or other quota error.
The token is loaded from .env via python-dotenv and is never printed or saved;
errors print the exception type and status only, never the URL.
"""
import json
import os
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT / ".env")
TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE = "https://eodhd.com/api/mp/unicornbay/options"
BUDGET = 20
OUT = PROJECT / "data_snapshots" / "spx_vol_engine" / "eodhd_check" / "eodhd_coverage_check.json"

used = 0
log = []


class Stop(RuntimeError):
    pass


def call(path, params):
    global used
    if used >= BUDGET:
        raise Stop("budget reached")
    used += 1
    try:
        r = requests.get(f"{BASE}/{path}", params={**params, "api_token": TOKEN}, timeout=120)
    except requests.RequestException as exc:
        log.append({"n": used, "path": path, "params": params, "error": type(exc).__name__})
        raise Stop(type(exc).__name__)
    entry = {"n": used, "path": path, "params": params, "status": r.status_code}
    log.append(entry)
    if r.status_code in (401, 402, 403, 429):
        raise Stop(f"HTTP {r.status_code}")
    if r.status_code != 200:
        return None
    return r.json()


def records_on(sym, d):
    """Count of records (first page only, limit 1) for an underlying on one trade date."""
    js = call("eod", {"filter[underlying_symbol]": sym, "filter[tradetime_from]": d.isoformat(),
                      "filter[tradetime_to]": d.isoformat(), "page[limit]": 1})
    if not js:
        return 0, None
    data = js.get("data") or []
    total = (js.get("meta") or {}).get("total")
    rec = data[0].get("attributes", {}) if data else None
    return (total if total is not None else len(data)), rec


def main():
    result = {"checked_on": date.today().isoformat(), "symbols": {}}
    try:
        js = call("underlying-symbols", {})
        raw = js.get("data", []) if isinstance(js, dict) else (js or [])
        syms = [s if isinstance(s, str) else s.get("id") or s.get("attributes", {}).get("symbol")
                for s in raw]
        result["underlying_symbols_count"] = len(syms)
        listed = {s.upper() for s in syms if s}
        hits = [s for s in ("SPX", "SPXW", "VIX", "XSP", "VIXW") if s in listed]
        result["matching_underlyings"] = hits
        print("underlying symbols listed:", len(syms), "matches:", hits)
        # Recent business day to confirm records exist at all, then a coarse back-search.
        probe_days = [date(2026, 10, 15), date(2025, 10, 15), date(2024, 10, 15),
                      date(2023, 10, 16), date(2022, 10, 17), date(2021, 10, 15)]
        for sym in hits:
            info = {}
            for d in probe_days:
                n, rec = records_on(sym, d)
                info[d.isoformat()] = n
                if rec and "example" not in info:
                    info["example"] = {k: rec.get(k) for k in
                                       ("contract", "exp_date", "type", "strike", "bid", "ask",
                                        "volatility", "delta", "open_interest", "tradetime")}
                print(sym, d, n)
                if n == 0 and d.year < 2026:
                    break
            result["symbols"][sym] = info
    except Stop as exc:
        result["stopped"] = str(exc)
        print("STOPPED:", exc)
    result["requests_used"] = used
    result["request_log"] = log
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1, default=str))
    print("requests used:", used)


if __name__ == "__main__":
    main()

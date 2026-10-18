"""Stage 0 follow-up to stage0_eodhd_check.py (same 20-request total budget; 1 already used).

Re-reads the underlying-symbols list to look for other spellings (substring SPX / VIX / XSP),
then queries SPX and VIX directly for one recent date. Token never printed or saved.
"""
import json
from datetime import date

import stage0_eodhd_check as c

c.used = 1  # the first run used 1 request
OUT = c.OUT.with_name("eodhd_coverage_check_followup.json")


def main():
    result = {"checked_on": date.today().isoformat()}
    try:
        js = c.call("underlying-symbols", {})
        raw = js.get("data", []) if isinstance(js, dict) else (js or [])
        syms = [s if isinstance(s, str) else s.get("id") or s.get("attributes", {}).get("symbol")
                for s in raw]
        near = sorted(s for s in syms if s and any(k in s.upper() for k in ("SPX", "VIX", "XSP", "GSPC")))
        result["substring_matches"] = near
        result["spy_listed"] = "SPY" in {s.upper() for s in syms if s}
        print("substring matches:", near, "SPY listed:", result["spy_listed"])
        for sym in ("SPX", "VIX"):
            n, rec = c.records_on(sym, date(2026, 10, 15))
            result[f"direct_{sym}_2026-10-15"] = n
            print("direct", sym, n)
    except c.Stop as exc:
        result["stopped"] = str(exc)
        print("STOPPED:", exc)
    result["requests_used_total"] = c.used
    result["request_log"] = c.log
    OUT.write_text(json.dumps(result, indent=1, default=str))
    print("requests used total:", c.used)


if __name__ == "__main__":
    main()

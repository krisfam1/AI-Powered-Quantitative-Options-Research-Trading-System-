"""
Earnings release dates from SEC EDGAR (free, official, no API key) -> earnings_dates.db.

Decision 2026-10-01: EODHD's plan has no earnings calendar (HTTP 403, "Only EOD data allowed for free
users"). EDGAR's submissions API tags US issuers' earnings releases as 8-K Item 2.02 ("Results of
Operations and Financial Condition"), with an exact acceptance timestamp.

Session rule: a release accepted at/after 16:00 ET affects the NEXT trading session; one accepted before
09:30 ET affects the same session; one accepted during market hours is attributed to the same session.

Foreign private issuers (e.g. ASML, ARM, NIO) file untagged 6-Ks, so their earnings dates are NOT
derivable here; they are recorded in edgar_coverage with status 'foreign_6k_unknown' and the backtester
must treat their earnings exposure as unknown.
Usage: python earnings_dates_edgar.py   (idempotent; refetches everything, ~1 req per ticker, 10 req/s limit)
"""
import os, sqlite3, time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, "earnings_dates.db")
H = {"User-Agent": "fmkris05 options-research fmkris05@gmail.com"}
ET = ZoneInfo("America/New_York")
SINCE = "2022-06-01"


def tickers():
    from generate_broader_universe_volatility_dataset import TICKERS
    return list(TICKERS) + ["SPY"]


def main():
    from straddle_schedule import trading_days
    days = trading_days(start=date(2022, 1, 1))
    cikmap = {v["ticker"]: v["cik_str"] for v in
              requests.get("https://www.sec.gov/files/company_tickers.json", headers=H, timeout=30).json().values()}
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS earnings (ticker TEXT, filing_date TEXT, acceptance_utc TEXT,
                 acceptance_et TEXT, session_date TEXT, timing TEXT, form TEXT, items TEXT,
                 UNIQUE(ticker, acceptance_utc))""")
    c.execute("""CREATE TABLE IF NOT EXISTS edgar_coverage (ticker TEXT PRIMARY KEY, cik INTEGER, status TEXT,
                 n_releases INTEGER, earliest TEXT, latest TEXT, fetched_at TEXT)""")
    for t in tickers():
        cik = cikmap.get(t)
        status, rows = None, []
        if t == "SPY":
            status = "etf_no_earnings"
        elif not cik:
            status = "no_cik"
        else:
            j = requests.get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", headers=H, timeout=30).json()
            f = {k: list(v) for k, v in j["filings"]["recent"].items()}
            # heavy filers: "recent" holds only the last 1,000 filings; older ones sit in paged files
            for older in j["filings"].get("files", []):
                if older.get("filingTo", "9999") >= SINCE:
                    time.sleep(0.15)
                    o = requests.get("https://data.sec.gov/submissions/" + older["name"], headers=H, timeout=30).json()
                    for k in ("form", "items", "filingDate", "acceptanceDateTime"):
                        f[k].extend(o[k])
            forms = set(f["form"])
            for i, form in enumerate(f["form"]):
                if form in ("8-K", "8-K/A") and "2.02" in f["items"][i].split(",") and f["filingDate"][i] >= SINCE:
                    acc_utc = datetime.fromisoformat(f["acceptanceDateTime"][i].replace("Z", "+00:00"))
                    acc_et = acc_utc.astimezone(ET)
                    hm = acc_et.hour * 60 + acc_et.minute
                    d = acc_et.date()
                    if hm >= 16 * 60 or d not in days:
                        sess, timing = next(x for x in days if x > d), "after_close"
                    elif hm < 9 * 60 + 30:
                        sess, timing = d, "before_open"
                    else:
                        sess, timing = d, "intraday"
                    rows.append((t, f["filingDate"][i], acc_utc.isoformat(), acc_et.isoformat(), sess.isoformat(),
                                 timing, form, f["items"][i]))
            if len([r for r in rows if r[1] >= "2023-10-01"]) < 8:
                # e.g. XOM files its results under other items: too sparse to trust -> unknown
                status = "foreign_6k_unknown" if not rows and ("6-K" in forms or "20-F" in forms) \
                    else "sparse_item_2_02_unknown"
            elif rows:
                status = "ok"
                if min(f["filingDate"]) > SINCE:   # still truncated even after the paged files
                    status = "ok_recent_window_may_be_truncated"
            elif "6-K" in forms or "20-F" in forms:
                status = "foreign_6k_unknown"
            else:
                status = "no_item_2_02_found"
            time.sleep(0.15)
        c.executemany("INSERT OR IGNORE INTO earnings VALUES (?,?,?,?,?,?,?,?)", rows)
        dates = sorted(r[5 - 1] for r in rows)
        c.execute("INSERT OR REPLACE INTO edgar_coverage VALUES (?,?,?,?,?,?,?)",
                  (t, cik, status, len(rows), dates[0] if dates else None, dates[-1] if dates else None,
                   datetime.now().isoformat(timespec="seconds")))
        c.commit()
        print(f"{t:6} {status:34} releases={len(rows)}")
    c.close()


if __name__ == "__main__":
    main()

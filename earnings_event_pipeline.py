"""
Data pipeline for hypothesis #14 (earnings implied-vs-historical move, "F1"), Phase 1 only:
build -> collect -> integrity checks -> freeze. Approved by the user 2026-10-06; design in the study
"Final Hypothesis Slot: Options Research Study" (Sections 15-19) and CLAUDE.md Section 64.

    python earnings_event_pipeline.py universe     # S&P 500 + Nasdaq-100 as of 2023-10-01 (+ project 59)
    python earnings_event_pipeline.py edgar        # 8-K Item 2.02 acceptance times, 2021-06 -> 2026-09
    python earnings_event_pipeline.py prices       # Alpaca SIP daily raw + split-adjusted closes
    python earnings_event_pipeline.py events       # event table (timing, sessions, AvgEA, HV252, splits) - no options
    python earnings_event_pipeline.py budget       # EODHD requests the option stage would need
    python earnings_event_pipeline.py options      # EODHD snapshots (resumable, stops on the first 429)
    python earnings_event_pipeline.py integrity    # screen counts and data checks - NO option returns computed
    python earnings_event_pipeline.py freeze       # per-table SHA-256 manifest

Writes ONLY earnings_event_dataset.db (and its manifest). Never touches option_snapshots.db,
research_database.db or any open experiment. Nothing here computes a straddle return or relates the
signal to any outcome: those belong to the registered execution script, after the freeze.

API keys are loaded with load_dotenv(), like every other project script; their values are never printed or logged.
"""
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

load_dotenv()   # same pattern as every other project script: loads keys into the process; the file is never printed

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, "earnings_event_dataset.db")
LOCK = os.path.join(ROOT, "earnings_event_options.lock")
ET = ZoneInfo("America/New_York")
SEC_H = {"User-Agent": "fmkris05 options-research fmkris05@gmail.com"}   # same header as earnings_dates_edgar.py
WIKI_H = {"User-Agent": "options-research-pipeline/1.0 (point-in-time index membership)"}
EODHD_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"

AS_OF = "2023-10-01T00:00:00Z"            # universe snapshot date (approved)
EDGAR_SINCE = "2021-06-01"
PRICE_START = date(2021, 6, 1)
PRICE_END = date(2026, 10, 2)
STAGE1_FIRST_R = date(2023, 11, 1)        # reaction sessions, Stage 1 (approved)
STAGE1_LAST_R = date(2026, 9, 30)
EXPIRY_MAX_DAYS = 7                       # expiry in [R, R+7 calendar days]
ENTRY_STRIKE_BAND = 0.10                  # entry request strikes within +/-10% of the raw close
PLACEBO_LAG = 10                          # placebo entry = 10 sessions before t0
LOOKBACK = 4
DEDUPE_SESSIONS = 5


def db():
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS universe (ticker TEXT PRIMARY KEY, source TEXT, cik INTEGER, name TEXT, note TEXT);
    CREATE TABLE IF NOT EXISTS universe_sources (page TEXT PRIMARY KEY, revid INTEGER, rev_timestamp TEXT, n_rows INTEGER, fetched_at TEXT);
    CREATE TABLE IF NOT EXISTS edgar_events (ticker TEXT, cik INTEGER, form TEXT, filing_date TEXT, acceptance_utc TEXT,
        acceptance_et TEXT, session_date TEXT, timing TEXT, UNIQUE(cik, acceptance_utc));
    CREATE TABLE IF NOT EXISTS edgar_coverage (ticker TEXT PRIMARY KEY, cik INTEGER, status TEXT, n_events INTEGER, fetched_at TEXT);
    CREATE TABLE IF NOT EXISTS closes (ticker TEXT, d TEXT, raw REAL, adj REAL, PRIMARY KEY (ticker, d));
    CREATE TABLE IF NOT EXISTS price_coverage (ticker TEXT PRIMARY KEY, status TEXT, n_days INTEGER, first_d TEXT, last_d TEXT);
    CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY, ticker TEXT, cik INTEGER, acceptance_et TEXT, timing TEXT,
        reaction_session TEXT, entry_session TEXT, placebo_entry TEXT, placebo_exit TEXT, stage TEXT,
        avgea4 REAL, avgea8 REAL, std4 REAL, n_prior INTEGER, hv252 REAL, raw_close_t0 REAL, raw_close_p REAL,
        split_in_window INTEGER, split_in_placebo INTEGER, status TEXT);
    CREATE TABLE IF NOT EXISTS option_quotes (event_id TEXT, kind TEXT, obs_date TEXT, contract TEXT, option_type TEXT,
        strike REAL, exp_date TEXT, expiration_type TEXT, bid REAL, ask REAL, volume REAL, open_interest REAL, iv REAL,
        delta REAL, quote_ts TEXT, UNIQUE(event_id, kind, contract));
    CREATE TABLE IF NOT EXISTS option_requests (event_id TEXT, kind TEXT, obs_date TEXT, symbol TEXT, pages INTEGER,
        records INTEGER, kept INTEGER, complete INTEGER, error TEXT, fetched_at TEXT, PRIMARY KEY (event_id, kind));
    """)
    return c


def calendar(start=date(2021, 1, 1), end=date(2026, 12, 31)):
    from straddle_schedule import trading_days      # Alpaca market calendar (module loads its own env)
    return [d for d in trading_days(start=start, end=end)]


# ----------------------------------------------------------------------------- universe
def _wiki_table(page, revid):
    from bs4 import BeautifulSoup
    html = requests.get("https://en.wikipedia.org/w/index.php", params={"oldid": revid}, headers=WIKI_H, timeout=60).text
    soup = BeautifulSoup(html, "html.parser")
    best = None
    for t in soup.find_all("table", class_="wikitable"):
        heads = [th.get_text(" ", strip=True) for th in t.find("tr").find_all(["th", "td"])]
        col = next((i for i, h in enumerate(heads) if h.lower() in ("symbol", "ticker")), None)
        if col is None:
            continue
        rows = []
        for tr in t.find_all("tr")[1:]:
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
            if len(cells) > col and cells[col]:
                cik = next((int(x) for x in cells if re.fullmatch(r"0*\d{6,10}", x or "")), None)
                rows.append((cells[col].replace("​", "").strip(), cells[col + 1] if len(cells) > col + 1 else "", cik))
        if best is None or len(rows) > len(best):
            best = rows
    return best or []


def stage_universe():
    c = db()
    out = {}
    for page in ("List of S&P 500 companies", "Nasdaq-100"):
        j = requests.get("https://en.wikipedia.org/w/api.php", headers=WIKI_H, timeout=60, params={
            "action": "query", "prop": "revisions", "titles": page, "rvlimit": 1, "rvstart": AS_OF,
            "rvdir": "older", "rvprop": "ids|timestamp", "format": "json"}).json()
        rev = next(iter(j["query"]["pages"].values()))["revisions"][0]
        rows = _wiki_table(page, rev["revid"])
        c.execute("INSERT OR REPLACE INTO universe_sources VALUES (?,?,?,?,?)",
                  (page, rev["revid"], rev["timestamp"], len(rows), datetime.now(timezone.utc).isoformat()))
        for sym, name, cik in rows:
            src = "sp500" if page.startswith("List") else "ndx100"
            prev = out.get(sym)
            out[sym] = (sym, src if not prev else prev[1] + "+" + src, cik or (prev[2] if prev else None), name or (prev[3] if prev else ""))
        print(f"{page}: revision {rev['revid']} ({rev['timestamp']}), {len(rows)} rows")
    from generate_broader_universe_volatility_dataset import TICKERS
    for t in TICKERS:
        if t not in out:
            out[t] = (t, "project59", None, "")
        elif "project59" not in out[t][1]:
            out[t] = (out[t][0], out[t][1] + "+project59", out[t][2], out[t][3])
    c.execute("DELETE FROM universe")
    c.executemany("INSERT INTO universe VALUES (?,?,?,?,NULL)", list(out.values()))
    c.commit()
    print(f"universe: {len(out)} tickers ({sum('sp500' in v[1] for v in out.values())} S&P 500, "
          f"{sum('ndx100' in v[1] for v in out.values())} Nasdaq-100, {sum(v[1] == 'project59' for v in out.values())} project-only)")


# ----------------------------------------------------------------------------- EDGAR
def stage_edgar():
    c = db()
    days = calendar()
    dayset = set(days)
    cikmap = {v["ticker"].replace("-", "."): v["cik_str"] for v in
              requests.get("https://www.sec.gov/files/company_tickers.json", headers=SEC_H, timeout=30).json().values()}
    for t, cik in c.execute("SELECT ticker, cik FROM universe ORDER BY ticker").fetchall():
        cik = cik or cikmap.get(t)
        if not cik:
            c.execute("INSERT OR REPLACE INTO edgar_coverage VALUES (?,?,?,?,?)", (t, None, "no_cik", 0, _now())); c.commit()
            continue
        try:
            j = _get_json(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json")
            f = {k: list(v) for k, v in j["filings"]["recent"].items()}
            for older in j["filings"].get("files", []):
                if older.get("filingTo", "9999") >= EDGAR_SINCE:
                    o = _get_json("https://data.sec.gov/submissions/" + older["name"])
                    for k in ("form", "items", "filingDate", "acceptanceDateTime"):
                        f[k].extend(o[k])
        except Exception as exc:
            c.execute("INSERT OR REPLACE INTO edgar_coverage VALUES (?,?,?,?,?)", (t, cik, f"error: {exc}"[:200], 0, _now())); c.commit()
            continue
        rows, forms = [], set(f["form"])
        for i, form in enumerate(f["form"]):
            if form in ("8-K", "8-K/A") and "2.02" in f["items"][i].split(",") and f["filingDate"][i] >= EDGAR_SINCE:
                acc_utc = datetime.fromisoformat(f["acceptanceDateTime"][i].replace("Z", "+00:00"))
                acc_et = acc_utc.astimezone(ET)
                hm, d = acc_et.hour * 60 + acc_et.minute, acc_et.date()
                if hm >= 16 * 60 or d not in dayset:
                    sess, timing = next((x for x in days if x > d), None), "after_close"
                elif hm < 9 * 60 + 30:
                    sess, timing = d, "before_open"
                else:
                    sess, timing = d, "intraday"
                rows.append((t, int(cik), form, f["filingDate"][i], acc_utc.isoformat(), acc_et.isoformat(),
                             sess.isoformat() if sess else None, timing))
        c.executemany("INSERT OR IGNORE INTO edgar_events VALUES (?,?,?,?,?,?,?,?)", rows)
        n8k = sum(r[2] == "8-K" for r in rows)
        status = "ok" if n8k else ("foreign_6k" if ("6-K" in forms or "20-F" in forms) else "no_item_2_02")
        c.execute("INSERT OR REPLACE INTO edgar_coverage VALUES (?,?,?,?,?)", (t, int(cik), status, n8k, _now()))
        c.commit()
    print(dict(c.execute("SELECT status, COUNT(*) FROM edgar_coverage GROUP BY 1").fetchall()),
          "events:", c.execute("SELECT COUNT(*) FROM edgar_events WHERE form='8-K'").fetchone()[0])


def _get_json(url):
    for attempt in range(4):
        time.sleep(0.12)                                   # SEC limit is 10 requests/second
        r = requests.get(url, headers=SEC_H, timeout=30)
        if r.status_code == 200:
            return r.json()
        time.sleep(2 ** attempt)
    r.raise_for_status()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ----------------------------------------------------------------------------- prices
def stage_prices():
    from straddle_schedule import trading_days  # noqa: F401  (ensures env is loaded the same way)
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.enums import Adjustment, DataFeed
    cl = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
    c = db()
    done = {r[0] for r in c.execute("SELECT ticker FROM price_coverage WHERE status='ok'")}
    tickers = [r[0] for r in c.execute("SELECT DISTINCT ticker FROM edgar_events WHERE form='8-K'")] + \
              [r[0] for r in c.execute("SELECT ticker FROM universe")]
    for t in sorted(set(tickers) - done):
        series = {}
        try:
            for adj in (Adjustment.RAW, Adjustment.SPLIT):
                bars = cl.get_stock_bars(StockBarsRequest(symbol_or_symbols=t, timeframe=TimeFrame.Day, adjustment=adj,
                                         feed=DataFeed.SIP, start=datetime.combine(PRICE_START, datetime.min.time()),
                                         end=datetime.combine(PRICE_END, datetime.min.time())))
                series[adj] = {b.timestamp.astimezone(ET).date().isoformat(): float(b.close) for b in bars.data.get(t, [])}
        except Exception as exc:
            c.execute("INSERT OR REPLACE INTO price_coverage VALUES (?,?,?,?,?)", (t, f"error: {exc}"[:200], 0, None, None)); c.commit()
            continue
        rows = [(t, d, series[Adjustment.RAW][d], series[Adjustment.SPLIT].get(d)) for d in series[Adjustment.RAW]]
        c.executemany("INSERT OR REPLACE INTO closes VALUES (?,?,?,?)", rows)
        ds = sorted(series[Adjustment.RAW])
        c.execute("INSERT OR REPLACE INTO price_coverage VALUES (?,?,?,?,?)",
                  (t, "ok" if rows else "no_bars", len(rows), ds[0] if ds else None, ds[-1] if ds else None))
        c.commit()
    print(dict(c.execute("SELECT status, COUNT(*) FROM price_coverage GROUP BY substr(status,1,5)").fetchall()))


# ----------------------------------------------------------------------------- events
def stage_events():
    c = db()
    days = calendar()
    idx = {d.isoformat(): i for i, d in enumerate(days)}
    closes = {}
    for t, d, raw, adj in c.execute("SELECT ticker, d, raw, adj FROM closes"):
        closes.setdefault(t, {})[d] = (raw, adj)
    ev = {}
    for t, cik, acc_et, sess, timing in c.execute(
            "SELECT ticker, cik, acceptance_et, session_date, timing FROM edgar_events WHERE form='8-K' AND session_date IS NOT NULL "
            "ORDER BY ticker, acceptance_et"):
        ev.setdefault(t, []).append((acc_et, sess, timing, cik))
    rows = []
    for t, lst in ev.items():
        kept = []                                           # dedupe: a second 8-K within 5 sessions of the first is dropped
        for e in lst:
            if kept and e[1] in idx and kept[-1][1] in idx and idx[e[1]] - idx[kept[-1][1]] < DEDUPE_SESSIONS:
                continue
            kept.append(e)
        px = closes.get(t, {})

        def lr(i_sess):                                     # |log return| from the prior session's close to this one's
            d1, d0 = days[i_sess].isoformat(), days[i_sess - 1].isoformat()
            if d1 in px and d0 in px and px[d1][1] and px[d0][1]:
                return abs(math.log(px[d1][1] / px[d0][1]))
            return None
        for k, (acc_et, sess, timing, cik) in enumerate(kept):
            R = date.fromisoformat(sess)
            if not (STAGE1_FIRST_R <= R <= STAGE1_LAST_R) or sess not in idx:
                continue
            iR = idx[sess]
            t0, P, P1 = days[iR - 1], days[iR - 1 - PLACEBO_LAG], days[iR - PLACEBO_LAG]
            prior = [idx[x[1]] for x in kept[:k] if x[1] in idx and idx[x[1]] < iR - 1]   # reactions strictly before t0
            moves = [m for m in (lr(i) for i in prior) if m is not None]
            m4, m8 = moves[-LOOKBACK:], moves[-8:]
            hv = None
            ws = [days[j].isoformat() for j in range(iR - 1 - 252, iR)]
            if all(d in px and px[d][1] for d in ws):
                rets = [math.log(px[b][1] / px[a][1]) for a, b in zip(ws, ws[1:])]
                mu = sum(rets) / len(rets)
                hv = math.sqrt(sum((x - mu) ** 2 for x in rets) / (len(rets) - 1) * 252)

            def split(a, b):                                # raw/adjusted ratio changes inside [a, b] -> split
                if a.isoformat() not in px or b.isoformat() not in px:
                    return None
                ra, rb = px[a.isoformat()], px[b.isoformat()]
                if not all((ra[0], ra[1], rb[0], rb[1])):
                    return None
                return int(abs((ra[0] / ra[1]) / (rb[0] / rb[1]) - 1) > 0.01)
            status = ("intraday_timing_ambiguous" if timing == "intraday" else
                      "insufficient_prior_events" if len(m4) < LOOKBACK else
                      "no_price_t0" if t0.isoformat() not in px else "candidate")
            rows.append((f"{t}_{sess}", t, cik, acc_et, timing, sess, t0.isoformat(), P.isoformat(), P1.isoformat(),
                         "stage1", sum(m4) / len(m4) if len(m4) == LOOKBACK else None,
                         sum(m8) / len(m8) if len(m8) == 8 else None,
                         (math.sqrt(sum((x - sum(m4) / 4) ** 2 for x in m4) / 3) if len(m4) == LOOKBACK else None),
                         len(moves), hv, px.get(t0.isoformat(), (None,))[0], px.get(P.isoformat(), (None,))[0],
                         split(t0, R), split(P, P1), status))
    c.execute("DELETE FROM events")
    c.executemany("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    c.commit()
    print(dict(c.execute("SELECT status, COUNT(*) FROM events GROUP BY status").fetchall()))


def stage_budget():
    c = db()
    n = c.execute("SELECT COUNT(*) FROM events WHERE status='candidate' AND split_in_window IS NOT 1").fetchone()[0]
    print(f"candidate events: {n}")
    for pass_rate in (0.5, 0.6, 0.7):
        npass = round(n * pass_rate)
        print(f"  if {pass_rate:.0%} pass the liquidity screen: entry {n} + exit {npass} + placebo 2x{npass} "
              f"= {n + 3 * npass} requests (without placebo: {n + npass})")


# ----------------------------------------------------------------------------- options (EODHD)
class QuotaExhaustedError(RuntimeError):
    pass


def _eodhd(symbol, obs, exp_from, exp_to, strike_lo=None, strike_hi=None):
    params = {"filter[underlying_symbol]": symbol, "filter[tradetime_from]": obs, "filter[tradetime_to]": obs,
              "filter[exp_date_from]": exp_from, "filter[exp_date_to]": exp_to, "page[limit]": 1000, "page[offset]": 0,
              "api_token": os.environ["EODHD_API_TOKEN"]}
    if strike_lo is not None:
        params["filter[strike_from]"], params["filter[strike_to]"] = round(strike_lo, 2), round(strike_hi, 2)
    out, pages = [], 0
    while True:
        pages += 1
        r = requests.get(EODHD_URL, params=params, timeout=60)
        if r.status_code == 429:
            raise QuotaExhaustedError(f"429 at {symbol} {obs}")
        r.raise_for_status()
        data = r.json().get("data", [])
        out += data
        if len(data) < 1000 or pages >= 10:
            return out, pages, len(data) < 1000
        params["page[offset]"] += 1000


def _store(c, event_id, kind, obs, symbol, recs, pages, complete):
    kept = 0
    for x in recs:
        a = x.get("attributes", {})
        if not str(x.get("id", "")).endswith("-" + obs):          # id-date rule (CLAUDE.md Section 4)
            continue
        kept += 1
        c.execute("INSERT OR IGNORE INTO option_quotes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (event_id, kind, obs, a.get("contract"), a.get("type"), a.get("strike"), a.get("exp_date"),
                   a.get("expiration_type"), a.get("bid"), a.get("ask"), a.get("volume"), a.get("open_interest"),
                   a.get("volatility"), a.get("delta"), a.get("ask_date")))
    c.execute("INSERT OR REPLACE INTO option_requests VALUES (?,?,?,?,?,?,?,?,?,?)",
              (event_id, kind, obs, symbol, pages, len(recs), kept, int(complete), None, _now()))
    c.commit()
    return kept


def select_contract(c, event_id, kind, obs, R_or_next, spot):
    """Entry-known ATM straddle: earliest expiry in [R, R+7]; strike nearest the raw close with both legs bid>0, ask>bid."""
    q = c.execute("SELECT option_type, strike, exp_date, bid, ask FROM option_quotes WHERE event_id=? AND kind=? AND obs_date=?",
                  (event_id, kind, obs)).fetchall()
    lo, hi = R_or_next, (date.fromisoformat(R_or_next) + timedelta(days=EXPIRY_MAX_DAYS)).isoformat()
    exps = sorted({e for _, _, e, _, _ in q if lo <= e <= hi})
    for e in exps[:1]:
        legs = {}
        for typ, k, ex, b, a in q:
            if ex == e and b is not None and a is not None and b > 0 and a > b:
                legs.setdefault(k, {})[typ] = (b, a)
        both = [k for k, v in legs.items() if "call" in v and "put" in v]
        if both:
            k = min(both, key=lambda s: (abs(s - spot), s))
            if abs(k / spot - 1) <= 0.05:
                return e, k, legs[k]["call"], legs[k]["put"]
    return None


def screen(call, put):
    mid = (call[0] + call[1]) / 2 + (put[0] + put[1]) / 2
    spread = (call[1] - call[0]) + (put[1] - put[0])
    return mid >= 1.00 and spread <= 0.10 * mid, mid, spread


def stage_options(include_placebo=False, max_requests=None):
    fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)
    made = 0
    try:
        c = db()
        done = {(r[0], r[1]) for r in c.execute("SELECT event_id, kind FROM option_requests WHERE error IS NULL")}
        evs = c.execute("SELECT event_id, ticker, reaction_session, entry_session, placebo_entry, placebo_exit, raw_close_t0, "
                        "raw_close_p FROM events WHERE status='candidate' AND split_in_window IS NOT 1 ORDER BY reaction_session").fetchall()
        for eid, t, R, t0, P, P1, s0, sp in evs:
            sym = t.replace(".", "-")
            plan = [("entry", t0, R, s0)]
            for kind, obs, Rn, spot in plan:
                if (eid, kind) not in done:
                    recs, pages, ok = _eodhd(sym, obs, Rn, (date.fromisoformat(Rn) + timedelta(days=EXPIRY_MAX_DAYS)).isoformat(),
                                             spot * (1 - ENTRY_STRIKE_BAND), spot * (1 + ENTRY_STRIKE_BAND))
                    _store(c, eid, kind, obs, sym, recs, pages, ok); made += pages
            sel = select_contract(c, eid, "entry", t0, R, s0)
            if not sel or not screen(sel[2], sel[3])[0]:
                continue
            e, k = sel[0], sel[1]
            if (eid, "exit") not in done:
                recs, pages, ok = _eodhd(sym, R, e, e, k - 0.01, k + 0.01)
                _store(c, eid, "exit", R, sym, recs, pages, ok); made += pages
            if include_placebo and sp:
                if (eid, "placebo_entry") not in done:
                    recs, pages, ok = _eodhd(sym, P, P1, (date.fromisoformat(P1) + timedelta(days=EXPIRY_MAX_DAYS)).isoformat(),
                                             sp * (1 - ENTRY_STRIKE_BAND), sp * (1 + ENTRY_STRIKE_BAND))
                    _store(c, eid, "placebo_entry", P, sym, recs, pages, ok); made += pages
                ps = select_contract(c, eid, "placebo_entry", P, P1, sp)
                if ps and (eid, "placebo_exit") not in done:
                    recs, pages, ok = _eodhd(sym, P1, ps[0], ps[0], ps[1] - 0.01, ps[1] + 0.01)
                    _store(c, eid, "placebo_exit", P1, sym, recs, pages, ok); made += pages
            if max_requests and made >= max_requests:
                print(f"request cap {max_requests} reached"); break
    except QuotaExhaustedError as exc:
        print(f"=== STOPPED ON QUOTA (429): {exc}; requests this run {made} ===")
    finally:
        os.remove(LOCK)
    print(f"requests this run: {made}")


# ----------------------------------------------------------------------------- integrity + freeze
def stage_integrity():
    """Counts and data checks only. Uses entry-day quotes for the liquidity screen (entry-known data);
    never computes an exit value, a straddle return, or anything relating the signal to an outcome."""
    c = db()
    out = {"events_by_status": dict(c.execute("SELECT status, COUNT(*) FROM events GROUP BY status").fetchall())}
    cand = c.execute("SELECT event_id, entry_session, reaction_session, raw_close_t0, split_in_window FROM events "
                     "WHERE status='candidate'").fetchall()
    fail = {"split_in_window": 0, "no_entry_request": 0, "no_expiry_in_window_or_no_atm_pair": 0,
            "raw_close_lt_10": 0, "mid_lt_1": 0, "spread_gt_10pct": 0, "exit_quotes_missing": 0}
    survivors = []
    for eid, t0, R, s0, spl in cand:
        if spl == 1:
            fail["split_in_window"] += 1; continue
        if not c.execute("SELECT 1 FROM option_requests WHERE event_id=? AND kind='entry'", (eid,)).fetchone():
            fail["no_entry_request"] += 1; continue
        sel = select_contract(c, eid, "entry", t0, R, s0)
        if not sel:
            fail["no_expiry_in_window_or_no_atm_pair"] += 1; continue
        if s0 < 10:
            fail["raw_close_lt_10"] += 1; continue
        ok, mid, spread = screen(sel[2], sel[3])
        if mid < 1.0:
            fail["mid_lt_1"] += 1; continue
        if spread > 0.10 * mid:
            fail["spread_gt_10pct"] += 1; continue
        n_exit = c.execute("SELECT COUNT(*) FROM option_quotes WHERE event_id=? AND kind='exit' AND strike=? AND exp_date=?",
                           (eid, sel[1], sel[0])).fetchone()[0]
        if n_exit < 2:
            fail["exit_quotes_missing"] += 1          # NOT an exclusion: the registered fallback (intrinsic) applies
        survivors.append(eid)
    out["candidates"] = len(cand)
    out["screen_failures"] = fail
    out["surviving_events"] = len(survivors) + 0
    out["surviving_events_note"] = "exit_quotes_missing events survive (registered intrinsic fallback); counted for the <=5% soft check"
    out["quote_id_date_mismatch_rows"] = 0             # enforced at storage: rows whose id-date != obs are never stored
    out["timing"] = dict(c.execute("SELECT timing, COUNT(*) FROM events GROUP BY timing").fetchall())
    print(json.dumps(out, indent=1))
    with open(os.path.join(ROOT, "earnings_event_integrity.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    return out


def stage_freeze():
    c = db()
    man = {"created_utc": _now(), "db": os.path.basename(DB), "tables": {}}
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        h = hashlib.sha256()
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
        n = 0
        for row in c.execute(f"SELECT * FROM {t} ORDER BY {', '.join(cols)}"):
            h.update(json.dumps(row, default=str).encode()); n += 1
        man["tables"][t] = {"rows": n, "sha256": h.hexdigest()}
    with open(os.path.join(ROOT, "earnings_event_dataset_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1)
    print(json.dumps(man, indent=1))


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    {"universe": stage_universe, "edgar": stage_edgar, "prices": stage_prices, "events": stage_events,
     "budget": stage_budget, "integrity": stage_integrity, "freeze": stage_freeze,
     "options": lambda: stage_options(include_placebo="--placebo" in sys.argv,
                                      max_requests=int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else None),
     }.get(stage, lambda: print(__doc__))()

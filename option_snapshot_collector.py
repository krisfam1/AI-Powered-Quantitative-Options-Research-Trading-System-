from dotenv import load_dotenv
load_dotenv()

"""
Full option-chain snapshots for the cross-sectional straddle hypothesis (CLAUDE.md Section 62).

For every cycle in straddle_schedule.cycles() of the requested window and every ticker in the 59-ticker
universe, stores two snapshots from EODHD's UnicornBay options EOD endpoint:
  entry : all expirations from the entry date to +60 days, strikes within +/-25% of the raw close
          (enough for the straddle, wings, term slope, skew and a later GEX computation)
  exit  : only the target expiration, same strike band (the day-before-expiry exit variant)
Only records whose id-date suffix equals the snapshot date are kept (Section 4 rule).

Quota safety (Section 60): the first HTTP 429 raises QuotaExhaustedError and stops the whole run
immediately -- no retries, no hammering. Resumable: a (ticker, date, kind) with a complete summary row is
skipped. An exclusive lockfile prevents concurrent runs. Never touches the BLIND window unless asked.

Usage:
  python option_snapshot_collector.py                    # DEV window, all tickers
  python option_snapshot_collector.py --measure AAPL 2024-03-18   # one ticker-cycle, request cost
"""
import os, sqlite3, sys, time
from datetime import date, datetime, timedelta, timezone
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, "option_snapshots.db")
LOCK = os.path.join(ROOT, "option_snapshot_collection.lock")
LOG = os.path.join(ROOT, "option_snapshot_collection_log.txt")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
TOKEN = os.environ.get("EODHD_API_TOKEN")
STRIKE_BAND = 0.25
ENTRY_MAX_DTE = 60
PAGE = 1000


class QuotaExhaustedError(RuntimeError):
    pass


def log(msg):
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def universe():
    from generate_broader_universe_volatility_dataset import TICKERS
    return list(TICKERS)


def raw_closes(ticker, start, end):
    from alpaca.data.historical.stock import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.enums import Adjustment, DataFeed
    cli = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
    bars = cli.get_stock_bars(StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Day,
                                               start=datetime.combine(start, datetime.min.time()),
                                               end=datetime.combine(end, datetime.min.time()),
                                               adjustment=Adjustment.RAW, feed=DataFeed.IEX))
    return {b.timestamp.date(): float(b.close) for b in bars.data.get(ticker, [])}


def fetch(ticker, obs, exp_from, exp_to, spot=None, strike_filter=True):
    """All pages for one request; returns (records, pages, complete). 429 -> QuotaExhaustedError."""
    params = {"filter[underlying_symbol]": ticker, "filter[tradetime_from]": obs.isoformat(),
              "filter[tradetime_to]": obs.isoformat(), "filter[exp_date_from]": exp_from.isoformat(),
              "filter[exp_date_to]": exp_to.isoformat(), "page[limit]": PAGE, "page[offset]": 0,
              "api_token": TOKEN}
    if strike_filter and spot:
        params["filter[strike_from]"] = round(spot * (1 - STRIKE_BAND), 2)
        params["filter[strike_to]"] = round(spot * (1 + STRIKE_BAND), 2)
    out, pages, nxt = [], 0, None
    while True:
        pages += 1
        if nxt:
            r = requests.get(nxt + ("&" if "?" in nxt else "?") + "api_token=" + TOKEN, timeout=60)
        else:
            r = requests.get(BASE_URL, params=params, timeout=60)
        if r.status_code == 429:
            raise QuotaExhaustedError(f"429 at {ticker} {obs} page {pages}")
        r.raise_for_status()
        p = r.json()
        data = p.get("data", [])
        out.extend(data)
        links = p.get("links") or {}
        if links.get("next"):
            nxt = links["next"]
            continue
        if len(data) == PAGE and not links:
            params["page[offset]"] += PAGE
            if pages > 25:
                return out, pages, False
            continue
        return out, pages, True


def _init(c):
    c.execute("""CREATE TABLE IF NOT EXISTS chain (
        ticker TEXT, obs_date TEXT, kind TEXT, contract TEXT, option_type TEXT, strike REAL, exp_date TEXT,
        bid REAL, ask REAL, bid_size REAL, ask_size REAL, last REAL, volume INTEGER, open_interest INTEGER,
        iv REAL, delta REAL, gamma REAL, theta REAL, vega REAL, ask_date TEXT,
        UNIQUE(ticker, obs_date, kind, contract))""")
    c.execute("""CREATE TABLE IF NOT EXISTS snapshot_summary (
        ticker TEXT, obs_date TEXT, kind TEXT, cycle_entry TEXT, target_expiry TEXT, window TEXT,
        spot_raw REAL, pages INTEGER, records INTEGER, retained INTEGER, complete INTEGER, error TEXT,
        fetched_at TEXT, UNIQUE(ticker, obs_date, kind))""")


def _rows(ticker, obs, kind, recs):
    rows, kept = [], 0
    for r in recs:
        rid, a = r.get("id", ""), r.get("attributes", {})
        if rid.rsplit("-", 3)[-3:] != obs.isoformat().split("-"):   # id-date suffix must equal obs date
            continue
        kept += 1
        rows.append((ticker, obs.isoformat(), kind, a.get("contract"), a.get("type"), a.get("strike"),
                     a.get("exp_date"), a.get("bid"), a.get("ask"), a.get("bid_size"), a.get("ask_size"),
                     a.get("last"), a.get("volume"), a.get("open_interest"), a.get("volatility"),
                     a.get("delta"), a.get("gamma"), a.get("theta"), a.get("vega"), a.get("ask_date")))
    return rows, kept


def snapshot(c, ticker, obs, kind, cyc, spot, strike_filter=True):
    if kind == "entry":
        exp_from, exp_to = obs, obs + timedelta(days=ENTRY_MAX_DTE)
    else:
        exp_from = exp_to = cyc["expiry"]
    recs, pages, complete = fetch(ticker, obs, exp_from, exp_to, spot, strike_filter)
    rows, kept = _rows(ticker, obs, kind, recs)
    c.executemany(f"INSERT OR IGNORE INTO chain VALUES ({','.join('?' * 20)})", rows)
    c.execute("INSERT OR REPLACE INTO snapshot_summary VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (ticker, obs.isoformat(), kind, cyc["entry"].isoformat(), cyc["expiry"].isoformat(), cyc["window"],
               spot, pages, len(recs), kept, int(complete), None, datetime.now(timezone.utc).isoformat()))
    c.commit()
    return pages, len(recs), kept


def measure(ticker, entry_str):
    from straddle_schedule import cycles
    entry = date.fromisoformat(entry_str)
    cyc = next(x for x in cycles(last_entry=entry) if x["entry"] == entry)
    px = raw_closes(ticker, entry - timedelta(days=5), cyc["exit"] + timedelta(days=2))
    c = sqlite3.connect(DB); _init(c)
    total = 0
    for kind, obs in (("entry", cyc["entry"]), ("exit", cyc["exit"])):
        spot = px[obs]
        pages, n, kept = snapshot(c, ticker, obs, kind, cyc, spot)
        strikes = [r[0] for r in c.execute("SELECT strike FROM chain WHERE ticker=? AND obs_date=? AND kind=?",
                                           (ticker, obs.isoformat(), kind))]
        inband = sum(spot * (1 - STRIKE_BAND) - 0.01 <= s <= spot * (1 + STRIKE_BAND) + 0.01 for s in strikes)
        print(f"{kind:5} {obs} spot {spot}: {pages} request(s), {n} records, {kept} id-date matched; "
              f"strike filter honored: {inband}/{len(strikes)} in band")
        total += pages
    # cost without the strike filter, for comparison (entry only; NOT stored)
    recs, pages_nf, _ = fetch(ticker, cyc["entry"], cyc["entry"], cyc["entry"] + timedelta(days=ENTRY_MAX_DTE),
                              strike_filter=False)
    print(f"entry without strike filter: {pages_nf} request(s), {len(recs)} records (not stored)")
    print(f"TOTAL requests for this ticker-cycle (stored path): {total}")
    c.close()


def collect(window="dev"):
    from straddle_schedule import cycles
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode()); os.close(fd)
    except FileExistsError:
        log("LOCK HELD -- another collection run is active. Exiting without touching data.")
        return
    c = sqlite3.connect(DB); _init(c)
    done = {(t, d, k) for t, d, k in c.execute("SELECT ticker, obs_date, kind FROM snapshot_summary WHERE complete=1 AND error IS NULL")}
    cyc = [x for x in cycles(last_entry=date.today()) if x["window"] == window and x["expiry"] < date.today()]
    log(f"=== RUN START | window={window} cycles={len(cyc)} tickers={len(universe())} already_done={len(done)}")
    requests_made, stored = 0, 0
    try:
        for t in universe():
            need = [(x, k, x[k]) for x in cyc for k in ("entry", "exit") if (t, x[k].isoformat(), k) not in done]
            if not need:
                continue
            try:
                px = raw_closes(t, cyc[0]["entry"] - timedelta(days=5), cyc[-1]["exit"] + timedelta(days=2))
            except Exception as exc:
                log(f"{t}: price fetch failed, skipping ticker this run: {exc}")
                continue
            for x, kind, obs in need:
                spot = px.get(obs)
                if spot is None:
                    c.execute("INSERT OR REPLACE INTO snapshot_summary VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                              (t, obs.isoformat(), kind, x["entry"].isoformat(), x["expiry"].isoformat(), window,
                               None, 0, 0, 0, 0, "no_raw_close", datetime.now(timezone.utc).isoformat()))
                    c.commit(); continue
                try:
                    pages, n, kept = snapshot(c, t, obs, kind, x, spot)
                    requests_made += pages; stored += 1
                except QuotaExhaustedError:
                    raise
                except Exception as exc:
                    log(f"{t} {obs} {kind}: fetch error (retried next run): {exc}")
            log(f"DONE {t}: requests so far {requests_made}, snapshots stored {stored}")
        log(f"=== RUN COMPLETE | requests {requests_made} | snapshots {stored}")
    except QuotaExhaustedError as exc:
        log(f"STOPPED ON QUOTA EXHAUSTION: {exc} | requests {requests_made} | snapshots {stored}")
        log("=== RUN STOPPED EARLY (QUOTA)")
    finally:
        c.close()
        os.remove(LOCK)


def status(window="dev"):
    from straddle_schedule import cycles
    cyc = [x for x in cycles(last_entry=date.today()) if x["window"] == window and x["expiry"] < date.today()]
    need = len(cyc) * 2 * len(universe())
    if not os.path.exists(DB):
        return 0, need
    with sqlite3.connect(DB) as c:
        try:
            have = c.execute("SELECT COUNT(*) FROM snapshot_summary WHERE window=? AND complete=1 AND error IS NULL",
                             (window,)).fetchone()[0]
        except sqlite3.OperationalError:
            have = 0
    return have, need


if __name__ == "__main__":
    if "--measure" in sys.argv:
        i = sys.argv.index("--measure")
        measure(sys.argv[i + 1], sys.argv[i + 2])
    elif "--status" in sys.argv:
        print("dev snapshots: %d / %d" % status("dev"))
    else:
        collect("blind" if "--blind" in sys.argv else "dev")

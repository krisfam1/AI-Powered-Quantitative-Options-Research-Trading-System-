from dotenv import load_dotenv
load_dotenv()

"""
Execution-cost measurement, Stream B: per-minute option quote sampler (execution_cost_measurement_design_v1.md).

ROLE CHANGED 2026-10-01 (user decision): the PRIMARY cost source is now EODHD's real end-of-day bid/ask,
built by execution_cost_eod.py into the eod_spreads table of the same database (zero extra EODHD calls).
This intraday sampler on Alpaca's indicative feed is SECONDARY: it measures the time-of-day SHAPE of
spreads and is cross-checked against EODHD at the close. Its absolute spread levels are not real costs.

Pure logging. It places no orders and changes no signal, sizing or exit logic. The options loop calls
sample_once() once per 60s cycle during market hours, inside try/except, so a failure here can never
affect trading. Options only (user decision 2026-10-01: the stock bot is out of scope).

Panel (fixed once per ET trading day, at the first sample): the 6 research tickers + SPY. Per ticker, in
the IV term-structure buckets (near = soonest expiration with 7-16 DTE, far = latest with 30-45 DTE),
a call and a put at |delta| closest to 0.30 and at the strike closest to spot: up to 8 contracts.

FEED CAVEAT (found 2026-10-01): this account has only Alpaca's INDICATIVE options feed. OPRA returns
"OPRA agreement is not signed". Indicative quotes are adjusted derivatives of OPRA, not real exchange
quotes, so spreads sampled on it are NOT real market costs. The feed is recorded on every row; set
EXECUTION_COST_OPTIONS_FEED=opra in .env once an OPRA subscription is active.
"""

import os
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from alpaca.data.enums import DataFeed, OptionsFeed
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import OptionChainRequest, OptionLatestQuoteRequest, StockLatestTradeRequest

from options_backtest_engine import _estimated_spread_cost_pct

ET = ZoneInfo("America/New_York")
DB_PATH = os.environ.get("EXECUTION_COST_DB",
                         os.path.join(os.path.dirname(os.path.abspath(__file__)), "execution_cost_log.db"))
PANEL_TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR", "SPY"]
BUCKETS = {"near": (7, 16), "far": (30, 45)}
TARGET_DELTA = 0.30
FEED_NAME = os.environ.get("EXECUTION_COST_OPTIONS_FEED", "indicative").lower()
FEED = OptionsFeed.OPRA if FEED_NAME == "opra" else OptionsFeed.INDICATIVE

_key, _secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
_opt = OptionHistoricalDataClient(_key, _secret)
_stk = StockHistoricalDataClient(_key, _secret)
_panel_cache = {"date": None, "rows": []}


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS panel (
        et_date TEXT, ticker TEXT, bucket TEXT, option_type TEXT, role TEXT, symbol TEXT,
        expiration TEXT, dte INTEGER, strike REAL, delta_at_selection REAL, iv_at_selection REAL,
        spot_at_selection REAL, feed TEXT, selected_at TEXT,
        UNIQUE(et_date, ticker, bucket, option_type, role))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sample_ts TEXT, et_date TEXT, et_minute TEXT, ticker TEXT, symbol TEXT, bucket TEXT,
        option_type TEXT, role TEXT, feed TEXT, quote_ts TEXT, bid REAL, ask REAL,
        bid_size REAL, ask_size REAL, mid REAL, quoted_half_spread_pct REAL,
        model_v1_half_spread_pct REAL, spot REAL, strike REAL, dte INTEGER, moneyness REAL,
        UNIQUE(symbol, sample_ts))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS sampler_runs (
        sample_ts TEXT PRIMARY KEY, n_symbols INTEGER, n_quotes INTEGER, seconds REAL, error TEXT)""")
    return conn


def _spots(tickers):
    trades = _stk.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=tickers, feed=DataFeed.IEX))
    return {t: float(trades[t].price) for t in tickers if t in trades}


def _parse_occ(symbol):
    """OCC symbol ROOT + YYMMDD + C/P + strike*1000 (8 digits)."""
    tail = symbol[-15:]
    exp = date(2000 + int(tail[0:2]), int(tail[2:4]), int(tail[4:6]))
    return symbol[:-15], exp, ("call" if tail[6] == "C" else "put"), int(tail[7:]) / 1000.0


def _select_panel(et_today):
    spots = _spots(PANEL_TICKERS)
    rows = []
    for t in PANEL_TICKERS:
        spot = spots.get(t)
        if not spot:
            continue
        chain = _opt.get_option_chain(OptionChainRequest(
            underlying_symbol=t, feed=FEED,
            expiration_date_gte=et_today + timedelta(days=7), expiration_date_lte=et_today + timedelta(days=45)))
        parsed = []
        for sym, snap in chain.items():
            _, exp, typ, strike = _parse_occ(sym)
            g = getattr(snap, "greeks", None)
            parsed.append((sym, exp, (exp - et_today).days, typ, strike,
                           getattr(g, "delta", None) if g else None, getattr(snap, "implied_volatility", None)))
        for bucket, (lo, hi) in BUCKETS.items():
            exps = sorted({p[1] for p in parsed if lo <= p[2] <= hi})
            if not exps:
                continue
            exp = exps[0] if bucket == "near" else exps[-1]   # IV term-structure convention
            for typ in ("call", "put"):
                cands = [p for p in parsed if p[1] == exp and p[3] == typ]
                if not cands:
                    continue
                atm = min(cands, key=lambda p: abs(p[4] - spot))
                with_d = [p for p in cands if p[5] is not None]
                d30 = min(with_d, key=lambda p: abs(abs(p[5]) - TARGET_DELTA)) if with_d else None
                for role, p in (("atm", atm), ("delta30", d30)):
                    if p is not None:
                        rows.append({"ticker": t, "bucket": bucket, "option_type": typ, "role": role,
                                     "symbol": p[0], "expiration": p[1].isoformat(), "dte": p[2], "strike": p[4],
                                     "delta": p[5], "iv": p[6], "spot": spot})
    return rows


def _panel(conn, et_today):
    if _panel_cache["date"] == et_today and _panel_cache["rows"]:
        return _panel_cache["rows"]
    stored = conn.execute("SELECT ticker,bucket,option_type,role,symbol,expiration,dte,strike FROM panel "
                          "WHERE et_date=?", (et_today.isoformat(),)).fetchall()
    if stored:
        rows = [dict(zip(("ticker", "bucket", "option_type", "role", "symbol", "expiration", "dte", "strike"), r))
                for r in stored]
    else:
        rows = _select_panel(et_today)
        now = datetime.now(timezone.utc).isoformat()
        conn.executemany("INSERT OR IGNORE INTO panel VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            (et_today.isoformat(), r["ticker"], r["bucket"], r["option_type"], r["role"], r["symbol"],
             r["expiration"], r["dte"], r["strike"], r["delta"], r["iv"], r["spot"], FEED_NAME, now) for r in rows])
        conn.commit()
    _panel_cache.update(date=et_today, rows=rows)
    return rows


def sample_once():
    """Take one snapshot of the panel's latest quotes. Returns the number of quote rows written."""
    t0 = time.time()
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(ET)
    sample_ts = now_utc.replace(microsecond=0).isoformat()
    conn = _connect()
    err, written, symbols = None, 0, []
    try:
        panel = _panel(conn, now_et.date())
        symbols = sorted({r["symbol"] for r in panel})
        quotes = _opt.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=symbols, feed=FEED))
        spots = _spots(PANEL_TICKERS)
        out = []
        for r in panel:
            q = quotes.get(r["symbol"])
            if q is None:
                continue
            bid, ask = float(q.bid_price or 0), float(q.ask_price or 0)
            mid = (bid + ask) / 2 if bid > 0 and ask >= bid else None
            spot = spots.get(r["ticker"])
            out.append((sample_ts, now_et.date().isoformat(), now_et.strftime("%H:%M"), r["ticker"], r["symbol"],
                        r["bucket"], r["option_type"], r["role"], FEED_NAME,
                        q.timestamp.isoformat() if q.timestamp else None, bid, ask, q.bid_size, q.ask_size, mid,
                        (ask - bid) / (2 * mid) if mid else None,
                        _estimated_spread_cost_pct(mid) / 2 if mid else None,
                        spot, r["strike"], (date.fromisoformat(r["expiration"]) - now_et.date()).days,
                        r["strike"] / spot - 1 if spot else None))
        conn.executemany("INSERT OR IGNORE INTO quotes (sample_ts,et_date,et_minute,ticker,symbol,bucket,option_type,"
                         "role,feed,quote_ts,bid,ask,bid_size,ask_size,mid,quoted_half_spread_pct,"
                         "model_v1_half_spread_pct,spot,strike,dte,moneyness) VALUES "
                         "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", out)
        written = len(out)
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"[:500]
    conn.execute("INSERT OR REPLACE INTO sampler_runs VALUES (?,?,?,?,?)",
                 (sample_ts, len(symbols), written, round(time.time() - t0, 2), err))
    conn.commit()
    conn.close()
    if err:
        raise RuntimeError(err)
    return written


if __name__ == "__main__":
    print("feed:", FEED_NAME, "| db:", DB_PATH)
    print("rows written:", sample_once())

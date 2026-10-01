"""
Execution cost, PRIMARY source (user decision 2026-10-01): real EODHD end-of-day bid/ask spreads.

Makes ZERO EODHD calls. GEX_Historical_Incremental_Update already downloads the full option chain for
AAPL, TSLA, NVDA, AMD, SMCI, MSTR and SPY every night and keeps every raw record (with bid, ask, sizes,
delta, IV) in gex_data_cache.db:raw_records. This script only reads that table, read-only.

Writes execution_cost_log.db:eod_spreads, one row per (date, contract, panel), for two panels:
  panel='eodhd'  : the cost panel, chosen from EODHD's own data with the same rules as the intraday
                   sampler -- near = soonest expiration 7-16 DTE, far = latest 30-45 DTE; call and put at
                   the strike nearest spot ('atm') and at |EODHD delta| nearest 0.30 ('delta30').
  panel='alpaca' : EODHD's close quote for the exact contracts Alpaca's intraday sampler watched that
                   day (execution_cost_log.db:panel), for the indicative-vs-real cross-check.
Then prints/stores the cross-check: Alpaca indicative quote nearest the close vs EODHD close, same contract.

Idempotent (UNIQUE + INSERT OR IGNORE) and self-healing: every run rebuilds any missing date, so a GEX
backlog fills in automatically once the GEX task catches up. Run nightly after the GEX update.
Usage: python execution_cost_eod.py [--since YYYY-MM-DD]
"""
import json, os, sqlite3, sys
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
GEX_DB = os.path.join(ROOT, "gex_data_cache.db")
COST_DB = os.environ.get("EXECUTION_COST_DB", os.path.join(ROOT, "execution_cost_log.db"))
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR", "SPY"]
BUCKETS = {"near": (7, 16), "far": (30, 45)}
FIRST_DATE = "2026-06-10"   # earliest stored chains

DDL = """CREATE TABLE IF NOT EXISTS eod_spreads (
    et_date TEXT, ticker TEXT, panel TEXT, bucket TEXT, option_type TEXT, role TEXT, contract TEXT,
    exp_date TEXT, dte INTEGER, strike REAL, spot REAL, moneyness REAL, delta REAL, iv REAL,
    bid REAL, ask REAL, bid_size REAL, ask_size REAL, mid REAL, half_spread_pct REAL,
    open_interest INTEGER, volume INTEGER, ask_date TEXT, source TEXT, built_at TEXT,
    UNIQUE(et_date, contract, panel, role))"""


def _row(d, t, panel, bucket, role, r, spot):
    b, a = r.get("bid") or 0.0, r.get("ask") or 0.0
    mid = (a + b) / 2 if b > 0 and a >= b else None
    return (d, t, panel, bucket, r["type"], role, r["contract"], r["exp_date"],
            (date.fromisoformat(r["exp_date"]) - date.fromisoformat(d)).days, float(r["strike"]), spot,
            float(r["strike"]) / spot - 1 if spot else None, r.get("delta"), r.get("volatility"),
            b, a, r.get("bid_size"), r.get("ask_size"), mid, (a - b) / (2 * mid) if mid else None,
            r.get("open_interest"), r.get("volume"), r.get("ask_date"), "eodhd_eod",
            date.today().isoformat())


def build(since=FIRST_DATE):
    g = sqlite3.connect(f"file:{GEX_DB}?mode=ro", uri=True)
    c = sqlite3.connect(COST_DB)
    c.execute(DDL)
    have = {r[0] for r in c.execute("SELECT DISTINCT et_date FROM eod_spreads WHERE panel='eodhd'")}
    alpaca_panel = {}
    if c.execute("SELECT name FROM sqlite_master WHERE name='panel'").fetchone():
        for d, sym, bucket, role in c.execute("SELECT et_date, symbol, bucket, role FROM panel"):
            alpaca_panel.setdefault(d, []).append((sym, bucket, role))
    have_alp = {r[0] for r in c.execute("SELECT DISTINCT et_date FROM eod_spreads WHERE panel='alpaca'")}
    spot = {(t, d): s for t, d, s in g.execute(
        "SELECT ticker, snapshot_date, spot_price FROM gex_metrics WHERE sign_convention='model_a'")}
    dates = [r[0] for r in g.execute(
        "SELECT DISTINCT requested_date FROM raw_records WHERE requested_date>=? ORDER BY 1", (since,))]
    built = 0
    for d in dates:
        need_eod, need_alp = d not in have, (d in alpaca_panel and d not in have_alp)
        if not (need_eod or need_alp):
            continue
        chains = {}
        for t, rj in g.execute("SELECT ticker, raw_json FROM raw_records WHERE requested_date=? "
                               "AND matches_requested_date=1", (d,)):
            r = json.loads(rj)
            chains.setdefault(t, {}).setdefault(r["contract"], r)   # id-date matched; first record per contract
        rows = []
        if need_eod:
            for t in TICKERS:
                S, recs = spot.get((t, d)), list(chains.get(t, {}).values())
                if not S or not recs:
                    continue
                for bucket, (lo, hi) in BUCKETS.items():
                    exps = sorted({r["exp_date"] for r in recs
                                   if lo <= (date.fromisoformat(r["exp_date"]) - date.fromisoformat(d)).days <= hi})
                    if not exps:
                        continue
                    e = exps[0] if bucket == "near" else exps[-1]
                    for typ in ("call", "put"):
                        cand = [r for r in recs if r["exp_date"] == e and r["type"] == typ]
                        if not cand:
                            continue
                        rows.append(_row(d, t, "eodhd", bucket, "atm", min(cand, key=lambda r: abs(r["strike"] - S)), S))
                        wd = [r for r in cand if r.get("delta") is not None]
                        if wd:
                            rows.append(_row(d, t, "eodhd", bucket, "delta30",
                                             min(wd, key=lambda r: abs(abs(r["delta"]) - 0.30)), S))
        if need_alp:
            for sym, bucket, role in alpaca_panel[d]:
                t = sym[:-15]
                r = chains.get(t, {}).get(sym)
                if r:
                    rows.append(_row(d, t, "alpaca", bucket, role, r, spot.get((t, d))))
        c.executemany(f"INSERT OR IGNORE INTO eod_spreads VALUES ({','.join('?' * 25)})", rows)
        c.commit()
        built += 1
    n, lo, hi = c.execute("SELECT COUNT(*), MIN(et_date), MAX(et_date) FROM eod_spreads WHERE panel='eodhd'").fetchone()
    print(f"eod_spreads: built/updated {built} date(s); panel=eodhd now {n} rows, {lo}..{hi}")
    cross_check(c)
    c.close(); g.close()


def cross_check(c):
    """Alpaca indicative quote nearest the close vs EODHD's close quote, same contract, same day."""
    if not c.execute("SELECT name FROM sqlite_master WHERE name='quotes'").fetchone():
        print("cross-check: no intraday quotes yet")
        return
    rows = c.execute("""
        WITH last_q AS (
            SELECT q.et_date, q.symbol, q.quoted_half_spread_pct AS ind_half, q.et_minute
            FROM quotes q JOIN (SELECT et_date, symbol, MAX(et_minute) m FROM quotes
                                WHERE et_minute <= '16:00' AND quoted_half_spread_pct IS NOT NULL
                                GROUP BY et_date, symbol) x
              ON q.et_date=x.et_date AND q.symbol=x.symbol AND q.et_minute=x.m)
        SELECT l.ind_half, e.half_spread_pct FROM last_q l
        JOIN eod_spreads e ON e.et_date=l.et_date AND e.contract=l.symbol AND e.panel='alpaca'
        WHERE l.et_minute >= '15:45' AND e.half_spread_pct IS NOT NULL""").fetchall()
    if not rows:
        print("cross-check: no matched contract-days yet (needs a full sampled session + that night's GEX chains)")
        return
    ratios = sorted(a / b for a, b in rows if b)
    med = ratios[len(ratios) // 2]
    print(f"cross-check: {len(rows)} contract-days; median indicative/EODHD half-spread ratio {med:.2f}")


if __name__ == "__main__":
    since = sys.argv[sys.argv.index("--since") + 1] if "--since" in sys.argv else FIRST_DATE
    build(since)

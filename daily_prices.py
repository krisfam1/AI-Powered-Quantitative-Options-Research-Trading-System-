from dotenv import load_dotenv
load_dotenv()

"""
Daily close cache for the straddle backtester (CLAUDE.md Section 62) -> daily_prices.db.

Consolidated SIP daily bars from Alpaca (historical SIP is available on the free plan; verified
2026-10-01: NVDA 2024-06-07 raw close 1208.88, the official close, vs IEX 1208.42). Two series per day:
  raw_close   -- unadjusted; compared against option strikes (Section 56 rule) and used for settlement
  split_close -- split-adjusted only (no dividends); used for log returns / HV, and the ratio
                 raw_close / split_close changes exactly on split dates (split detection)
Usage: python daily_prices.py   (refreshes all tickers from 2022-06-01)
"""
import os, sqlite3
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, "daily_prices.db")
START = date(2022, 6, 1)


def refresh(tickers, start=START, end=None):
    from alpaca.data.historical.stock import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.enums import Adjustment, DataFeed
    end = end or date.today()
    cli = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS prices (ticker TEXT, date TEXT, raw_close REAL, split_close REAL, "
              "PRIMARY KEY(ticker, date))")
    for t in tickers:
        series = {}
        for adj in (Adjustment.RAW, Adjustment.SPLIT):
            bars = cli.get_stock_bars(StockBarsRequest(
                symbol_or_symbols=t, timeframe=TimeFrame.Day, adjustment=adj, feed=DataFeed.SIP,
                start=datetime.combine(start, datetime.min.time()),
                end=datetime.combine(end - timedelta(days=1), datetime.max.time().replace(microsecond=0))))
            series[adj] = {b.timestamp.date().isoformat(): float(b.close) for b in bars.data.get(t, [])}
        rows = [(t, d, series[Adjustment.RAW][d], series[Adjustment.SPLIT].get(d)) for d in series[Adjustment.RAW]]
        c.executemany("INSERT OR REPLACE INTO prices VALUES (?,?,?,?)", rows)
        c.commit()
        print(f"{t}: {len(rows)} days")
    c.close()


def load(ticker):
    """{date: (raw_close, split_close)} for one ticker."""
    with sqlite3.connect(DB) as c:
        return {date.fromisoformat(d): (r, s) for d, r, s in
                c.execute("SELECT date, raw_close, split_close FROM prices WHERE ticker=? ORDER BY date", (ticker,))}


if __name__ == "__main__":
    from generate_broader_universe_volatility_dataset import TICKERS
    refresh(list(TICKERS))

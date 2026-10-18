"""Stage 0 downloads for the SPX volatility-state engine (approved 2026-10-17).

Free public market data only. Writes raw files under data_snapshots/spx_vol_engine/
and never modifies anything else. The manifest is written by stage0_manifest.py.
"""
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent / "data_snapshots" / "spx_vol_engine"
UA = {"User-Agent": "Mozilla/5.0"}
SOURCES = {}  # relative path -> url


def get(url, dest, stream=False):
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, headers=UA, timeout=120, stream=stream)
    if r.status_code != 200:
        return r.status_code
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1 << 20):
            f.write(chunk)
    SOURCES[dest.relative_to(ROOT).as_posix()] = url
    return 200


def vx_archive():
    """Monthly VX contracts expiring 2004-2013 (old CFE archive format).

    2013 is included because the current-format files for 2013 expiries start only on
    2013-01-02, so the archive files are the only source for their 2012 trading.
    """
    codes = "FGHJKMNQUVXZ"
    for yy in range(4, 14):
        for c in codes:
            name = f"CFE_{c}{yy:02d}_VX.csv"
            url = f"https://cdn.cboe.com/resources/futures/archive/volume-and-price/{name}"
            st = get(url, ROOT / "vx_futures" / "archive" / name)
            if st != 200:
                print("archive missing", name, st)
            time.sleep(0.2)


def vx_current():
    """Monthly VX contracts listed in Cboe's product list (expiries 2013 onward)."""
    lst = requests.get(
        "https://www.cboe.com/us/futures/market_statistics/historical_data/product/list/VX/",
        headers=UA, timeout=120).json()
    (ROOT / "vx_futures").mkdir(parents=True, exist_ok=True)
    (ROOT / "vx_futures" / "product_list_VX.json").write_text(json.dumps(lst, indent=1))
    SOURCES["vx_futures/product_list_VX.json"] = (
        "https://www.cboe.com/us/futures/market_statistics/historical_data/product/list/VX/")
    for year, items in lst.items():
        for it in items:
            if it.get("duration_type") != "M":
                continue
            url = "https://cdn.cboe.com/" + it["path"]
            name = Path(it["path"]).name
            st = get(url, ROOT / "vx_futures" / "current" / name)
            if st != 200:
                print("current missing", name, st)
            time.sleep(0.2)


def yahoo():
    """Daily OHLC (and SPY adjusted close, splits, dividends) from Yahoo's chart API."""
    p1, p2 = 946684800, int(time.time())  # 2000-01-01 to now
    for sym, fname in (("%5EGSPC", "GSPC_yahoo_daily.json"), ("SPY", "SPY_yahoo_daily.json")):
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}"
               "&interval=1d&events=div%2Csplits&includeAdjustedClose=true")
        print(fname, get(url, ROOT / "daily_ohlc" / fname))


def hd_sample():
    url = "https://historicaldata.net/file/options_sample_2022H2.zip"
    print("sample", get(url, ROOT / "historicaldata_net_sample" / "options_sample_2022H2.zip", stream=True))


if __name__ == "__main__":
    for name in ("SPX", "VIX", "VIX9D", "VIX3M", "VIX6M", "VIX1Y", "VVIX", "SKEW", "VIX1D"):
        SOURCES[f"cboe_indices/{name}_History.csv"] = (
            f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{name}_History.csv")
    yahoo()
    vx_archive()
    vx_current()
    hd_sample()
    (ROOT / "_sources.json").write_text(json.dumps(SOURCES, indent=1, sort_keys=True))
    print("files:", len(SOURCES))

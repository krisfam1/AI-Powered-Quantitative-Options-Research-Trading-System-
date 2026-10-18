"""Stage 1, Task A: clean the Stage 0 raw files (rules: spx_vol/stage1_protocol.md, Section 1).

Runs on all years, since cleaning is row-level only. For 2017+ the manifest records row counts
only, never a statistic of values. Raw files are read, never modified.
Output: data_snapshots/spx_vol_engine/clean/{spx_daily,vol_indices,vx_futures}.csv + manifest.json
"""
import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from common import CLEAN, SNAP, block_of
from stage0_audit import cboe_frame, read_vx, yahoo_frame

VX_UNIT_CHANGE = pd.Timestamp("2007-03-26")
MONTHS = {c: i + 1 for i, c in enumerate("FGHJKMNQUVXZ")}


def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def counts_by_block(dates):
    """Row counts per block; the only thing recorded about later years."""
    if len(dates) == 0:
        return {}
    return {k: int(v) for k, v in block_of(dates).value_counts().sort_index().items()}


def dev_count(mask, dates):
    """Count of flagged rows in the development block only (no statistics on later years)."""
    b = block_of(dates)
    return int((pd.Series(np.asarray(mask), index=b.index)[b.values == "dev"]).sum())


def clean_spx(cal):
    g, _ = yahoo_frame("GSPC_yahoo_daily.json")
    g = g.loc[g.index.isin(cal), ["OPEN", "HIGH", "LOW", "CLOSE"]].copy()
    g.columns = ["open", "high", "low", "close"]
    cb = cboe_frame("SPX")["SPX"]
    g["cboe_close"] = cb.reindex(g.index)
    g["stale_open"] = (g["open"] == g["close"].shift(1)).astype(int)
    g["invalid_ohlc"] = ((g["high"] < g["low"]) | (g["open"] > g["high"]) | (g["open"] < g["low"])
                         | (g["close"] > g["high"]) | (g["close"] < g["low"])).astype(int)
    g["src_disagree"] = ((g["cboe_close"] / g["close"] - 1).abs() > 0.001).astype(int)
    rules = {"rows": counts_by_block(g.index),
             "stale_open_dev": dev_count(g["stale_open"] == 1, g.index),
             "invalid_ohlc_dev": dev_count(g["invalid_ohlc"] == 1, g.index),
             "cboe_vs_yahoo_close_gt_0.1pct_dev": dev_count(g["src_disagree"] == 1, g.index),
             "cboe_close_missing_dev": dev_count(g["cboe_close"].isna(), g.index)}
    return g, rules


def clean_vol(cal):
    out, rules = pd.DataFrame(index=cal), {}
    for name in ("VIX", "VIX9D", "VIX3M", "VIX6M", "VIX1Y", "VVIX", "SKEW"):
        df = cboe_frame(name)
        col = "CLOSE" if "CLOSE" in df.columns else name
        in_cal = df.index.isin(cal) | (df.index < cal.min())
        dropped = df.index[~df.index.isin(cal) & (df.index >= cal.min())]
        rules[name] = {"non_session_rows_dropped": counts_by_block(dropped),
                       "pre_2000_rows_not_used": int((df.index < cal.min()).sum())}
        kept = df[df.index.isin(cal)]
        out[name.lower()] = kept[col].reindex(cal)
        if {"HIGH", "LOW"} <= set(df.columns):
            hl = kept["HIGH"] < kept["LOW"]
            out[f"{name.lower()}_hl_flag"] = hl.reindex(cal).fillna(False).astype(int)
            rules[name]["high_lt_low_rows"] = [str(d.date()) for d in kept.index[hl]]
    out["vvix_bad_print"] = 0
    out.loc[out.index == pd.Timestamp("2006-03-15"), "vvix_bad_print"] = 1
    out.index.name = "date"
    rules["vvix_bad_print_flagged"] = ["2006-03-15"]
    return out, rules


def clean_vx(cal):
    rows = []
    for p in sorted((SNAP / "vx_futures" / "archive").glob("CFE_*_VX.csv")):
        df = read_vx(p, "%m/%d/%Y")
        df["era"], df["contract"] = "archive", f"20{p.name[5:7]}-{MONTHS[p.name[4]]:02d}"
        rows.append(df)
    for p in sorted((SNAP / "vx_futures" / "current").glob("VX_*.csv")):
        df = read_vx(p, "%Y-%m-%d")
        df["era"], df["contract"] = "current", p.name[3:10]
        df["expire_date_listed"] = p.name[3:13]
        rows.append(df)
    vx = pd.concat(rows, ignore_index=True)
    rules = {"rows_in": counts_by_block(vx["Trade Date"])}
    for c in ("Open", "High", "Low", "Close", "Settle"):
        vx[c] = pd.to_numeric(vx[c], errors="coerce")
    pre = vx["Trade Date"] < VX_UNIT_CHANGE
    vx.loc[pre, ["Open", "High", "Low", "Close", "Settle"]] /= 10.0
    rules["divided_by_10_pre_2007-03-26"] = int(pre.sum())
    rank = np.where(vx["Settle"] > 0, 0, 2) + np.where(vx["era"] == "current", 0, 1)
    vx = vx.assign(_rank=rank).sort_values("_rank")
    n0 = len(vx)
    vx = vx.drop_duplicates(["contract", "Trade Date"])
    rules["duplicate_contract_date_rows_dropped_2013_handover"] = int(n0 - len(vx))
    bad = ~(vx["Settle"] > 0)
    rules["settle_missing_or_le0_dropped"] = counts_by_block(vx.loc[bad, "Trade Date"])
    vx = vx[~bad]
    nons = ~vx["Trade Date"].isin(cal)
    rules["non_session_rows_dropped"] = counts_by_block(vx.loc[nons, "Trade Date"])
    vx = vx[~nons].copy()
    last = vx.groupby("contract")["Trade Date"].transform("max")
    listed = pd.to_datetime(vx.get("expire_date_listed"), errors="coerce")
    vx["expiry_proxy"] = listed.fillna(last)
    vx["expiry_source"] = np.where(listed.notna(), "cboe_product_list", "last_trade_date")
    vx["open_zero_flag"] = (vx["Open"] == 0).astype(int)
    vx["hl_flag"] = (vx["High"] < vx["Low"]).astype(int)
    out = vx.rename(columns={"Trade Date": "trade_date", "Settle": "settle"})[
        ["contract", "trade_date", "settle", "expiry_proxy", "expiry_source", "era",
         "open_zero_flag", "hl_flag"]].sort_values(["trade_date", "expiry_proxy"])
    out["dte"] = (out["expiry_proxy"] - out["trade_date"]).dt.days
    # Dev-era check only: for current-format contracts that expired by 2016, does the listed
    # expiry equal the last trade date in the file?
    cur = out[(out["expiry_source"] == "cboe_product_list") & (out["expiry_proxy"] <= "2016-12-31")]
    lt = cur.groupby("contract").agg(exp=("expiry_proxy", "first"), last=("trade_date", "max"))
    rules["dev_listed_expiry_vs_last_trade_date"] = {
        "contracts": int(len(lt)), "equal": int((lt["exp"] == lt["last"]).sum()),
        "differences_days": sorted({int(x) for x in (lt["exp"] - lt["last"]).dt.days})}
    rules["rows_out"] = counts_by_block(out["trade_date"])
    rules["contracts_out"] = int(out["contract"].nunique())
    return out, rules


def main():
    CLEAN.mkdir(parents=True, exist_ok=True)
    g, _ = yahoo_frame("GSPC_yahoo_daily.json")
    cal = g.dropna(subset=["CLOSE"]).index
    spx, r_spx = clean_spx(cal)
    vol, r_vol = clean_vol(cal)
    vx, r_vx = clean_vx(cal)
    spx.to_csv(CLEAN / "spx_daily.csv", index_label="date")
    vol.to_csv(CLEAN / "vol_indices.csv", index_label="date")
    vx.to_csv(CLEAN / "vx_futures.csv", index=False)
    src = json.loads((SNAP / "manifest.json").read_text())["files"]
    used = {k: v["sha256"] for k, v in src.items()
            if k.startswith(("cboe_indices/", "daily_ohlc/GSPC", "vx_futures/"))}
    man = {"created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "protocol": "spx_vol/stage1_protocol.md Section 1 (commit e2ff0b6)",
           "calendar": {"source": "Yahoo ^GSPC session dates", "sessions": counts_by_block(cal)},
           "source_sha256": used,
           "rules": {"spx": r_spx, "vol_indices": r_vol, "vx_futures": r_vx},
           "outputs": {f.name: {"rows": int(sum(1 for _ in open(f)) - 1), "sha256": sha256(f)}
                       for f in (CLEAN / "spx_daily.csv", CLEAN / "vol_indices.csv", CLEAN / "vx_futures.csv")},
           "note": "Later-year (val/locked) entries are row counts only; no value statistics."}
    (CLEAN / "manifest.json").write_text(json.dumps(man, indent=1, default=str))
    print(json.dumps(man["rules"], indent=1, default=str))


if __name__ == "__main__":
    main()

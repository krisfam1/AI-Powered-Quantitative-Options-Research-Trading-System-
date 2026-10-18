"""Stage 0 data audit for the SPX volatility-state engine (approved 2026-10-17).

Counts, dates and data quality ONLY. It computes no relationship between series, no
returns used as targets, no forecasts. The only cross-series comparison is calendar
alignment (which dates exist) and SPX close vs SPX close from a second source
(a same-series consistency check). Output: data_snapshots/spx_vol_engine/stage0_audit.json
"""
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent / "data_snapshots" / "spx_vol_engine"
AUDIT_START = pd.Timestamp("2004-01-01")
LOCK_START = pd.Timestamp("2021-01-01")
OUT = {}


def yahoo_frame(fname):
    js = json.loads((ROOT / "daily_ohlc" / fname).read_text())
    res = js["chart"]["result"][0]
    ts = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert("America/New_York")
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({"OPEN": q["open"], "HIGH": q["high"], "LOW": q["low"],
                       "CLOSE": q["close"], "VOLUME": q["volume"]},
                      index=pd.DatetimeIndex(ts.tz_localize(None).normalize(), name="DATE"))
    adj = res["indicators"].get("adjclose")
    if adj:
        df["ADJCLOSE"] = adj[0]["adjclose"]
    ev = res.get("events", {})
    return df, {"splits": len(ev.get("splits", {})), "dividends": len(ev.get("dividends", {}))}


def cboe_frame(name):
    df = pd.read_csv(ROOT / "cboe_indices" / f"{name}_History.csv")
    df["DATE"] = pd.to_datetime(df["DATE"], format="%m/%d/%Y")
    return df.set_index("DATE").sort_index()


def series_quality(df, cal, close_col):
    """Calendar gaps and value-quality counts for one daily series."""
    idx = df.index
    first, last = idx.min(), idx.max()
    cal_in = cal[(cal >= max(first, cal.min())) & (cal <= min(last, cal.max()))]
    missing = cal_in.difference(idx)
    extra = idx[(idx >= cal.min()) & (idx <= cal.max())].difference(cal)
    c = df[close_col].astype(float)
    out = {
        "first_date": str(first.date()), "last_date": str(last.date()), "rows": int(len(df)),
        "duplicate_dates": int(idx.duplicated().sum()),
        "rows_from_2004": int((idx >= AUDIT_START).sum()),
        "rows_dev_2004_2016": int(((idx >= AUDIT_START) & (idx < "2017-01-01")).sum()),
        "rows_val_2017_2020": int(((idx >= "2017-01-01") & (idx < LOCK_START)).sum()),
        "rows_locked_2021_on": int((idx >= LOCK_START).sum()),
        "missing_reference_sessions": int(len(missing)),
        "missing_examples": [str(d.date()) for d in missing[:15]],
        "missing_by_year": {str(k): int(v) for k, v in pd.Series(missing.year).value_counts().sort_index().items()},
        "dates_not_in_reference_calendar": int(len(extra)),
        "extra_examples": [str(d.date()) for d in extra[:10]],
        "null_close": int(c.isna().sum()),
        "nonpositive_close": int((c <= 0).sum()),
    }
    # Suspect prints: a one-day move in log level larger than 0.5 that reverses the next day.
    lc = np.log(c.where(c > 0))
    d1, d2 = lc.diff(), lc.diff(-1)
    spikes = lc.index[(d1.abs() > 0.5) & (d2.abs() > 0.5) & (np.sign(d1) == np.sign(d2))]
    out["suspect_spike_prints"] = [str(d.date()) for d in spikes]
    if {"OPEN", "HIGH", "LOW"} <= set(df.columns):
        o, h, l = (df[k].astype(float) for k in ("OPEN", "HIGH", "LOW"))
        flat = (o == h) & (h == l) & (l == c)
        out["ohlc_all_equal_rows"] = int(flat.sum())
        out["ohlc_all_equal_last_date"] = str(df.index[flat].max().date()) if flat.any() else None
        out["ohlc_all_equal_from_2004"] = int(flat[idx >= AUDIT_START].sum())
        out["open_equals_prev_close_from_2004"] = int(((o == c.shift(1)) & (idx >= AUDIT_START)).sum())
        out["high_lt_low"] = int((h < l).sum())
        out["close_outside_high_low"] = int(((c > h + 1e-9) | (c < l - 1e-9)).sum())
        out["null_ohlc_rows"] = int(df[["OPEN", "HIGH", "LOW", "CLOSE"]].isna().any(axis=1).sum())
    return out


def audit_daily():
    gspc, gev = yahoo_frame("GSPC_yahoo_daily.json")
    spy, sev = yahoo_frame("SPY_yahoo_daily.json")
    cal = gspc.dropna(subset=["CLOSE"]).index  # reference NYSE session calendar, 2000+
    OUT["reference_calendar"] = {"source": "Yahoo ^GSPC session dates", "first": str(cal.min().date()),
                                 "last": str(cal.max().date()), "sessions": int(len(cal))}
    g = series_quality(gspc, cal, "CLOSE")
    g["events"] = gev
    OUT["SPX_yahoo_ohlc"] = g
    s = series_quality(spy, cal, "CLOSE")
    s["events"] = sev
    s["null_volume"] = int(spy["VOLUME"].isna().sum())
    OUT["SPY_yahoo_ohlc"] = s
    spx_cboe = cboe_frame("SPX")
    OUT["SPX_cboe_close"] = series_quality(spx_cboe, cal, "SPX")
    # Same-series consistency: Cboe SPX close vs Yahoo ^GSPC close on common dates (2004+).
    j = spx_cboe[["SPX"]].join(gspc[["CLOSE"]], how="inner")
    j = j[j.index >= AUDIT_START].dropna()
    rel = (j["SPX"] / j["CLOSE"] - 1).abs()
    OUT["SPX_close_source_agreement"] = {
        "common_dates_2004_on": int(len(j)), "max_abs_rel_diff": float(rel.max()),
        "dates_diff_over_0.1pct": int((rel > 0.001).sum()),
        "examples": [str(d.date()) for d in rel[rel > 0.001].index[:10]]}
    for name in ("VIX", "VIX9D", "VIX3M", "VIX6M", "VIX1Y", "VIX1D", "VVIX", "SKEW"):
        df = cboe_frame(name)
        col = "CLOSE" if "CLOSE" in df.columns else name
        q = series_quality(df, cal, col)
        q["columns"] = list(df.columns)
        OUT[f"{name}_cboe"] = q
    old = pd.read_csv(Path(__file__).resolve().parent.parent / "data_snapshots" / "vrp_timing_20261002"
                      / "VIX3M_History.csv")
    OUT["VIX3M_cboe"]["note_vs_2026-10-02_snapshot"] = {"old_first": old["DATE"].iloc[0],
                                                        "old_rows": int(len(old))}
    return cal


def read_vx(path, fmt):
    # Some archive rows carry a trailing comma (12 fields); keep the 11 named columns.
    lines = Path(path).read_text().splitlines()
    while lines and not lines[0].startswith("Trade Date"):
        lines.pop(0)  # any preamble line before the header
    header = [c.strip() for c in lines[0].split(",")][:11]
    body = [ln.split(",")[:11] for ln in lines[1:] if ln.strip()]
    df = pd.DataFrame(body, columns=header)
    df["Trade Date"] = pd.to_datetime(df["Trade Date"], format=fmt)
    return df


def audit_vx(cal):
    rows, contracts = [], []
    for p in sorted((ROOT / "vx_futures" / "archive").glob("CFE_*_VX.csv")):
        df = read_vx(p, "%m/%d/%Y")
        df["file"], df["era"] = p.name, "archive"
        rows.append(df)
    for p in sorted((ROOT / "vx_futures" / "current").glob("VX_*.csv")):
        df = read_vx(p, "%Y-%m-%d")
        df["file"], df["era"] = p.name, "current"
        rows.append(df)
    vx = pd.concat(rows, ignore_index=True)
    # 2013 expiries exist in both formats. Key each row by expiry year-month and keep one row
    # per (contract, date): the current-format row if its settle is positive, else the archive row.
    months = {c: i + 1 for i, c in enumerate("FGHJKMNQUVXZ")}

    def key(f):
        if f.startswith("CFE_"):
            return f"20{f[5:7]}-{months[f[4]]:02d}"
        return f[3:10]

    vx["contract"] = vx["file"].map(key)
    vx["_settle"] = pd.to_numeric(vx["Settle"], errors="coerce")
    vx["_rank"] = np.where(vx["_settle"] > 0, 0, 2) + np.where(vx["era"] == "current", 0, 1)
    n0 = len(vx)
    vx = vx.sort_values("_rank").drop_duplicates(["contract", "Trade Date"]).sort_values(["contract", "Trade Date"])
    OUT["VX_overlap_rows_dropped_2013"] = int(n0 - len(vx))
    for f, g in vx.groupby("contract"):
        contracts.append({"contract": f, "files": sorted(g["file"].unique()), "first": str(g["Trade Date"].min().date()),
                          "last": str(g["Trade Date"].max().date()), "rows": int(len(g))})
    settle = pd.to_numeric(vx["Settle"], errors="coerce")
    o, h, l = (pd.to_numeric(vx[k], errors="coerce") for k in ("Open", "High", "Low"))
    pre = vx["Trade Date"] < "2007-03-26"
    exp_last = vx.groupby("contract")["Trade Date"].transform("max")  # last trade date ~ expiry
    vx["dte"] = (exp_last - vx["Trade Date"]).dt.days
    good = vx[settle > 0]
    per_day = good.groupby("Trade Date")
    n_live = per_day.size()
    max_dte = per_day["dte"].max()
    future_files = [c for c in contracts if c["last"] >= "2026-10-16"]
    sess = cal[(cal >= n_live.index.min()) & (cal <= min(n_live.index.max(), cal.max()))]
    OUT["VX_futures"] = {
        "monthly_contracts": len(contracts),
        "archive_files": int((vx.groupby("file")["era"].first() == "archive").sum()),
        "current_files": int((vx.groupby("file")["era"].first() == "current").sum()),
        "first_trade_date": str(vx["Trade Date"].min().date()),
        "last_trade_date": str(vx["Trade Date"].max().date()),
        "rows": int(len(vx)),
        "rows_settle_missing_or_zero": int((~(settle > 0)).sum()),
        "rows_open_zero": int((o == 0).sum()),
        "rows_high_lt_low": int((h < l).sum()),
        "pre_2007-03-26_rows": int(pre.sum()),
        "pre_2007-03-26_median_settle": float(settle[pre].median()),
        "post_2007-03-26_median_settle": float(settle[~pre].median()),
        "sessions_with_any_settle": int(len(n_live)),
        "reference_sessions_missing_any_settle": int(len(sess.difference(n_live.index))),
        "missing_session_examples": [str(d.date()) for d in sess.difference(n_live.index)[:10]],
        "missing_sessions_by_year": {str(k): int(v) for k, v in
                                     pd.Series(sess.difference(n_live.index).year).value_counts().sort_index().items()},
        "sessions_with_only_1_contract_by_year": {str(k): int(v) for k, v in
                                                  (n_live == 1).groupby(n_live.index.year).sum().items() if v},
        "contracts_live_per_session": {"min": int(n_live.min()), "median": float(n_live.median()),
                                       "max": int(n_live.max())},
        "sessions_with_ge2_contracts": int((n_live >= 2).sum()),
        "sessions_from_2004_with_contract_dte_ge_150": int((max_dte >= 150).sum()),
        "first_session_with_dte_ge_150": str(max_dte[max_dte >= 150].index.min().date()),
        "sessions_with_contract_dte_ge_150_by_year": {
            str(k): int(v) for k, v in (max_dte >= 150).groupby(max_dte.index.year).sum().items()},
        "contract_files_still_trading_or_unexpired": len(future_files),
        "per_contract": contracts,
    }


def audit_sample():
    z = zipfile.ZipFile(ROOT / "historicaldata_net_sample" / "options_sample_2022H2.zip")
    names = sorted(n for n in z.namelist() if n.startswith("day_by_date/") and n.endswith(".csv"))
    agg = {}
    for n in names:
        df = pd.read_csv(io.BytesIO(z.read(n)), low_memory=False)
        df = df[df["underlying"].isin(["SPX", "SPXW", "SPY"])]
        for u, g in df.groupby("underlying"):
            a = agg.setdefault(u, {"files": 0, "rows": 0, "bid_present": 0, "ask_present": 0,
                                   "two_sided": 0, "crossed": 0, "iv_present": 0, "delta_present": 0,
                                   "oi_present": 0, "quote_time_present": 0, "expirations": set(),
                                   "same_day_expiry_rows": 0, "iv_flag": {}})
            a["files"] += 1
            a["rows"] += len(g)
            b, k = g["bid"], g["ask"]
            a["bid_present"] += int(b.notna().sum())
            a["ask_present"] += int(k.notna().sum())
            a["two_sided"] += int((b.notna() & k.notna() & (b > 0)).sum())
            a["crossed"] += int((b > k).sum())
            a["iv_present"] += int(g["iv"].notna().sum())
            a["delta_present"] += int(g["delta"].notna().sum())
            a["oi_present"] += int(g["open_interest"].notna().sum())
            a["quote_time_present"] += int(g["quote_time"].notna().sum())
            a["expirations"].update(g["expiration"].unique())
            a["same_day_expiry_rows"] += int((g["expiration"] == g["quote_date"]).sum())
            for fl, cnt in g["iv_flag"].value_counts(dropna=False).items():
                a["iv_flag"][str(fl)] = a["iv_flag"].get(str(fl), 0) + int(cnt)
    for u, a in agg.items():
        a["distinct_expirations"] = len(a.pop("expirations"))
    OUT["historicaldata_net_sample"] = {"daily_files": len(names), "first": names[0][12:22],
                                        "last": names[-1][12:22], "by_underlying": agg}


if __name__ == "__main__":
    cal = audit_daily()
    audit_vx(cal)
    audit_sample()
    (ROOT / "stage0_audit.json").write_text(json.dumps(OUT, indent=1, default=str))
    slim = {k: {kk: vv for kk, vv in v.items() if kk != "per_contract"} if isinstance(v, dict) else v
            for k, v in OUT.items()}
    print(json.dumps(slim, indent=1, default=str))

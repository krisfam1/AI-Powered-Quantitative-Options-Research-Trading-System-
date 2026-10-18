"""Stage 1, Task B: VIX futures curve and the 127 pre-declared features (stage1_protocol.md, Section 2).

Development years only. The loader stops reading each clean file at its first row dated after
2016-12-30, so later years are never parsed, and dev_guard() checks every input.
No feature is related to any target here.
"""
import csv
import io

import numpy as np
import pandas as pd

from common import CLEAN, DEV_START, FEATURES, dev_guard
from estimators import rv_points, window_estimate

LAST_DEV_SESSION = "2016-12-30"
CM_TENORS = (30, 60, 90, 120, 150)
# Deviation D2 (reported in the Stage 1 report): a 252-session window needs >= 250 non-missing
# values, so one missing VVIX/SKEW day does not blank 252 days of statistics.
ROLL_MIN = 250


def read_dev_csv(path, date_col):
    """Read rows with DEV_START <= date <= LAST_DEV_SESSION; stop at the first later row (files are date-sorted)."""
    lo = DEV_START.strftime("%Y-%m-%d")
    buf = io.StringIO()
    with open(path, newline="") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        i = header.index(date_col)
        w = csv.writer(buf)
        w.writerow(header)
        for row in rdr:
            d = row[i][:10]
            if d > LAST_DEV_SESSION:
                break
            if d >= lo:
                w.writerow(row)
    buf.seek(0)
    df = pd.read_csv(buf, parse_dates=[date_col])
    dev_guard(df[date_col], f"read_dev_csv({path.name})")
    return df


def load_dev():
    spx = read_dev_csv(CLEAN / "spx_daily.csv", "date").set_index("date")
    vol = read_dev_csv(CLEAN / "vol_indices.csv", "date").set_index("date")
    vx = read_dev_csv(CLEAN / "vx_futures.csv", "trade_date")
    return spx, vol, vx


def build_curve(vx, dates):
    """Constant-maturity VIX futures (linear in DTE on price), VX1/VX2, roll and extrapolation flags."""
    dev_guard(dates, "build_curve")
    vx = vx[vx["trade_date"].isin(dates)]
    out = pd.DataFrame(index=pd.DatetimeIndex(dates, name="date"),
                       columns=[f"cm{t}" for t in CM_TENORS] + ["vx1", "vx2", "vx1_contract", "cm_extrapolated"],
                       dtype=object)
    for d, g in vx.groupby("trade_date"):
        g = g[g["dte"] >= 1].sort_values("dte")
        if g.empty:
            continue
        dte, px = g["dte"].to_numpy(float), g["settle"].to_numpy(float)
        extrap = 0
        for t in CM_TENORS:
            if t < dte[0]:
                val, extrap = px[0], 1
            elif t > dte[-1]:
                val = np.nan
            else:
                j = int(np.searchsorted(dte, t))
                if dte[j] == t:
                    val = px[j]
                else:
                    d1, d2, f1, f2 = dte[j - 1], dte[j], px[j - 1], px[j]
                    val = f1 + (f2 - f1) * (t - d1) / (d2 - d1)
            out.at[d, f"cm{t}"] = val
        out.at[d, "vx1"] = px[0]
        out.at[d, "vx2"] = px[1] if len(px) > 1 else np.nan
        out.at[d, "vx1_contract"] = g["contract"].iloc[0]
        out.at[d, "cm_extrapolated"] = extrap
    num = [c for c in out.columns if c != "vx1_contract"]
    out[num] = out[num].astype(float)
    out["vx_roll"] = (out["vx1_contract"] != out["vx1_contract"].shift(1)).astype(int)
    out.iloc[0, out.columns.get_loc("vx_roll")] = 0
    return out


def _pct_rank(x, window=None):
    if window:
        r = x.rolling(window, min_periods=ROLL_MIN).rank()
        n = x.rolling(window, min_periods=ROLL_MIN).count()
        return (r - 1) / (n - 1)
    r = x.expanding(min_periods=252).rank()
    n = x.expanding(min_periods=252).count()
    return (r - 1) / (n - 1)


def _mad(a):
    a = a[~np.isnan(a)]
    return np.median(np.abs(a - np.median(a)))


def _robust_z(x, window=None):
    if window:
        med = x.rolling(window, min_periods=ROLL_MIN).median()
        mad = x.rolling(window, min_periods=ROLL_MIN).apply(_mad, raw=True)
    else:
        med = x.expanding(min_periods=252).median()
        mad = x.expanding(min_periods=252).apply(_mad, raw=True)
    return (x - med) / (1.4826 * mad.replace(0, np.nan))


def _rolling_ar1(y, window=252):
    x = y.shift(1)
    ok = y.notna() & x.notna()
    yy, xx = y.where(ok), x.where(ok)
    mx = xx.rolling(window, min_periods=window).mean()
    my = yy.rolling(window, min_periods=window).mean()
    cov = (xx * yy).rolling(window, min_periods=window).mean() - mx * my
    var = (xx * xx).rolling(window, min_periods=window).mean() - mx * mx
    return cov / var


LEVELS = ("vix", "rv5", "rv21", "vix_over_rv21", "vix_over_rv5", "vvix_over_vix", "skew")
SPREADS = ("vix_minus_rv21", "vrp_trail", "ts_9d", "ts_3m", "ts_6m", "fut_basis", "fut_slope",
           "fut_curv", "vx1_minus_vx2")
DYNAMICS = ("vix_mom5", "vix_mom20", "vix_ar1_252")


def base_variables(spx, vol, curve, estimator):
    idx = spx.index
    dev_guard(idx, "base_variables")
    rv5 = rv_points(window_estimate(spx, estimator, 5))
    rv21 = rv_points(window_estimate(spx, estimator, 21))
    vix = vol["vix"].reindex(idx)
    b = pd.DataFrame(index=idx)
    b["vix"], b["rv5"], b["rv21"] = vix, rv5, rv21
    b["vix_minus_rv21"] = vix - rv21
    b["vix_over_rv21"] = vix / rv21.replace(0, np.nan)
    b["vix_over_rv5"] = vix / rv5.replace(0, np.nan)
    b["vrp_trail"] = (vix / 100) ** 2 - (rv21 / 100) ** 2
    b["ts_9d"] = vol["vix9d"].reindex(idx) - vix
    b["ts_3m"] = vix - vol["vix3m"].reindex(idx)
    b["ts_6m"] = vol["vix3m"].reindex(idx) - vol["vix6m"].reindex(idx)
    c = curve.reindex(idx)
    b["fut_basis"] = c["cm30"] - vix
    b["fut_slope"] = c["cm60"] - c["cm30"]
    b["fut_curv"] = c["cm30"] - 2 * c["cm60"] + c["cm90"]
    b["vx1_minus_vx2"] = c["vx1"] - c["vx2"]
    b["vvix_over_vix"] = vol["vvix"].reindex(idx) / vix
    b["skew"] = vol["skew"].reindex(idx)
    lv = np.log(vix)
    b["vix_mom5"] = lv - lv.shift(5)
    b["vix_mom20"] = lv - lv.shift(20)
    b["vix_ar1_252"] = _rolling_ar1(lv)
    return b


def build_features(spx, vol, curve, estimator="CC"):
    """Return the 127 feature columns plus flags, indexed by session date (dev years only)."""
    b = base_variables(spx, vol, curve, estimator)
    f = {}
    for name in LEVELS + SPREADS:
        x = b[name]
        f[f"{name}__raw"] = x
        f[f"{name}__pct252"] = _pct_rank(x, 252)
        f[f"{name}__pctexp"] = _pct_rank(x)
        f[f"{name}__rz252"] = _robust_z(x, 252)
        f[f"{name}__rzexp"] = _robust_z(x)
        if name in LEVELS:
            lx = np.log(x.where(x > 0))
            f[f"{name}__chg5"], f[f"{name}__chg20"] = lx - lx.shift(5), lx - lx.shift(20)
        else:
            f[f"{name}__chg5"], f[f"{name}__chg20"] = x - x.shift(5), x - x.shift(20)
    for name in DYNAMICS:
        x = b[name]
        f[f"{name}__raw"] = x
        f[f"{name}__pct252"] = _pct_rank(x, 252)
        f[f"{name}__rz252"] = _robust_z(x, 252)
    vvix_rz = _robust_z(vol["vvix"].reindex(b.index), 252)
    f["ix_vrpgap_slope"] = f["vix_minus_rv21__rz252"] * f["fut_slope__rz252"]
    f["ix_vrpgap_vvix"] = f["vix_minus_rv21__rz252"] * vvix_rz
    f["ix_ratio_skew"] = f["vix_over_rv21__rz252"] * f["skew__rz252"]
    f["ix_vixz_rvz"] = f["vix__rz252"] * f["rv21__rz252"]
    f["ix_vvixz_minus_vixz"] = vvix_rz - f["vix__rz252"]
    f["ix_slopepct_vrppct"] = f["fut_slope__pct252"] * f["vrp_trail__pct252"]
    f = pd.DataFrame(f, index=b.index)
    assert f.shape[1] == 127, f.shape
    c = curve.reindex(b.index)
    f = f.copy()
    f["flag_vx_roll"] = c["vx_roll"]
    f["flag_cm_extrapolated"] = c["cm_extrapolated"]
    f["flag_stale_open"] = spx["stale_open"].reindex(b.index)
    return f


def main(estimator):
    spx, vol, vx = load_dev()
    curve = build_curve(vx, spx.index)
    feats = build_features(spx, vol, curve, estimator)
    FEATURES.mkdir(parents=True, exist_ok=True)
    feats.to_csv(FEATURES / "features_dev_2008_2016.csv", index_label="date")
    curve.to_csv(FEATURES / "vx_curve_dev_2008_2016.csv", index_label="date")
    return feats, curve


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "CC")

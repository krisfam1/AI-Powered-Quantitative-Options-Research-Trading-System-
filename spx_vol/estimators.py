"""Realized-variance estimators (spx_vol/stage1_protocol.md, Section 3.1).

Daily proxies are in unannualized variance; window estimates are annualized (x252).
On stale-open or invalid-OHLC days the open is unknown: P/GK/RS fall back to r^2, and YZ
treats the day as overnight = r, open-to-close = 0, RS = 0.
"""
import numpy as np
import pandas as pd

ESTIMATORS = ("CC", "P", "GK", "RS", "YZ")
LN2 = np.log(2.0)


def daily_components(spx):
    """spx: DataFrame with open, high, low, close, stale_open, invalid_ohlc (session index)."""
    o_, h_, l_, c_ = (spx[k].astype(float) for k in ("open", "high", "low", "close"))
    r = np.log(c_ / c_.shift(1))
    ov = np.log(o_ / c_.shift(1))
    u, d, c = np.log(h_ / o_), np.log(l_ / o_), np.log(c_ / o_)
    hl = np.log(h_ / l_)
    rs_intra = u * (u - c) + d * (d - c)
    fb = (spx["stale_open"].astype(int) == 1) | (spx["invalid_ohlc"].astype(int) == 1)
    comp = pd.DataFrame({"r": r, "o": ov, "c": c, "hl": hl, "rs": rs_intra, "fallback": fb.astype(int)},
                        index=spx.index)
    comp.loc[fb, "o"] = comp.loc[fb, "r"]
    comp.loc[fb, ["c", "rs"]] = 0.0
    return comp


def daily_proxies(comp):
    r2 = comp["r"] ** 2
    p = comp["o"] ** 2 + comp["hl"] ** 2 / (4 * LN2)
    gk = comp["o"] ** 2 + 0.5 * comp["hl"] ** 2 - (2 * LN2 - 1) * comp["c"] ** 2
    rs = comp["o"] ** 2 + comp["rs"]
    fb = comp["fallback"] == 1
    out = pd.DataFrame({"CC": r2, "P": p, "GK": gk, "RS": rs}, index=comp.index)
    for col in ("P", "GK", "RS"):
        out.loc[fb, col] = r2[fb]
    return out


def yang_zhang(comp, n):
    k = 0.34 / (1.34 + (n + 1) / (n - 1))
    so = comp["o"].rolling(n, min_periods=n).var(ddof=1)
    sc = comp["c"].rolling(n, min_periods=n).var(ddof=1)
    srs = comp["rs"].rolling(n, min_periods=n).mean()
    return 252.0 * (so + k * sc + (1 - k) * srs)


def window_estimate(spx, est, w, comp=None):
    """Annualized variance estimate over the last w sessions up to and including t."""
    comp = daily_components(spx) if comp is None else comp
    if est == "YZ":
        return yang_zhang(comp, w)
    return 252.0 * daily_proxies(comp)[est].rolling(w, min_periods=w).mean()


def rv_points(var):
    """Annualized variance -> vol points (100 * sqrt)."""
    return 100.0 * np.sqrt(var.clip(lower=0))

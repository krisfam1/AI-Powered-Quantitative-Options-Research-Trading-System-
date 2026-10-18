"""Shared paths, block dates and the development-only guard for the SPX volatility-state engine."""
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parent.parent
SNAP = PROJECT / "data_snapshots" / "spx_vol_engine"
CLEAN = SNAP / "clean"
FEATURES = SNAP / "features"
RESULTS = SNAP / "results"

DEV_START = pd.Timestamp("2008-01-02")
DEV_END = pd.Timestamp("2016-12-31")       # guard limit; the last dev session is 2016-12-30
VAL_START = pd.Timestamp("2017-01-01")
LOCK_START = pd.Timestamp("2021-01-01")

# Stage 1 only: analysis may touch development years only (user rule 2026-10-17).
ANALYSIS_MAX_DATE = DEV_END


class LockedDataError(RuntimeError):
    """Raised when an analysis function is handed dates outside what this stage may touch."""


VAL_MAX_DATE = pd.Timestamp("2020-12-31")  # Stage 2 validation only (run_validation)


def lock_guard(dates, where=""):
    """Always in force: nothing dated 2021-01-01 or later may be analysed in any step."""
    idx = pd.DatetimeIndex(dates)
    if len(idx) and idx.max() >= LOCK_START:
        raise LockedDataError(f"{where}: date {idx.max().date()} is in the locked years (2021+)")


def val_guard(dates, where=""):
    """Stage 2 validation only: allows 2008-01-02 .. 2020-12-31; 2021+ still raises."""
    lock_guard(dates, where)
    idx = pd.DatetimeIndex(dates)
    if len(idx) and (idx.max() > VAL_MAX_DATE or idx.min() < DEV_START):
        raise LockedDataError(f"{where}: dates outside 2008-01-02..2020-12-31")


def dev_guard(dates, where=""):
    """Raise unless every date lies in [DEV_START, ANALYSIS_MAX_DATE]."""
    lock_guard(dates, where)
    idx = pd.DatetimeIndex(dates)
    if len(idx) == 0:
        return
    if idx.max() > ANALYSIS_MAX_DATE:
        raise LockedDataError(f"{where}: date {idx.max().date()} is after {ANALYSIS_MAX_DATE.date()} "
                              "(validation/locked years may not be analysed in Stage 1)")
    if idx.min() < DEV_START:
        raise LockedDataError(f"{where}: date {idx.min().date()} is before {DEV_START.date()} "
                              "(2004-2007 stays unused)")


def block_of(dates):
    """Label each date dev / val / locked / pre (counting only)."""
    d = pd.DatetimeIndex(dates)
    out = pd.Series("dev", index=d)
    out[d < DEV_START] = "pre"
    out[d >= VAL_START] = "val"
    out[d >= LOCK_START] = "locked"
    return out

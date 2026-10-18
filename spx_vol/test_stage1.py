"""Tests for Stage 1 (run: spx_vol\\.venv\\Scripts\\python -m unittest test_stage1 -v, from spx_vol/).

All tests use synthetic data; none reads real data or writes to the search ledger.
"""
import unittest

import numpy as np
import pandas as pd

import compare
import features
from common import LockedDataError, dev_guard
from estimators import daily_components, daily_proxies, window_estimate


def synth(n=700, seed=0, start="2008-01-02"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n)
    c = 1300 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = c * np.exp(rng.normal(0, 0.003, n))
    h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.004, n)))
    l = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.004, n)))
    spx = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "stale_open": 0, "invalid_ohlc": 0}, index=idx)
    spx.iloc[10, spx.columns.get_loc("stale_open")] = 1
    vix = 20 * np.exp(np.cumsum(rng.normal(0, 0.03, n)) * 0.2)
    vol = pd.DataFrame({"vix": vix, "vix9d": vix * 0.95, "vix3m": vix * 1.05, "vix6m": vix * 1.08,
                        "vvix": 90 + rng.normal(0, 5, n), "skew": 120 + rng.normal(0, 3, n)}, index=idx)
    rows = []
    for k in range(-1, n // 21 + 8):
        exp = idx[0] + pd.Timedelta(days=30 * k + 10)
        for d in idx:
            dte = (exp - d).days
            if 0 <= dte <= 220:
                rows.append({"contract": f"C{k}", "trade_date": d, "settle": 18 + 0.01 * dte + rng.normal(0, 0.1),
                             "dte": dte})
    vx = pd.DataFrame(rows)
    return spx, vol, vx


class TestGuard(unittest.TestCase):
    def test_guard(self):
        dev_guard(pd.to_datetime(["2008-01-02", "2016-12-30"]))
        with self.assertRaises(LockedDataError):
            dev_guard(pd.to_datetime(["2016-12-30", "2017-01-03"]))
        with self.assertRaises(LockedDataError):
            dev_guard(pd.to_datetime(["2007-12-31"]))

    def test_analysis_functions_refuse_2017(self):
        spx, vol, vx = synth(n=60, start="2016-11-01")
        with self.assertRaises(LockedDataError):
            compare.run(spx, vol)
        with self.assertRaises(LockedDataError):
            features.build_curve(vx, spx.index)


class TestEstimators(unittest.TestCase):
    def test_fallback_equals_cc(self):
        spx, _, _ = synth(60)
        p = daily_proxies(daily_components(spx))
        for col in ("P", "GK", "RS"):
            self.assertAlmostEqual(p[col].iloc[10], p["CC"].iloc[10])

    def test_yang_zhang_manual(self):
        spx, _, _ = synth(60)
        n = 21
        comp = daily_components(spx)
        w = comp.iloc[30 - n + 1:31]
        k = 0.34 / (1.34 + (n + 1) / (n - 1))
        manual = 252 * (np.var(w["o"], ddof=1) + k * np.var(w["c"], ddof=1) + (1 - k) * w["rs"].mean())
        self.assertAlmostEqual(window_estimate(spx, "YZ", n).iloc[30], manual, places=12)

    def test_qlike(self):
        self.assertAlmostEqual(compare.qlike(np.array([0.04]), np.array([0.04]))[0], 0.0)
        self.assertGreater(compare.qlike(np.array([0.04]), np.array([0.02]))[0], 0)


class TestTargetAndPurge(unittest.TestCase):
    def test_target(self):
        spx, _, _ = synth(100)
        y = compare.forward_target(spx, 5)
        r = np.log(spx["close"] / spx["close"].shift(1))
        self.assertAlmostEqual(y.iloc[20], 252 / 5 * (r.iloc[21:26] ** 2).sum())
        self.assertTrue(y.iloc[-5:].isna().all())

    def test_training_rows_purged(self):
        ok = np.arange(0, 500)
        tr = compare.training_rows(400, 21, ok)
        self.assertEqual(tr.max(), 400 - 42)

    def test_oos_run_synthetic(self):
        spx, vol, _ = synth(900)
        res = compare.run(spx, vol, log=False)
        for h in ("21", "5"):
            self.assertTrue(all(m["purge_ok"] for m in res["horizons"][h]["models"].values()))
        self.assertEqual(res["ledger_rows_logged"], 0)


class TestCurve(unittest.TestCase):
    def test_interpolation(self):
        d = pd.Timestamp("2010-06-01")
        vx = pd.DataFrame({"contract": ["a", "b", "c"], "trade_date": [d] * 3,
                           "settle": [20.0, 22.0, 23.0], "dte": [20, 50, 100]})
        cur = features.build_curve(vx, pd.DatetimeIndex([d]))
        self.assertAlmostEqual(cur.at[d, "cm30"], 20 + 2 * 10 / 30)
        self.assertAlmostEqual(cur.at[d, "cm60"], 22 + 1 * 10 / 50)
        self.assertTrue(np.isnan(cur.at[d, "cm120"]))
        self.assertEqual(cur.at[d, "vx1"], 20.0)
        self.assertEqual(cur.at[d, "cm_extrapolated"], 0)


class TestNoLookahead(unittest.TestCase):
    def setUp(self):
        self.spx, self.vol, self.vx = synth(700)
        self.T = self.spx.index[600]

    def feats(self, spx, vol, vx):
        return features.build_features(spx, vol, features.build_curve(vx, spx.index), "CC")

    def test_truncation(self):
        full = self.feats(self.spx, self.vol, self.vx)
        cut = self.feats(self.spx.loc[:self.T], self.vol.loc[:self.T], self.vx[self.vx.trade_date <= self.T])
        pd.testing.assert_frame_equal(full.loc[:self.T], cut, check_freq=False)

    def test_perturb_future(self):
        rng = np.random.default_rng(7)
        spx2, vol2, vx2 = self.spx.copy(), self.vol.copy(), self.vx.copy()
        fut = spx2.index > self.T
        for col in ("open", "high", "low", "close"):
            spx2.loc[fut, col] *= rng.uniform(0.5, 1.5, fut.sum())
        for col in vol2.columns:
            vol2.loc[vol2.index > self.T, col] *= rng.uniform(0.5, 1.5, (vol2.index > self.T).sum())
        m = vx2.trade_date > self.T
        vx2.loc[m, "settle"] *= rng.uniform(0.5, 1.5, m.sum())
        a = self.feats(self.spx, self.vol, self.vx).loc[:self.T]
        b = self.feats(spx2, vol2, vx2).loc[:self.T]
        pd.testing.assert_frame_equal(a, b)

    def test_single_missing_value_does_not_blank_window(self):
        vol2 = self.vol.copy()
        vol2.iloc[400, vol2.columns.get_loc("skew")] = np.nan
        f = self.feats(self.spx, vol2, self.vx)
        self.assertEqual(int(f["skew__rz252"].iloc[300:].isna().sum()), 1)

    def test_feature_count(self):
        f = self.feats(self.spx, self.vol, self.vx)
        self.assertEqual(sum(not c.startswith("flag_") for c in f.columns), 127)


if __name__ == "__main__":
    unittest.main()

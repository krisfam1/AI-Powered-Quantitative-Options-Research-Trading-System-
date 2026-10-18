"""Stage 2 tests (synthetic data only; run from spx_vol/: .venv\\Scripts\\python -m unittest test_stage2 -v)."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import search_ledger
import stage2
from common import LockedDataError, dev_guard, lock_guard, val_guard
from test_stage1 import synth


def synth_inputs(n=2300, start="2008-01-02", seed=1):
    spx, vol, vx = synth(n=n, seed=seed, start=start)
    return spx, vol, vx


class TestLock(unittest.TestCase):
    def test_guards_block_2021(self):
        d21 = pd.to_datetime(["2020-12-31", "2021-01-04"])
        for g in (dev_guard, val_guard, lock_guard):
            with self.assertRaises(LockedDataError):
                g(d21)
        val_guard(pd.to_datetime(["2008-01-02", "2020-12-31"]))
        with self.assertRaises(LockedDataError):
            dev_guard(pd.to_datetime(["2017-01-03"]))

    def test_steps_refuse_locked_data(self):
        spx, vol, vx = synth_inputs(n=300, start="2020-06-01")   # runs into 2021
        with self.assertRaises(LockedDataError):
            stage2.build_inputs(spx, vol, vx, guard=val_guard)
        idx = pd.bdate_range("2020-06-01", periods=300)
        fake = pd.DataFrame({"vix": 1.0}, index=idx)
        with self.assertRaises(LockedDataError):
            stage2.run_validation("skew__raw", {"dev_sign": 1}, log=False, data=fake)
        with self.assertRaises(LockedDataError):
            stage2.dev_run(fake, "skew__raw", log=False)


class TestNoLookahead(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spx, cls.vol, cls.vx = synth_inputs(n=700)
        cls.d = stage2.build_inputs(cls.spx, cls.vol, cls.vx)

    def test_features_use_data_through_t_only(self):
        T = self.spx.index[500]
        rng = np.random.default_rng(3)
        spx2, vol2, vx2 = self.spx.copy(), self.vol.copy(), self.vx.copy()
        m = spx2.index > T
        for c in ("open", "high", "low", "close"):
            spx2.loc[m, c] *= rng.uniform(0.5, 1.5, m.sum())
        for c in vol2.columns:
            vol2.loc[vol2.index > T, c] *= rng.uniform(0.5, 1.5, (vol2.index > T).sum())
        mv = vx2.trade_date > T
        vx2.loc[mv, "settle"] *= rng.uniform(0.5, 1.5, mv.sum())
        d2 = stage2.build_inputs(spx2, vol2, vx2)
        cols = ["vix", "rvtrail", *stage2.FEATURES3]
        pd.testing.assert_frame_equal(self.d.loc[:T, cols], d2.loc[:T, cols])

    def test_target_uses_t_plus_1_to_21_only(self):
        t = 300
        r = np.log(self.spx["close"] / self.spx["close"].shift(1))
        manual = self.vol["vix"].iloc[t] ** 2 - 1e4 * (252 / 21) * (r.iloc[t + 1:t + 22] ** 2).sum()
        self.assertAlmostEqual(self.d["G"].iloc[t], manual, places=8)
        spx2 = self.spx.copy()
        spx2.iloc[t + 22:, spx2.columns.get_loc("close")] *= 1.3     # beyond t+21: no effect
        self.assertAlmostEqual(stage2.build_inputs(spx2, self.vol, self.vx)["G"].iloc[t], self.d["G"].iloc[t])
        spx3 = self.spx.copy()
        spx3.iloc[t + 21, spx3.columns.get_loc("close")] *= 1.3      # inside the window: changes
        self.assertNotAlmostEqual(stage2.build_inputs(spx3, self.vol, self.vx)["G"].iloc[t], self.d["G"].iloc[t])
        self.assertTrue(self.d["G"].iloc[-21:].isna().all())


class TestSchemeAndLedger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spx, vol, vx = synth_inputs(n=2260)
        cls.d = stage2.build_inputs(spx, vol, vx)

    def test_purge_embargo_and_min_train(self):
        ev, refits = stage2.oos(self.d, "skew__raw", self.d.index[0], self.d.index[-1])
        self.assertTrue(all(r["max_train_pos"] <= r["refit_pos"] - 42 for r in refits))
        self.assertTrue(all(r["n_train"] >= 756 for r in refits))
        self.assertGreaterEqual(ev.index[0], self.d.index[refits[0]["refit_pos"]])

    def test_ledger_count_equals_runs(self):
        old = search_ledger.DB
        with tempfile.TemporaryDirectory() as tmp:
            search_ledger.DB = Path(tmp) / "t.db"
            try:
                for f in stage2.FEATURES3:
                    stage2.dev_run(self.d, f, log=True)
                self.assertEqual(search_ledger.count(), 3)
            finally:
                search_ledger.DB = old


if __name__ == "__main__":
    unittest.main()

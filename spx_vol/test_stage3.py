"""Stage 3 tests (synthetic data only; run from spx_vol/: .venv\\Scripts\\python -m unittest test_stage3 -v)."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import search_ledger
import stage2
import stage3
from common import LockedDataError
from test_stage1 import synth


def regime_lnvix(n=1300, start="2008-01-02", seed=5, k=2):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n)
    state = np.zeros(n, int)
    for i in range(1, n):
        state[i] = state[i - 1] if rng.random() < 0.98 else rng.choice([s for s in range(k) if s != state[i - 1]])
    levels, sds = np.log([15, 35, 22])[:k], np.array([0.08, 0.15, 0.10])[:k]
    x = levels[state] + rng.normal(0, sds[state])
    return pd.Series(x, index=idx), state


class TestStage3(unittest.TestCase):
    def test_guard(self):
        lv, _ = regime_lnvix(n=300, start="2016-06-01")
        with self.assertRaises(LockedDataError):
            stage3.label_full(lv, 2, search_reps=20)
        with self.assertRaises(LockedDataError):
            stage3.label_rule(np.exp(lv))

    def test_order_high_regime_last(self):
        lv, state = regime_lnvix()
        lab, _ = stage3.label_full(lv, 2, search_reps=20)
        self.assertGreater(lv[lab == 1].mean(), lv[lab == 0].mean())
        self.assertGreater((lab.to_numpy() == state).mean(), 0.9)

    def test_no_lookahead_expanding_and_rule(self):
        lv, _ = regime_lnvix()
        T = pd.Timestamp("2011-06-30")
        lv2 = lv.copy()
        m = lv2.index > T
        lv2[m] = lv2[m] + np.random.default_rng(9).normal(0, 0.1, m.sum())
        a, _ = stage3.label_expanding(lv, 2, search_reps=20)
        b, _ = stage3.label_expanding(lv2, 2, search_reps=20)
        pd.testing.assert_series_equal(a[a.index <= T], b[b.index <= T])
        ra, _ = stage3.label_rule(np.exp(lv))
        rb, _ = stage3.label_rule(np.exp(lv2))
        pd.testing.assert_series_equal(ra[ra.index <= T], rb[rb.index <= T])

    def test_ledger_count_equals_runs(self):
        lv, _ = regime_lnvix(n=1300, seed=11, k=3)
        rng = np.random.default_rng(4)
        rv = np.exp(2 * lv) * rng.uniform(0.5, 1.2, len(lv))
        d = pd.DataFrame({"vix": np.exp(lv), "rvfwd": rv, "G": np.exp(2 * lv) - rv}, index=lv.index)
        old = search_ledger.DB
        with tempfile.TemporaryDirectory() as tmp:
            search_ledger.DB = Path(tmp) / "t.db"
            try:
                out = stage3.run(d, log=True, search_reps=20)
                self.assertEqual(search_ledger.count(), 5)
                self.assertEqual(set(out["labelings"]), {"L1", "L2", "L3", "L4", "L5"})
            finally:
                search_ledger.DB = old


if __name__ == "__main__":
    unittest.main()

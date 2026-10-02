"""Unit tests for straddle_backtester.py on hand-computed trades. No network, no production DBs.
Run: python -m pytest -q test_straddle_backtester.py   (or: python test_straddle_backtester.py)"""
import math, os, sqlite3, tempfile, unittest
from datetime import date, timedelta
import straddle_backtester as sb


class Pieces(unittest.TestCase):
    def test_fill(self):
        self.assertAlmostEqual(sb.fill(1.0, 1.2, "buy", 1.0), 1.2)
        self.assertAlmostEqual(sb.fill(1.0, 1.2, "buy", 0.5), 1.15)
        self.assertAlmostEqual(sb.fill(1.0, 1.2, "buy", 0.0), 1.1)
        self.assertAlmostEqual(sb.fill(1.0, 1.2, "sell", 1.0), 1.0)
        self.assertAlmostEqual(sb.fill(1.0, 1.2, "sell", 0.5), 1.05)

    def test_straddle_payoff(self):
        self.assertEqual(sb.straddle_payoff(108, 100), 8)
        self.assertEqual(sb.straddle_payoff(93, 100), 7)
        self.assertEqual(sb.straddle_payoff(100, 100), 0)

    def test_iron_fly_payoff(self):
        # K=100, wings 90/110: owed = |S-K| capped at the wing width (10)
        for S, owed in ((100, 0), (105, 5), (110, 10), (115, 10), (95, 5), (90, 10), (70, 10)):
            self.assertAlmostEqual(sb.iron_fly_payoff(S, 100, 90, 110), owed, msg=f"S={S}")

    def test_hv252(self):
        self.assertIsNone(sb.hv252([100.0] * 252))
        flat = [100 * math.exp(0.001 * i) for i in range(253)]          # constant return -> zero vol
        self.assertAlmostEqual(sb.hv252(flat), 0.0, places=9)
        px, p = [], 100.0
        for i in range(253):                                              # +/-1% log returns alternating
            px.append(p); p *= math.exp(0.01 if i % 2 == 0 else -0.01)
        expected = math.sqrt(252 * 0.0001 / 251) * math.sqrt(252)
        self.assertAlmostEqual(sb.hv252(px), expected, places=6)

    def test_has_split(self):
        self.assertTrue(sb.has_split([1.0, 1.0, 10.0, 10.0]))   # 10:1 split inside the window
        self.assertFalse(sb.has_split([1.0, 1.001, 1.002]))     # rounding noise only

    def test_straddle_delta_expiry(self):
        self.assertEqual(sb.straddle_delta(105, 100, 0, 0.3), 1.0)
        self.assertEqual(sb.straddle_delta(95, 100, 0, 0.3), -1.0)
        self.assertAlmostEqual(sb.straddle_delta(100, 100, 30 / 365, 0.3), 2 * sb.norm_cdf(
            (0.04 + 0.045) * (30 / 365) / (0.3 * math.sqrt(30 / 365))) - 1, places=12)

    def test_hedge_constant_price(self):
        pnl, cost = sb.hedge_pnl([(30, 100.0), (29, 100.0), (28, 100.0), (0, 100.0)], 100, 0.3, 30)
        self.assertEqual(pnl, 0.0)
        self.assertGreater(cost, 0.0)

    def test_hedge_one_step(self):
        d = sb.straddle_delta(100, 100, 30 / 365, 0.3)
        pnl, _ = sb.hedge_pnl([(30, 100.0), (29, 110.0)], 100, 0.3, 30, cost_bp=0)
        self.assertAlmostEqual(pnl, -d * 10)

    def test_liquidity(self):
        self.assertTrue(sb.liquidity_ok([0.04, 0.06, 0.03], (150, 120), 2000))
        self.assertFalse(sb.liquidity_ok([0.04, 0.06, 0.07], (150, 120), 2000))   # median 6% > 5%
        self.assertFalse(sb.liquidity_ok([0.02], (150, 50), 2000))                # leg OI below 100
        self.assertFalse(sb.liquidity_ok([0.02], (150, 150), 900))                # expiry OI below 1000
        self.assertTrue(sb.liquidity_ok([0.02], (None, None), 2000))              # missing leg OI = unknown
        self.assertFalse(sb.liquidity_ok([0.02], (None, 50), 2000))               # known leg still checked

    def test_group_sizes(self):
        self.assertEqual(sb.group_sizes(25), 5)
        self.assertEqual(sb.group_sizes(24), 3)


class EndToEnd(unittest.TestCase):
    """One synthetic cycle, hand-computed: entry 2024-03-18, exit 2024-04-18, expiry 2024-04-19."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "snap.db")
        c = sqlite3.connect(self.db)
        c.execute("""CREATE TABLE chain (ticker, obs_date, kind, contract, option_type, strike, exp_date, bid, ask,
                     bid_size, ask_size, last, volume, open_interest, iv, delta, gamma, theta, vega, ask_date)""")
        rows = []
        for kind, obs, legs in (
            ("entry", "2024-03-18", [("call", 100, 2.9, 3.1, 0.30, 0.52), ("put", 100, 1.9, 2.1, 0.30, -0.48),
                                     ("call", 110, 0.45, 0.55, 0.28, 0.12), ("put", 90, 0.35, 0.45, 0.32, -0.09),
                                     ("call", 105, 1.0, 1.2, 0.29, 0.30), ("put", 95, 0.8, 1.0, 0.31, -0.25)]),
            ("exit", "2024-04-18", [("call", 100, 7.8, 8.2, 0.30, 0.95), ("put", 100, 0.0, 0.05, 0.30, -0.02)])):
            for typ, k, b, a, iv, d in legs:
                rows.append(("TST", obs, kind, f"TST{typ}{k}", typ, k, "2024-04-19", b, a, 1, 1, None, 1, 500, iv, d,
                             None, None, None, obs))
        c.executemany(f"INSERT INTO chain VALUES ({','.join('?' * 20)})", rows)
        c.commit()
        self.c = c
        self.cyc = {"entry": date(2024, 3, 18), "exit": date(2024, 4, 18), "expiry": date(2024, 4, 19), "window": "dev"}
        # 253+ closes ending at entry, flat; then a path to 108 at expiry; raw == split (no split)
        d0 = date(2023, 1, 2)
        self.prices = {}
        d, i = d0, 0
        while d <= self.cyc["expiry"]:
            if d.weekday() < 5:
                px = 100.0 if d <= self.cyc["entry"] else 100.0 + 8.0 * min(1, (d - self.cyc["entry"]).days / 32)
                self.prices[d] = (px, px)
            d += timedelta(days=1)

    def tearDown(self):
        self.c.close()

    def test_trade(self):
        r = sb.evaluate(self.c, "TST", self.cyc, self.prices, {"TST": [date(2024, 4, 10)]}, {})
        self.assertIsNone(r["excluded"])
        self.assertEqual(r["K"], 100)
        self.assertEqual(r["ST"], 108.0)
        self.assertAlmostEqual(r["iv"], 0.30)
        self.assertAlmostEqual(r["hv"], 0.0, places=9)                  # flat history
        self.assertAlmostEqual(r["signal"], -0.30)
        # long at ask: cost 3.1 + 2.1 = 5.2, payoff 8 -> (8 - 5.2)/5.2
        self.assertAlmostEqual(r["long_exp_f100"], (8 - 5.2) / 5.2)
        # at mid: cost 5.0 -> 0.6
        self.assertAlmostEqual(r["long_exp_f000"], 0.6)
        # short straddle at bid: credit 2.9 + 1.9 = 4.8, owes 8 -> (4.8 - 8)/4.8 ; at mid exactly -0.6
        self.assertAlmostEqual(r["shortstrad_exp_f100"], (4.8 - 8) / 4.8)
        self.assertAlmostEqual(r["shortstrad_exp_f000"], -0.6)
        # day-before exit at bid: 7.8 + 0.0 = 7.8 -> (7.8 - 5.2)/5.2
        self.assertAlmostEqual(r["long_db_f100"], (7.8 - 5.2) / 5.2)
        # iron fly at quoted: credit = 2.9 + 1.9 - 0.55 (110C ask) - 0.45 (90P ask) = 3.8 ; wings 110/90 ;
        # max loss 10 - 3.8 = 6.2 ; owed at S=108: 8 -> (3.8 - 8)/6.2
        self.assertEqual((r["wing_call"], r["wing_put"]), (110, 90))
        self.assertAlmostEqual(r["fly_exp_f100"], (3.8 - 8) / 6.2)
        # at mid: credit = 3.0 + 2.0 - 0.5 - 0.4 = 4.1 ; max loss 5.9 -> (4.1 - 8)/5.9
        self.assertAlmostEqual(r["fly_exp_f000"], (4.1 - 8) / 5.9)
        # full spread = (3.1+2.1-2.9-1.9)/5.0 = 0.08 -> fails the 5% liquidity rule
        self.assertAlmostEqual(r["full_spread"], 0.08)
        self.assertEqual(r["eligible"], 0)
        self.assertEqual(r["earnings_in_window"], 1)

    def test_split_excluded(self):
        p = dict(self.prices)
        for d in p:
            if d > date(2024, 4, 1):
                p[d] = (p[d][0] / 10, p[d][1])                              # raw drops 10:1, adjusted does not
        r = sb.evaluate(self.c, "TST", self.cyc, p, {"TST": None}, {})
        self.assertEqual(r["excluded"], "split_in_window")

    def test_unknown_earnings_is_none(self):
        r = sb.evaluate(self.c, "TST", self.cyc, self.prices, {"TST": None}, {})
        self.assertIsNone(r["earnings_in_window"])

    def test_blind_refused(self):
        with self.assertRaises(PermissionError):
            sb.run("blind")


if __name__ == "__main__":
    unittest.main(verbosity=2)

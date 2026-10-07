"""Unit tests for paper_putspread_trial.py (no network, no orders).  Run:  python -m unittest test_paper_putspread_trial -v"""
import os
import unittest
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

import paper_putspread_trial as t
from paper_putspread_trial import Leg

ET = t.ET


def weekdays(start, n):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def chain(exp, deltas_by_strike, bid=1.0, ask=1.02):
    return {exp: [Leg(f"P{k:g}", k, dl, bid, ask) for k, dl in deltas_by_strike.items()]}


class PaperOnly(unittest.TestCase):
    def test_paper_client_passes(self):
        from alpaca.trading.client import TradingClient
        t.assert_paper_client(TradingClient("k", "s", paper=True))

    def test_live_client_aborts(self):
        from alpaca.trading.client import TradingClient
        with self.assertRaises(SystemExit):
            t.assert_paper_client(TradingClient("k", "s", paper=False))

    def test_missing_url_aborts(self):
        with self.assertRaises(SystemExit):
            t.assert_paper_client(SimpleNamespace())

    def test_account_number(self):
        t.assert_paper_account(SimpleNamespace(account_number="PA3XXXXXXX"))
        for bad in ("3XXXXXXX", "", None):
            with self.assertRaises(SystemExit):
                t.assert_paper_account(SimpleNamespace(account_number=bad))

    def test_no_order_submission_code(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_putspread_trial.py"),
                  encoding="utf-8") as f:
            src = f.read()
        for word in ("submit_order", "replace_order", "close_position", "close_all_positions"):
            self.assertNotIn(word + "(", src)

    def test_cli_refuses_without_dry_run(self):
        with self.assertRaises(SystemExit):
            t.main([])


class Calendar(unittest.TestCase):
    def test_entry_monday_and_holiday(self):
        s = set(weekdays(date(2026, 9, 1), 20)) - {date(2026, 9, 7)}
        self.assertEqual(t.entry_session(date(2026, 9, 10), s), date(2026, 9, 8))   # Labor Day -> Tuesday
        self.assertEqual(t.entry_session(date(2026, 9, 16), s), date(2026, 9, 14))

    def test_time_exit_session(self):
        s = weekdays(date(2026, 10, 5), 12)
        self.assertEqual(t.time_exit_session(date(2026, 10, 16), s), date(2026, 10, 14))
        self.assertEqual(t.time_exit_session(date(2026, 10, 19), s), date(2026, 10, 15))  # Monday expiry

    def test_early_close_clock(self):
        self.assertEqual(t.time_exit_clock(time(16, 0)), time(15, 45))
        self.assertEqual(t.time_exit_clock(time(13, 0)), time(12, 45))
        self.assertEqual(t.exit_check_times(time(13, 0)), [time(10), time(11), time(12), time(12, 45)])
        self.assertEqual(t.exit_check_times()[-1], time(15, 45))


class Expiry(unittest.TestCase):
    def test_first_in_window(self):
        e = date(2026, 10, 5)
        exps = [date(2026, 10, 14), date(2026, 10, 15), date(2026, 10, 16), date(2026, 10, 19), date(2026, 10, 20)]
        self.assertEqual(t.choose_expiry(e, exps), date(2026, 10, 15))   # 9 days excluded, 10 chosen

    def test_none_in_window(self):
        self.assertIsNone(t.choose_expiry(date(2026, 10, 5), [date(2026, 10, 14), date(2026, 10, 20)]))


class StrikeSelection(unittest.TestCase):
    def test_closest_to_015(self):
        p = [Leg("a", 700, -0.12, 1, 1.1), Leg("b", 705, -0.16, 1, 1.1), Leg("c", 710, -0.21, 1, 1.1)]
        self.assertEqual(t.select_short_put(p)[0].strike, 705)

    def test_tie_goes_to_lower_strike(self):
        p = [Leg("a", 700, -0.13, 1, 1.1), Leg("b", 705, -0.17, 1, 1.1)]
        self.assertEqual(t.select_short_put(p)[0].strike, 700)

    def test_missing_greeks_skip(self):
        leg, why = t.select_short_put([Leg("a", 700, None, 1, 1.1)])
        self.assertIsNone(leg)
        self.assertIn("greeks missing", why)

    def test_out_of_band_skip(self):
        leg, why = t.select_short_put([Leg("a", 700, -0.08, 1, 1.1), Leg("b", 710, -0.25, 1, 1.1)])
        self.assertIsNone(leg)
        self.assertIn("no strike", why)

    def test_missing_delta_ignored_not_skipped(self):
        p = [Leg("a", 700, None, 1, 1.1), Leg("b", 705, -0.15, 1, 1.1)]
        self.assertEqual(t.select_short_put(p)[0].strike, 705)

    def test_band_edges_inclusive(self):
        self.assertIsNotNone(t.select_short_put([Leg("a", 700, -0.10, 1, 1.1)])[0])
        self.assertIsNotNone(t.select_short_put([Leg("a", 700, -0.20, 1, 1.1)])[0])


class Sizing(unittest.TestCase):
    def test_basic(self):
        n, mlpc, why = t.size_position(100000, 0.45)
        self.assertEqual((n, mlpc, why), (2, 455.0, None))   # floor(1000 / 455) = 2

    def test_minimum_one(self):
        n, mlpc, why = t.size_position(40000, 0.45)           # 1% = 400 < 455, 1.5% = 600 >= 455
        self.assertEqual((n, why), (1, None))

    def test_one_contract_too_big_skip(self):
        n, mlpc, why = t.size_position(30000, 0.45)           # 1.5% = 450 < 455
        self.assertEqual(n, 0)
        self.assertIn("1.5%", why)

    def test_total_cap_reduces_then_skips(self):
        self.assertEqual(t.size_position(100000, 0.45, open_max_loss=1500)[0], 1)   # room 500 -> 1 contract
        n, _, why = t.size_position(100000, 0.45, open_max_loss=1600)              # room 400 -> 0
        self.assertEqual(n, 0)
        self.assertIn("2%", why)

    def test_bad_credit(self):
        self.assertEqual(t.size_position(100000, 0.0)[0], 0)
        self.assertEqual(t.size_position(100000, 5.0)[0], 0)


class EntrySkipRules(unittest.TestCase):
    E = date(2026, 10, 5)
    X = date(2026, 10, 16)

    def puts(self, short_bid=1.30, short_ask=1.31, long_bid=0.85, long_ask=0.86, long_strike=758):
        return {self.X: [Leg("S", 763, -0.15, short_bid, short_ask), Leg("L", long_strike, -0.10, long_bid, long_ask)]}

    def test_open(self):
        d = t.evaluate_entry(self.E, 93392.13, 93392.13, 0, self.puts())
        self.assertEqual(d["action"], "open")
        self.assertEqual((d["contracts"], d["intended_credit"], d["max_loss"]), (2, 0.45, 910.0))

    def test_pause_rule(self):
        d = t.evaluate_entry(self.E, 95000, 100000, 0, self.puts())
        self.assertEqual(d["action"], "skip")
        self.assertIn("PAUSE", d["skip_reason"])
        self.assertEqual(t.evaluate_entry(self.E, 95001, 100000, 0, self.puts())["action"], "open")

    def test_once_per_week(self):
        d = t.evaluate_entry(self.E, 1e5, 1e5, 0, self.puts(), already_entered_this_week=True)
        self.assertIn("already", d["skip_reason"])

    def test_no_bid_skip(self):
        d = t.evaluate_entry(self.E, 1e5, 1e5, 0, self.puts(long_bid=0.0))
        self.assertIn("long leg has no bid", d["skip_reason"])

    def test_long_strike_missing(self):
        d = t.evaluate_entry(self.E, 1e5, 1e5, 0, self.puts(long_strike=757))
        self.assertIn("not listed", d["skip_reason"])

    def test_width_rule(self):
        # spread bid = 1.30-0.90 = 0.40, ask = 1.36-0.85 = 0.51 -> width 0.11 > 15% of 0.455
        d = t.evaluate_entry(self.E, 1e5, 1e5, 0, self.puts(short_ask=1.36, long_ask=0.90))
        self.assertIn("15%", d["skip_reason"])

    def test_width_rule_boundary_passes(self):
        # bid 1.36-0.99 = 0.37, ask 1.39-0.96 = 0.43: mid 0.40, width 0.06 = exactly 15% (allowed)
        d = t.evaluate_entry(self.E, 1e5, 1e5, 0, self.puts(short_bid=1.36, short_ask=1.39, long_bid=0.96,
                                                              long_ask=0.99))
        self.assertEqual(d["width_pct_of_mid"], 15.0)
        self.assertEqual(d["action"], "open")

    def test_no_expiry(self):
        d = t.evaluate_entry(self.E, 1e5, 1e5, 0, {date(2026, 10, 20): []})
        self.assertIn("no listed expiration", d["skip_reason"])


class ExitRules(unittest.TestCase):
    S = {d: time(16, 0) for d in weekdays(date(2026, 10, 5), 12)}
    P = {"expiry": date(2026, 10, 16), "credit": 0.80}

    def run_(self, now, s, l):
        return t.check_exit(self.P, now, Leg("S", 650, -0.15, *s), Leg("L", 645, -0.1, *l), self.S)

    def test_hold(self):
        self.assertEqual(self.run_(datetime(2026, 10, 7, 11, tzinfo=ET), (1.0, 1.05), (0.4, 0.45))["action"], "hold")

    def test_take_profit_boundary(self):
        r = self.run_(datetime(2026, 10, 8, 12, tzinfo=ET), (0.60, 0.61), (0.21, 0.22))   # natural 0.40
        self.assertEqual(r["reason"], "take_profit")
        r = self.run_(datetime(2026, 10, 8, 12, tzinfo=ET), (0.60, 0.62), (0.21, 0.22))   # natural 0.41
        self.assertEqual(r["action"], "hold")

    def test_take_profit_uses_natural_not_mid(self):
        r = self.run_(datetime(2026, 10, 8, 12, tzinfo=ET), (0.50, 0.70), (0.20, 0.22))   # mid 0.39, natural 0.50
        self.assertEqual(r["action"], "hold")

    def test_stop_boundary(self):
        r = self.run_(datetime(2026, 10, 9, 14, tzinfo=ET), (2.5, 2.6), (1.0, 1.05))      # natural 1.60
        self.assertEqual(r["reason"], "stop")
        r = self.run_(datetime(2026, 10, 9, 14, tzinfo=ET), (2.5, 2.59), (1.0, 1.05))     # natural 1.59
        self.assertEqual(r["action"], "hold")

    def test_time_exit(self):
        self.assertEqual(self.run_(datetime(2026, 10, 14, 15, 45, tzinfo=ET), (0.9, 0.95), (0.3, 0.35))["reason"],
                         "time_exit")
        self.assertEqual(self.run_(datetime(2026, 10, 14, 15, 44, tzinfo=ET), (0.9, 0.95), (0.3, 0.35))["action"],
                         "hold")
        self.assertEqual(self.run_(datetime(2026, 10, 15, 10, tzinfo=ET), (0.9, 0.95), (0.3, 0.35))["reason"],
                         "time_exit")   # missed check -> close at the next one

    def test_stop_has_priority(self):
        r = self.run_(datetime(2026, 10, 14, 15, 45, tzinfo=ET), (2.5, 2.6), (1.0, 1.05))
        self.assertEqual((r["reason"], r["triggered"]), ("stop", ["stop", "time_exit"]))

    def test_bad_quotes_still_time_exit(self):
        r = t.check_exit(self.P, datetime(2026, 10, 14, 15, 50, tzinfo=ET), Leg("S", 650, None, None, None),
                         Leg("L", 645, None, 0.1, 0.2), self.S)
        self.assertEqual(r["reason"], "time_exit")
        self.assertIn("quote_problem", r)


class FillsAndBenchmarks(unittest.TestCase):
    def test_three_fills(self):
        r = t.pnl_three(2, entry_mid=0.45, entry_width=0.04, exit_mid=0.20, exit_width=0.04)
        self.assertEqual(r["conservative"], round((0.43 - 0.22) * 200, 2))
        self.assertEqual(r["stress"], round((0.41 - 0.24) * 200, 2))
        self.assertIsNone(r["paper_actual"])
        self.assertEqual(r["headline"], r["conservative"])
        self.assertEqual(t.pnl_three(1, 0.45, 0.04, 0.2, 0.04, 0.44, 0.21)["paper_actual"], 23.0)

    def test_benchmarks(self):
        self.assertEqual(t.tbill_benchmark(1000, 0.04, date(2026, 1, 1), date(2027, 1, 1)), 40.0)
        self.assertEqual(t.tbill_benchmark(910, 0.0365, date(2026, 10, 5), date(2026, 10, 15)), 0.91)
        self.assertAlmostEqual(t.spy_buy_hold_return(700, 714), 0.02)


if __name__ == "__main__":
    unittest.main()

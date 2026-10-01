from dotenv import load_dotenv
load_dotenv()

"""Continuous live-loop for the options strategy.

Runs check_signal_and_trade_options() on the same validated tickers, on the
same schedule as the stock bot. Every check is logged to
options_signal_log.db for later review, regardless of mode.

Whether real (paper) orders get placed is controlled entirely by
live_options_trader.py's OPTIONS_SHADOW_MODE flag, NOT by this file --
this loop is just the scheduler. [CORRECTED 2026-09-20: this docstring
previously and incorrectly claimed "places NO real orders". That has not
been true since OPTIONS_SHADOW_MODE was set to False ("LIVE as of first
supervised test") in live_options_trader.py -- this loop does submit real
(paper) orders whenever that flag is False and the market is open. Still
paper-only (see CLAUDE.md Section 8), no real capital at risk, but do not
assume "shadow" from this file's name alone -- check the flag.]
"""

import time
from datetime import datetime
from pathlib import Path

from live_options_trader import check_signal_and_trade_options, OPTIONS_SHADOW_MODE
from options_exit_monitor import check_and_close_options_positions
from uptime_log import log_heartbeat
from pattern_review import generate_pattern_review
from daily_price_audit import should_run_daily_audit, run_daily_price_audit
from account_review import should_run_weekly_account_review, generate_account_review
import sqlite3 as _sqlite3
from datetime import datetime as _datetime, timezone as _timezone, timedelta as _timedelta
import options_kill_server
from main import is_market_open, market_closed_for_day, minutes_to_open, idle_until_next_et_day, ET

from main import LIVE_TICKERS
OPTIONS_TICKERS = LIVE_TICKERS
OPTIONS_CYCLE_INTERVAL_SEC = 300  # 5 minutes, same cadence as the stock bot
EXIT_CHECK_INTERVAL_SEC = 60  # check open positions every 1 minute, independent of entry checks
KILL_SWITCH_PATH = Path("STOP_TRADING")


def run_options_shadow_cycle() -> list[dict]:
    """Run one options check cycle across all tickers. Places real (paper)
    orders on a fired signal unless live_options_trader.OPTIONS_SHADOW_MODE
    is True -- see this module's docstring."""
    now_str = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
    signal_label = "SHADOW SIGNAL" if OPTIONS_SHADOW_MODE else "LIVE SIGNAL (paper order)"
    check_label = "OPTIONS SHADOW CHECK" if OPTIONS_SHADOW_MODE else "OPTIONS LIVE CHECK (paper)"
    print("\n" + "=" * 68)
    print("  " + check_label + "  --  " + now_str)
    print("=" * 68)

    results = []
    for ticker in OPTIONS_TICKERS:
        print("\n  Checking " + ticker + " (options)...")
        result = check_signal_and_trade_options(ticker)
        results.append(result)
        if result["signal_fired"]:
            print("    [" + signal_label + "] " + str(result["note"]))
        else:
            print("    -  No signal  ->  " + str(result["note"]))

    fired = [r for r in results if r["signal_fired"]]
    print("\n" + "-" * 68)
    print("  Options checked: " + str(len(results)) + "  |  Signals fired: " + str(len(fired)))
    print("-" * 68)
    return results


def run_options_shadow_loop() -> None:
    """Continuously run the options checker during market hours. Whether
    this places real (paper) orders depends on OPTIONS_SHADOW_MODE in
    live_options_trader.py -- see this module's docstring."""
    options_kill_server.start()
    mode_banner = ("OPTIONS SHADOW LOOP -- paper analysis only, NO orders placed" if OPTIONS_SHADOW_MODE
                    else "OPTIONS LIVE LOOP -- OPTIONS_SHADOW_MODE=False, submits REAL (paper) orders")
    print("\n" + "#" * 68)
    print("  " + mode_banner)
    print("  Tickers : " + ", ".join(OPTIONS_TICKERS))
    print("  Interval: every " + str(OPTIONS_CYCLE_INTERVAL_SEC // 60) + " minutes during market hours")
    print("#" * 68 + "\n")

    entry_check_counter = 0
    while True:
        if KILL_SWITCH_PATH.exists():
            print("  STOP_TRADING file present -- options shadow loop paused too. Rechecking in 60s.")
            time.sleep(60)
            continue

        if market_closed_for_day():
            print("  Market closed for today. Idling until midnight ET, then exiting cleanly.")
            idle_until_next_et_day()  # see main.py: avoids ~450 NSSM restarts per evening
            return

        if not is_market_open():
            mins = minutes_to_open()
            if mins > 0:
                print("  Pre-market -- opens in " + str(mins) + " min. Sleeping 60s.")
            else:
                print("  Market closed. Sleeping 60s.")
            time.sleep(60)
            continue

        log_heartbeat("OptionsShadowLoop")
        _should_run_pattern_review = False
        try:
            with _sqlite3.connect("pattern_reviews.db") as _conn:
                _row = _conn.execute("SELECT generated_at FROM pattern_reviews ORDER BY generated_at DESC LIMIT 1").fetchone()
            if _row is None:
                _should_run_pattern_review = True
            else:
                _last = _datetime.fromisoformat(_row[0])
                if (_datetime.now(_timezone.utc) - _last) >= _timedelta(days=7):
                    _should_run_pattern_review = True
        except Exception:
            _should_run_pattern_review = False

        if _should_run_pattern_review:
            try:
                generate_pattern_review(days=7)
                print("  Weekly pattern review generated.")
            except Exception as _pr_exc:
                print("  Weekly pattern review failed: " + str(_pr_exc))

        if should_run_daily_audit():
            try:
                audit_result = run_daily_price_audit()
                print("  Daily price audit: checked " + str(audit_result["trades_checked"]) + " trades, corrected " + str(audit_result["mismatches_found"]) + " mismatch(es).")
            except Exception as _audit_exc:
                print("  Daily price audit failed: " + str(_audit_exc))

        if should_run_weekly_account_review():
            try:
                _account_review_text = generate_account_review()
                print("  Weekly account review generated (" + str(len(_account_review_text)) + " chars).")
            except Exception as _review_exc:
                print("  Weekly account review failed: " + str(_review_exc))

        entry_check_counter += 1
        if entry_check_counter >= (OPTIONS_CYCLE_INTERVAL_SEC // EXIT_CHECK_INTERVAL_SEC):
            entry_check_counter = 0
            run_options_shadow_cycle()

        try:
            closed = check_and_close_options_positions()
            if closed:
                print("  Closed " + str(closed) + " options position(s) this cycle.")
        except Exception as exc:
            print("  Exit monitor check failed: " + str(exc))

        # Execution-cost Stream B quote sampler (2026-10-01): pure logging, no orders, never blocks trading.
        try:
            import execution_cost_logger
            execution_cost_logger.sample_once()
        except Exception as _ec_exc:
            print("  Execution-cost quote sample failed: " + str(_ec_exc)[:200])

        print("  Sleeping " + str(EXIT_CHECK_INTERVAL_SEC) + "s before next exit check...")
        time.sleep(EXIT_CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    run_options_shadow_loop()
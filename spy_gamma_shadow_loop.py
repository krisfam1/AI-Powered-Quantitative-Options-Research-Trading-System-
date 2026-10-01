from dotenv import load_dotenv
load_dotenv()

"""
SPY gamma bot -- continuous shadow loop.

Mirrors the main options bot's loop structure: entry checks every 5
minutes, exit checks every 1 minute, real heartbeat logging so uptime
monitoring covers this bot too. Runs as its own NSSM service,
independent of the main OptionsShadowLoop.

Stays in SPY_GAMMA_SHADOW_MODE until explicitly, deliberately reviewed
and switched live in a future, clear-headed session.

Added 2026-09-21: this loop previously had no kill switch and never
checked the shared STOP_TRADING file at all -- unlike the stock bot and
options bot, stopping it required stopping the whole Windows Service.
Now starts spy_gamma_kill_server.py (port 8099, already provisioned in
.replit but previously unused) and checks STOP_FILE every cycle, exactly
matching the pattern in options_shadow_loop.py.
"""

import time
from datetime import datetime, timezone
from pathlib import Path
from spy_gamma_execution import check_and_enter_spy_gamma, check_and_close_spy_gamma_positions
from main import is_market_open
from uptime_log import log_heartbeat
import spy_gamma_kill_server

STOP_FILE = Path("STOP_TRADING")
ENTRY_CHECK_INTERVAL_SECONDS = 60  # 1 minute -- matches exit check cadence, given this bot's day-trading design benefits from prompt entries
EXIT_CHECK_INTERVAL_SECONDS = 60    # 1 minute

if __name__ == "__main__":
    spy_gamma_kill_server.start()
    print("SPY gamma shadow loop starting...")
    entry_check_counter = 0

    while True:
        if STOP_FILE.exists():
            print("  STOP_TRADING file present -- SPY gamma loop paused too. Rechecking in 60s.")
            time.sleep(60)
            continue

        try:
            if is_market_open():
                try:
                    log_heartbeat("SpyGammaLoop")
                except Exception:
                    pass

                exit_result = check_and_close_spy_gamma_positions()

                entry_check_counter += 1
                if entry_check_counter >= (ENTRY_CHECK_INTERVAL_SECONDS // EXIT_CHECK_INTERVAL_SECONDS):
                    entry_result = check_and_enter_spy_gamma()
                    print(str(datetime.now(timezone.utc)) + " -- " + entry_result.get("note", "no note"))
                    entry_check_counter = 0
            else:
                pass  # market closed, just wait

        except Exception as exc:
            print("Loop error (continuing): " + str(exc))

        time.sleep(EXIT_CHECK_INTERVAL_SECONDS)
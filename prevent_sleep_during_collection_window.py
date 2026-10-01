"""
prevent_sleep_during_collection_window.py

Self-expiring sleep-prevention window for the nightly data-collection tasks.

WHY THIS EXISTS (2026-09-30/10-01, CLAUDE.md Section 60): three separate
scheduled tasks (GEX_Historical_Incremental_Update, GEX_Prospective_Daily_
Collection, RF_v2_Stage2_Nightly_Update) were all killed by
STATUS_CONTROL_C_EXIT in the same few minutes one night, correlated with a
real "exiting Modern Standby" system event -- confirming a machine-wide
sleep/wake interruption, not a per-script bug. Enabling WakeToRun on every
task (done the same day) only fixes the case where the machine is ALREADY
asleep at the exact trigger moment -- it does nothing to protect a task
that is actively running when the machine decides to sleep partway
through. This script fixes that second case.

WHAT IT DOES: calls the documented Windows API SetThreadExecutionState
with ES_SYSTEM_REQUIRED (and ES_AWAYMODE_REQUIRED, the standard additional
flag for suppressing Modern Standby specifically, not just legacy S3
sleep) to tell Windows "don't sleep while this process is alive", holds
that state for a fixed window (default 65 minutes -- covers 19:45 through
20:50 ET, with a few minutes of margin on both ends), then explicitly
releases the flag and exits. Nothing about this is permanent: no power
plan setting is changed, nothing needs to be manually undone, and normal
sleep behavior resumes the instant this process exits (either naturally
after the window or if killed itself).

NOT a guarantee against every possible interruption (a real lid-close or
power button press can still force sleep), but it directly counters the
specific "idle system auto-enters Modern Standby" mechanism that this
project's own event-log evidence points to.
"""

import ctypes
import sys
import time

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_AWAYMODE_REQUIRED = 0x00000040

WINDOW_MINUTES = 65


def main():
    minutes = WINDOW_MINUTES
    if len(sys.argv) > 1:
        try:
            minutes = int(sys.argv[1])
        except ValueError:
            pass

    print(f"Preventing system sleep for {minutes} minutes (ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED)...", flush=True)
    ctypes.windll.kernel32.SetThreadExecutionState(
        ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
    )
    try:
        time.sleep(minutes * 60)
    finally:
        # ALWAYS release the flag, even on an unexpected exit path --
        # normal sleep behavior must resume, this must never be permanent.
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        print("Sleep-prevention window ended -- normal sleep behavior restored.", flush=True)


if __name__ == "__main__":
    main()

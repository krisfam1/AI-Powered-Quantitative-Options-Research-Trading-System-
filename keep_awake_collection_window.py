"""
keep_awake_collection_window.py -- keep the laptop out of Modern Standby during the nightly
data-collection window (weekdays 19:40-21:20 ET). Replaces prevent_sleep_during_collection_window.py
(retired 2026-10-05, CLAUDE.md Section 60).

WHY THE OLD SCRIPT FAILED (event logs, 2026-10-04): this machine's sleep timeout is already "never";
it enters Modern Standby when the DISPLAY turns off (5 min on AC, 3 min on battery). The old script
held only ES_SYSTEM_REQUIRED (+ ES_AWAYMODE_REQUIRED), which does not stop display-off, so the
machine re-entered Modern Standby one second after its wake timer fired. Its Python process was then
suspended, and because it slept for a fixed 65 minutes of *process* time it only ended ~20 hours later.

WHAT THIS DOES
  - Holds ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED, re-asserted every 60 s.
  - Ends at a WALL-CLOCK time (default 21:20 ET today), so a suspended process still exits as soon
    as it resumes past the end time. Started after the end time, it exits at once.
  - Releases the request on every exit path (normal end, exception, Ctrl+C). Nothing persistent is
    changed: no power-plan or registry setting.
  - Logs a heartbeat every minute with AC/battery status, so a gap > 3 min proves the machine slept
    anyway (e.g. lid closed). The health check reads those gaps.

LIMITS (disclosed): it cannot stop a lid-close or power-button sleep, and if the machine is already
in Modern Standby when the 19:40 wake timer fires, whether a display request from a woken background
task keeps it awake is untested on this machine -- the heartbeat log will show it.

  pythonw run_logged.py keep_awake_collection_window.py keep_awake_log.txt      (scheduled)
  python keep_awake_collection_window.py --end 21:20                              (manual)
"""
import ctypes
import sys
import time
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
DEFAULT_END = dtime(21, 20)
HEARTBEAT_SEC = 60


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte), ("SystemStatusFlag", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]


def power_source():
    s = SYSTEM_POWER_STATUS()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
        return "unknown"
    src = {0: "battery", 1: "AC"}.get(s.ACLineStatus, "unknown")
    pct = s.BatteryLifePercent if 0 <= s.BatteryLifePercent <= 100 else "?"
    return f"{src}, battery {pct}%"


def parse_end(argv):
    if "--end" in argv:
        hh, mm = argv[argv.index("--end") + 1].split(":")
        return dtime(int(hh), int(mm))
    return DEFAULT_END


def main(argv):
    now = datetime.now(ET)
    end = datetime.combine(now.date(), parse_end(argv), tzinfo=ET)
    print(f"KEEP-AWAKE WINDOW START -- {now.isoformat()} | until {end:%H:%M} ET | {power_source()}", flush=True)
    if now >= end:
        print(f"KEEP-AWAKE WINDOW END -- {now.isoformat()} | started after the end time, nothing held", flush=True)
        return
    flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
    try:
        while True:
            if not ctypes.windll.kernel32.SetThreadExecutionState(flags):
                print("WARNING: SetThreadExecutionState failed", flush=True)
            now = datetime.now(ET)
            if now >= end:
                break
            print(f"heartbeat {now.isoformat()} | {power_source()}", flush=True)
            time.sleep(max(1, min(HEARTBEAT_SEC, (end - now).total_seconds())))
    finally:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)  # release on every exit path
        print(f"KEEP-AWAKE WINDOW END -- {datetime.now(ET).isoformat()} | display/system request released", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])

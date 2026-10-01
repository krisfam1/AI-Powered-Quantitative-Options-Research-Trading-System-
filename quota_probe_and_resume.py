"""
Durable quota probe + backfill resume + GEX historical catch-up
(CLAUDE.md Section 60, 2026-10-01). Replaces Claude Code session job 323501bc
(which replaced 6d005d8e / 1fe19d18) with the same logic, run by the Windows
Scheduled Task `EODHD_Quota_Probe_And_Resume` every 2h via
`pythonw.exe run_logged.py quota_probe_and_resume.py quota_probe_and_resume_log.txt`
-- windowless, survives reboots, no 7-day expiry.

Each run:
 1. Probe the real UnicornBay endpoint exactly once (single_quota_test.py), no retry.
 2. On 429/FAILED: append one row to quota_probe_log.db (table probe_log). Nothing else.
 3. On SUCCESS:
    [BACKFILL]      if the 59-ticker backfill is incomplete and not already running,
                    clear a stale lock and launch it detached; confirm exactly one
                    process ~30s later.
    [GEX CATCH-UP]  run gex_gap_check.py (the updater's own scan rule); if anything is
                    missing, trigger the real GEX_Historical_Incremental_Update task via
                    schtasks /run, wait up to 10 min, re-check, classify.
    Each gets its own row (category BACKFILL / GEX) in quota_probe_log.db.

`--dry-run-success` (testing only): skip the probe and treat it as SUCCESS; launch a
dummy 60s pythonw child instead of the backfill (exercises detach + process
detection); run the gap check but do NOT trigger the GEX task; log to a scratch DB in
%TEMP% instead of quota_probe_log.db. Makes no EODHD calls. Never touches CLAUDE.md.
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone

import psutil

ROOT = r"C:\Users\fmkri\Downloads\Python-Backend\Python-Backend"
PYTHONW = r"C:\Users\fmkri\AppData\Local\Programs\Python\Python314\pythonw.exe"
# Probe results are logged to this SQLite table, NOT to CLAUDE.md (decoupled 2026-10-01).
PROBE_LOG_DB = os.path.join(ROOT, "quota_probe_log.db")
DRY_RUN_DB = os.path.join(os.environ.get("TEMP", ROOT), "quota_probe_log.dryrun.db")
BACKFILL_SCRIPT = "generate_broader_universe_volatility_dataset.py"
BACKFILL_DB = os.path.join(ROOT, "broader_universe_volatility_dataset.db")
BACKFILL_LOCK = os.path.join(ROOT, "broader_universe_volatility_generation.lock")
BACKFILL_STDOUT_LOG = os.path.join(ROOT, "broader_universe_volatility_update_stdout_log.txt")
GEX_TASK = "GEX_Historical_Incremental_Update"
NO_WINDOW = subprocess.CREATE_NO_WINDOW
DETACH = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_BREAKAWAY_FROM_JOB
DRY = "--dry-run-success" in sys.argv

os.chdir(ROOT)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def run(args, timeout=600):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                          creationflags=NO_WINDOW, cwd=ROOT)


def append_probe_rows(rows):
    """Append rows to quota_probe_log.db (table probe_log). DECOUPLED from CLAUDE.md 2026-10-01:
    this used to parse CLAUDE.md for a heading and insert markdown rows, and a doc edit broke it
    (StopIteration at 12:23 and 14:23 ET). CLAUDE.md is now human-only; nothing here reads or
    writes it. A dry run writes to a scratch copy of the DB in %TEMP% instead."""
    target = DRY_RUN_DB if DRY else PROBE_LOG_DB
    with sqlite3.connect(target) as c:
        c.execute("CREATE TABLE IF NOT EXISTS probe_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                  "utc_ts TEXT NOT NULL, result TEXT NOT NULL, category TEXT NOT NULL, action TEXT NOT NULL, "
                  "dry_run INTEGER NOT NULL DEFAULT 0)")
        c.executemany("INSERT INTO probe_log (utc_ts, result, category, action, dry_run) VALUES (?,?,?,?,?)",
                      [(ts, res, cat, act, int(DRY)) for ts, res, cat, act in rows])
    for r in rows:
        print(("DRY-RUN -> " + target + ":" if DRY else "logged:"), " | ".join(r))


def row(ts, result, action):
    category = "BACKFILL" if action.startswith("[BACKFILL]") else "GEX" if action.startswith("[GEX CATCH-UP]") else "PROBE"
    return (ts, result, category, action)


# ---------------------------------------------------------------- backfill
def backfill_status():
    import generate_broader_universe_volatility_dataset as bf
    c = sqlite3.connect(BACKFILL_DB)
    s = dict(c.execute("SELECT ticker, COUNT(*) FROM volatility_training_examples GROUP BY ticker"))
    e = dict(c.execute("SELECT ticker, COUNT(*) FROM volatility_excluded GROUP BY ticker"))
    c.close()
    tot = {t: s.get(t, 0) + e.get(t, 0) for t in bf.TICKERS}
    top = max(tot.values()) or 1
    done = [t for t, v in tot.items() if v >= 0.97 * top]
    partial = {t: v for t, v in tot.items() if 0 < v < 0.97 * top}
    return len(done) == len(bf.TICKERS), len(done), len(bf.TICKERS), partial


def backfill_procs(marker):
    out = []
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            if any(marker in a for a in (p.info["cmdline"] or [])):
                out.append(p.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return out


TARGET_C_RETIRED = True   # 2026-10-01: Target C retired; its quota goes to the option snapshot collector


def do_backfill():
    if TARGET_C_RETIRED and not DRY:
        return "[BACKFILL] retired 2026-10-01 (Target C design retired; not relaunched)"
    complete, n_done, n_all, partial = backfill_status()
    if complete:
        return f"[BACKFILL] complete ({n_done}/{n_all}), nothing to do"
    marker = "dryrun_backfill_stand_in" if DRY else BACKFILL_SCRIPT
    running = backfill_procs(marker)
    if running:
        return f"[BACKFILL] already running (PID {running}); {n_done}/{n_all} done, partial {partial}"
    note = ""
    if not DRY and os.path.exists(BACKFILL_LOCK):
        os.remove(BACKFILL_LOCK)
        note = "stale lock removed; "
    if DRY:
        cmd = [PYTHONW, "-c", "import time; time.sleep(60)  # dryrun_backfill_stand_in"]
    else:
        cmd = [PYTHONW, os.path.join(ROOT, BACKFILL_SCRIPT)]
    out_fh = open(BACKFILL_STDOUT_LOG, "ab")
    try:
        subprocess.Popen(cmd, cwd=ROOT, stdout=out_fh, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, creationflags=DETACH, close_fds=True)
    except OSError:
        # Job object forbids breakaway: launch without it (child may then share the task's lifetime).
        note += "no job breakaway; "
        subprocess.Popen(cmd, cwd=ROOT, stdout=out_fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         creationflags=DETACH & ~subprocess.CREATE_BREAKAWAY_FROM_JOB, close_fds=True)
    out_fh.close()
    time.sleep(30)
    after = backfill_procs(marker)
    status = "launched" if len(after) == 1 else f"WARNING: {len(after)} processes after launch"
    return f"[BACKFILL] {note}{status} (PID {after}); was {n_done}/{n_all} done, partial {partial}"


# ---------------------------------------------------------------- GEX
def gap_check():
    r = run([PYTHONW, os.path.join(ROOT, "gex_gap_check.py")], timeout=300)
    line = next((l for l in r.stdout.splitlines() if l.startswith("{")), None)
    if r.returncode != 0 or line is None:
        raise RuntimeError(f"gex_gap_check.py failed (rc={r.returncode}): {(r.stderr or r.stdout)[-200:]}")
    return json.loads(line)


def task_info(name):
    ps = (f"$i=Get-ScheduledTaskInfo -TaskName '{name}'; $t=Get-ScheduledTask -TaskName '{name}'; "
          "'{0}|{1}|{2}' -f $i.LastRunTime.ToString('o'),$i.LastTaskResult,$t.State")
    r = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], timeout=60)
    last, result, state = r.stdout.strip().split("|")
    return last, result, state


def do_gex():
    try:
        before = gap_check()
    except Exception as exc:
        return f"[GEX CATCH-UP] error: {exc}"
    if not before["missing"]:
        return f"[GEX CATCH-UP] GEX current (scan {before['scan']}, {before['gex_metrics_rows']} rows, max {before['gex_metrics_max']})"
    if DRY:
        return f"[GEX CATCH-UP] DRY-RUN: would trigger {GEX_TASK}; missing {before['missing']}"
    try:
        prev_last, _, _ = task_info(GEX_TASK)
        r = run(["schtasks", "/run", "/tn", GEX_TASK], timeout=60)
        if r.returncode != 0:
            return f"[GEX CATCH-UP] error: schtasks /run failed: {(r.stderr or r.stdout).strip()[:150]}"
        deadline = time.time() + 600
        while True:
            time.sleep(15)
            last, result, state = task_info(GEX_TASK)
            if last != prev_last and state != "Running":
                break
            if time.time() > deadline:
                return f"[GEX CATCH-UP] error: task did not finish within 10 min (state={state}); missing {before['missing']}"
        after = gap_check()
    except Exception as exc:
        return f"[GEX CATCH-UP] error: {exc}"
    filled = [m for m in before["missing"] if m not in after["missing"]]
    rows = f"rows {before['gex_metrics_rows']}->{after['gex_metrics_rows']}, task result {result}"
    if not after["missing"]:
        return f"[GEX CATCH-UP] success: filled {len(filled)} {filled}; {rows}"
    if filled:
        return f"[GEX CATCH-UP] partial: filled {len(filled)} {filled}; still missing {after['missing']}; {rows}"
    return f"[GEX CATCH-UP] still missing {after['missing']}; {rows}"


# ---------------------------------------------------------------- main
def main():
    ts = utc_now()
    print(f"=== quota_probe_and_resume {ts} UTC{' (DRY RUN)' if DRY else ''} ===")
    if DRY:
        ok, status = True, "SUCCESS (dry-run, probe skipped)"
    else:
        r = run([PYTHONW, os.path.join(ROOT, "single_quota_test.py")], timeout=120)
        line = next((l for l in r.stdout.splitlines() if l.startswith("{")), "")
        print("probe:", line or r.stdout.strip() or r.stderr.strip())
        status = json.loads(line)["status"] if line else f"FAILED probe script error rc={r.returncode}"
        ok = status.startswith("SUCCESS")

    if not ok:
        code = "429 (blocked)" if "429" in status else "FAILED"
        append_probe_rows([row(ts, code, "none (durable probe task; backfill and GEX untouched)")])
        return

    rows = [row(ts, "200 (cleared)", do_backfill()), row(ts, "200 (cleared)", do_gex())]
    append_probe_rows(rows)


if __name__ == "__main__":
    main()

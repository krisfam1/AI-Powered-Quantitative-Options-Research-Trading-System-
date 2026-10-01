"""
Daily automated health check (CLAUDE.md Section 60, added 2026-10-01).

Scheduled as `EODHD_Daily_Health_Check` (daily 21:15 ET, after every nightly task) via
`pythonw.exe run_logged.py health_check.py health_check_log.txt`.

Checks, each OK / WARN / FAIL:
 (a) DATA   -- each tracked dataset is current for the latest closed NYSE session:
               gex_metrics (all 7 tickers), IV Stage 2 (0 rows until 2026-11-19, then growing),
               59-ticker backfill (advanced since the last check, unless quota-blocked all day).
 (b) TASKS  -- each scheduled task ran on schedule, returned 0, AND left evidence of real work
               in its own log/data (not just exit code 0): e.g. a GEX "RESULT" block, a backfill
               run with no all-error tickers, a probe row in quota_probe_log.db, no tracebacks.
 (c) BOTS   -- StockTradingBot / OptionsShadowLoop / SpyGammaLoop: service running, python
               child alive, heartbeat (uptime_log.db) within the latest session.

Alerts on any FAIL: email if HEALTH_SMTP_HOST/PORT/USER/PASSWORD/TO are set in .env
(e.g. a Gmail app password); otherwise writes HEALTH_ALERT.txt in the project root and
tries a Windows toast. The full report always goes to stdout (-> health_check_log.txt) and
health_check_status.json. CLAUDE.md is never read or written by this script.

`--no-alert` runs every check but sends nothing (testing).
"""
import json
import os
import re
import sqlite3
import smtplib
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from email.message import EmailMessage
from zoneinfo import ZoneInfo

import psutil
from dotenv import load_dotenv

ROOT = r"C:\Users\fmkri\Downloads\Python-Backend\Python-Backend"
os.chdir(ROOT)
load_dotenv(os.path.join(ROOT, ".env"))
ET = ZoneInfo("America/New_York")
NO_WINDOW = subprocess.CREATE_NO_WINDOW
STATE_FILE = os.path.join(ROOT, "health_check_state.json")
STATUS_FILE = os.path.join(ROOT, "health_check_status.json")
ALERT_FILE = os.path.join(ROOT, "HEALTH_ALERT.txt")
GEX_TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR", "SPY"]
IV_FIRST_ELIGIBLE_NIGHT = date(2026, 11, 19)   # CLAUDE.md Section 33
IV_STAGE2_START = date(2026, 9, 10)
BOTS = ["StockTradingBot", "OptionsShadowLoop", "SpyGammaLoop"]

results = []


def add(group, name, status, detail):
    results.append({"group": group, "check": name, "status": status, "detail": detail})


# ----------------------------------------------------------------- calendar
def nyse_sessions(start, end):
    """[(date, close_dt_et)] from Alpaca's market calendar; weekday fallback if unavailable."""
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetCalendarRequest
        tc = TradingClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"], paper=True)
        out = []
        for c in tc.get_calendar(GetCalendarRequest(start=start, end=end)):
            close = c.close if isinstance(c.close, datetime) else datetime.combine(c.date, c.close)
            out.append((c.date, close.replace(tzinfo=ET) if close.tzinfo is None else close.astimezone(ET)))
        return out
    except Exception as exc:
        add("meta", "nyse_calendar", "WARN", f"Alpaca calendar unavailable, using weekdays: {exc}")
        d, out = start, []
        while d <= end:
            if d.weekday() < 5:
                out.append((d, datetime.combine(d, time(16, 0), ET)))
            d += timedelta(days=1)
        return out


NOW_ET = datetime.now(ET)
SESSIONS = nyse_sessions(NOW_ET.date() - timedelta(days=400), NOW_ET.date())
CLOSED = [d for d, close in SESSIONS if close <= NOW_ET]
LAST_CLOSED = CLOSED[-1]
PREV_CLOSED = CLOSED[-2]
IN_SESSION = any(d == NOW_ET.date() and close > NOW_ET for d, close in SESSIONS) and NOW_ET.time() >= time(9, 30)


# ----------------------------------------------------------------- helpers
def task_info(names):
    ps = ("$o=@(); foreach($n in @(" + ",".join(f"'{n}'" for n in names) + ")){ $t=Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue; "
          "if($t){$i=Get-ScheduledTaskInfo -TaskName $n; $o+=[pscustomobject]@{Name=$n;State=[string]$t.State;"
          "LastRun=$i.LastRunTime.ToString('o');Result=$i.LastTaskResult;Missed=$i.NumberOfMissedRuns}} "
          "else {$o+=[pscustomobject]@{Name=$n;State='MISSING'}} }; $o | ConvertTo-Json")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, text=True, timeout=120, creationflags=NO_WINDOW)
    data = json.loads(r.stdout)
    return {d["Name"]: d for d in (data if isinstance(data, list) else [data])}


def parse_dt(s):
    return datetime.fromisoformat(s).astimezone(ET)


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def probe_results_since(since_utc):
    """(n_success, n_429, n_other) from single_quota_test.py's JSONL since a UTC time."""
    ok = blocked = other = 0
    for line in read(os.path.join(ROOT, "eodhd_quota_probe_log.jsonl")).splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if datetime.fromisoformat(rec["utc_time"]) < since_utc:
            continue
        if rec["status"].startswith("SUCCESS"):
            ok += 1
        elif "429" in rec["status"]:
            blocked += 1
        else:
            other += 1
    return ok, blocked, other


def check_backfill_log_block(block):
    """Detect a false-success run: per-ticker DONE lines where every fetch failed."""
    bad = []
    for m in re.finditer(r"^(\w+) DONE: saved=(\d+) excl_ts=\d+ excl_oi=\d+ excl_error=(\d+)", block, re.M):
        t, saved, err = m.group(1), int(m.group(2)), int(m.group(3))
        if err > 0 and saved == 0 and err >= 20:
            bad.append(f"{t}(saved=0, excl_error={err})")
    complete = "=== RUN COMPLETE" in block
    return bad, complete


def check_probe_log_since(text, since_utc):
    """Return run headers since `since_utc` that ended in a traceback."""
    crashes = []
    runs = re.split(r"(?m)^(?==== quota_probe_and_resume )", text)
    for run in runs:
        m = re.match(r"=== quota_probe_and_resume (\S+) UTC", run)
        if not m:
            continue
        ts = datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc)
        if ts >= since_utc and "Traceback (most recent call last)" in run:
            last = [l for l in run.strip().splitlines() if l.strip()][-1]
            crashes.append(f"{m.group(1)} -> {last.strip()[:120]}")
    return crashes


# ----------------------------------------------------------------- (a) data
def check_data(state):
    expect_gex = PREV_CLOSED   # GEX for session S is fetched the evening AFTER S (T-1 publishing)
    try:
        with sqlite3.connect("gex_data_cache.db") as g:
            mx = dict(g.execute("SELECT ticker, MAX(snapshot_date) FROM gex_metrics GROUP BY ticker").fetchall())
        stale = {t: mx.get(t) for t in GEX_TICKERS if (mx.get(t) or "") < expect_gex.isoformat()}
        add("data", "gex_metrics current", "FAIL" if stale else "OK",
            f"expected every ticker >= {expect_gex}; stale: {stale}" if stale else f"all 7 tickers >= {expect_gex}")
    except Exception as exc:
        add("data", "gex_metrics current", "FAIL", f"query failed: {exc}")

    try:
        with sqlite3.connect("iv_termstructure_stage2_dataset.db") as c:
            n, mx_obs = c.execute("SELECT COUNT(*), MAX(obs_date) FROM termstructure_stage2_examples").fetchone()
        if LAST_CLOSED < IV_FIRST_ELIGIBLE_NIGHT:
            add("data", "IV Stage 2 rows", "OK" if n == 0 else "FAIL",
                f"{n} rows (0 expected before the night of {IV_FIRST_ELIGIBLE_NIGHT})")
        else:
            stage2 = [d for d, _ in SESSIONS if d >= IV_STAGE2_START]
            k = stage2.index(LAST_CLOSED) - 50
            expected = stage2[max(k - 2, 0)]   # 2-session tolerance for quota / publishing lag
            ok = mx_obs is not None and mx_obs >= expected.isoformat()
            add("data", "IV Stage 2 rows", "OK" if ok else "FAIL",
                f"{n} rows, latest obs {mx_obs}; expected latest obs >= {expected}")
    except Exception as exc:
        add("data", "IV Stage 2 rows", "FAIL", f"query failed: {exc}")

    # 2026-10-01: the 59-ticker Target C backfill is RETIRED (task disabled, probe no longer relaunches it).
    add("data", "59-ticker backfill", "OK", "retired 2026-10-01 with Target C; dataset kept as is")
    if False:
        with sqlite3.connect("broader_universe_volatility_dataset.db") as c:
            s = dict(c.execute("SELECT ticker, COUNT(*) FROM volatility_training_examples GROUP BY ticker"))
            e = dict(c.execute("SELECT ticker, COUNT(*) FROM volatility_excluded GROUP BY ticker"))
        tot = {t: s.get(t, 0) + e.get(t, 0) for t in set(s) | set(e)}
        total = sum(tot.values())
        top = max(tot.values()) if tot else 0
        complete = sum(v >= 0.97 * top for v in tot.values()) if top else 0
        prev = state.get("backfill_total")
        since = datetime.fromisoformat(state["checked_at_utc"]) if "checked_at_utc" in state else datetime.now(timezone.utc) - timedelta(hours=24)
        ok_p, blocked_p, other_p = probe_results_since(since)
        detail = f"{complete}/59 tickers complete, {total} candidates (last check: {prev}); probes since last check: {ok_p} ok, {blocked_p} 429, {other_p} other"
        if complete >= 59:
            add("data", "59-ticker backfill", "OK", detail + " -- COMPLETE")
        elif prev is None or total > prev:
            add("data", "59-ticker backfill", "OK", detail)
        elif ok_p > 0:
            add("data", "59-ticker backfill", "FAIL", detail + " -- quota was open but the backfill did not advance")
        else:
            add("data", "59-ticker backfill", "WARN", detail + " -- no progress, quota blocked all period")
        state["backfill_total"] = total


# ----------------------------------------------------------------- (b) tasks
def run_block(text, header_re, since_et):
    """The log block of the latest run whose header timestamp is >= since_et (minus 3 min), or None.
    header_re must capture the run's start time (ISO datetime, or a plain ET date) in group 1."""
    best = None
    for m in re.finditer(header_re, text, re.M):
        raw = m.group(1)
        try:
            ts = datetime.fromisoformat(raw)
            ts = ts.astimezone(ET) if ts.tzinfo else ts.replace(tzinfo=ET)
        except ValueError:
            continue
        if len(raw) == 10:   # date-only header: same ET date as the run counts
            ok = ts.date() == since_et.date()
        else:
            ok = ts >= since_et - timedelta(minutes=3)
        if ok:
            best = m.start()
    if best is None:
        return None
    nxt = re.compile(header_re, re.M).search(text, best + 1)
    return text[best: nxt.start() if nxt else len(text)]


def run_blocks_since(text, header_re, since_et):
    """Every (start_time_et, block) whose ISO header timestamp is >= since_et."""
    ms = list(re.finditer(header_re, text, re.M))
    out = []
    for k, m in enumerate(ms):
        try:
            ts = datetime.fromisoformat(m.group(1))
        except ValueError:
            continue
        ts = ts.astimezone(ET) if ts.tzinfo else ts.replace(tzinfo=ET)
        if ts >= since_et:
            out.append((ts, text[m.start(): ms[k + 1].start() if k + 1 < len(ms) else len(text)]))
    return out


# name -> (log file, run-header regex capturing the start time, regex proving real work in that run's block)
DAILY_TASKS = {
    "GEX_Historical_Incremental_Update": ("gex_historical_update_log.txt",
        r"^INCREMENTAL HISTORICAL GEX UPDATE -- (\S+)", r"^RESULT$"),
    "GEX_Prospective_Daily_Collection": ("gex_collection_log.txt",
        r"^DAILY PROSPECTIVE COLLECTION RUN -- (\d{4}-\d\d-\d\d)", r"INTEGRITY CHECK: PASSED"),
    "IVTermStructure_Stage2_Nightly_Update": ("iv_termstructure_stage2_generation_log.txt",
        r"^=== RUN START (\S+) \|", r"=== RUN (COMPLETE|STOPPED EARLY \(QUOTA\))"),
    "PreventSleep_DuringCollectionWindow": (None, None, None),
}


def check_tasks(state):
    info = task_info(list(DAILY_TASKS) + ["EODHD_Quota_Probe_And_Resume"])
    for name, (log, header_re, work_re) in DAILY_TASKS.items():
        i = info.get(name, {"State": "MISSING"})
        if i["State"] in ("MISSING", "Disabled"):
            add("tasks", name, "FAIL", f"task state {i['State']}")
            continue
        last = parse_dt(i["LastRun"])
        if last.year < 2000:
            add("tasks", name, "WARN", "has never run yet (newly created task)")
            continue
        problems = []
        if NOW_ET - last > timedelta(hours=26):
            problems.append(f"last run {last:%Y-%m-%d %H:%M} ET is >26h ago")
        if i["Result"] != 0:
            problems.append(f"LastTaskResult={i['Result']}")
        if log:
            block = run_block(read(os.path.join(ROOT, log)), header_re, last)
            if block is None and name == "BroaderUniverse_Volatility_Nightly_Update":
                # A run that found the backfill already running exits at once with LOCK HELD (stdout log only).
                if read("broader_universe_volatility_update_stdout_log.txt").rstrip().endswith("Exiting without touching data."):
                    block = "LOCK HELD"
            if block is None:
                problems.append(f"no run in {log} starting at/after the task's last run ({last:%Y-%m-%d %H:%M} ET) -- ran but did no logged work")
            elif block != "LOCK HELD":
                if "Traceback (most recent call last)" in block:
                    problems.append(f"traceback in that run's output in {log}")
                if work_re and not re.search(work_re, block, re.M):
                    problems.append(f"that run never reached a completion marker /{work_re}/")
        if name == "BroaderUniverse_Volatility_Nightly_Update":
            # EVERY backfill run since the previous health check (manual ones and probe-launched ones
            # too), not just the latest: a failed run must not hide behind a later healthy one.
            since = datetime.fromisoformat(state["checked_at_utc"]).astimezone(ET) if "checked_at_utc" in state else NOW_ET - timedelta(hours=24)
            for ts, blk in run_blocks_since(read(os.path.join(ROOT, log)), header_re, since):
                bad, complete = check_backfill_log_block(blk)
                if bad:
                    problems.append(f"run started {ts:%Y-%m-%d %H:%M} ET had {len(bad)} all-error tickers (e.g. {bad[:3]})"
                                    + (" yet logged RUN COMPLETE" if complete else ""))
        add("tasks", name, "FAIL" if problems else "OK",
            "; ".join(problems) or f"ran {last:%Y-%m-%d %H:%M} ET, result 0, real work logged")

    # Quota probe: every 2h, must leave a row in quota_probe_log.db and no crash in its own log.
    p = info.get("EODHD_Quota_Probe_And_Resume", {"State": "MISSING"})
    if p["State"] in ("MISSING", "Disabled"):
        add("tasks", "EODHD_Quota_Probe_And_Resume", "FAIL", f"task state {p['State']}")
        return
    last = parse_dt(p["LastRun"])
    problems = []
    if NOW_ET - last > timedelta(hours=2, minutes=30):
        problems.append(f"last run {last:%H:%M} ET is >2.5h ago")
    if p["Result"] != 0:
        problems.append(f"LastTaskResult={p['Result']}")
    since = datetime.fromisoformat(state["checked_at_utc"]) if "checked_at_utc" in state else datetime.now(timezone.utc) - timedelta(hours=24)
    crashes = check_probe_log_since(read("quota_probe_and_resume_log.txt"), since)
    if crashes:
        problems.append(f"{len(crashes)} probe run(s) crashed since last check: {crashes}")
    try:
        with sqlite3.connect("quota_probe_log.db") as c:
            last_row = c.execute("SELECT MAX(utc_ts) FROM probe_log WHERE dry_run=0").fetchone()[0]
        if last_row is None or datetime.fromisoformat(last_row).replace(tzinfo=timezone.utc) < last.astimezone(timezone.utc) - timedelta(minutes=1):
            problems.append(f"no probe_log row for the last run (latest row {last_row})")
    except Exception as exc:
        problems.append(f"quota_probe_log.db unreadable: {exc}")
    add("tasks", "EODHD_Quota_Probe_And_Resume", "FAIL" if problems else "OK",
        "; ".join(problems) or f"ran {last:%H:%M} ET, result 0, row logged, no crashes")


# ----------------------------------------------------------------- (c) bots
def check_bots():
    close_of_last = dict(SESSIONS)[LAST_CLOSED]
    need_after = (NOW_ET - timedelta(minutes=30)) if IN_SESSION else (close_of_last - timedelta(minutes=30))
    with sqlite3.connect("uptime_log.db") as c:
        hb = dict(c.execute("SELECT service, MAX(timestamp) FROM heartbeats GROUP BY service").fetchall())
    for svc in BOTS:
        problems = []
        try:
            s = psutil.win_service_get(svc).as_dict()
            if s["status"] != "running":
                problems.append(f"service {s['status']}")
            elif s["pid"] and not any("python" in ch.name().lower() for ch in psutil.Process(s["pid"]).children()):
                problems.append("service running but no python child process")
        except Exception as exc:
            problems.append(f"service lookup failed: {exc}")
        last_hb = hb.get(svc)
        if last_hb is None or datetime.fromisoformat(last_hb).astimezone(ET) < need_after:
            problems.append(f"last heartbeat {last_hb} is before {need_after:%Y-%m-%d %H:%M} ET")
        add("bots", svc, "FAIL" if problems else "OK", "; ".join(problems) or f"running; last heartbeat {last_hb}")


EXEC_COST_FIRST_SESSION = date(2026, 10, 2)   # sampler loads with the OptionsShadowLoop restart at midnight 10/02


def check_execution_cost():
    """PRIMARY: EODHD end-of-day spreads keep up with the GEX chains. SECONDARY: the intraday sampler ran."""
    path = os.path.join(ROOT, "execution_cost_log.db")
    with sqlite3.connect(os.path.join(ROOT, "gex_data_cache.db")) as g:
        gex_max = g.execute("SELECT MAX(requested_date) FROM raw_records").fetchone()[0]
    eod_max = None
    if os.path.exists(path):
        with sqlite3.connect(path) as c:
            try:
                eod_max = c.execute("SELECT MAX(et_date) FROM eod_spreads WHERE panel='eodhd'").fetchone()[0]
            except sqlite3.OperationalError:
                pass
    ok = bool(eod_max) and eod_max >= gex_max
    add("data", "execution_cost_eod_spreads", "OK" if ok else "FAIL",
        f"eod_spreads through {eod_max}; GEX chains through {gex_max}"
        + ("" if ok else " (ExecutionCost_EOD_Spreads behind)"))

    if LAST_CLOSED < EXEC_COST_FIRST_SESSION:
        add("data", "execution_cost_sampler", "OK", f"not active yet (first session {EXEC_COST_FIRST_SESSION})")
        return
    d = LAST_CLOSED.isoformat()
    try:
        with sqlite3.connect(path) as c:
            nq, feeds = c.execute("SELECT COUNT(*), GROUP_CONCAT(DISTINCT feed) FROM quotes WHERE et_date=?", (d,)).fetchone()
            runs, errs = c.execute("SELECT COUNT(*), SUM(error IS NOT NULL) FROM sampler_runs WHERE substr(sample_ts,1,10) "
                                   "BETWEEN ? AND ?", (d, (LAST_CLOSED + timedelta(days=1)).isoformat())).fetchone()
    except sqlite3.OperationalError as exc:
        add("data", "execution_cost_sampler", "WARN", f"no sampler tables yet: {exc}")
        return
    errs = errs or 0
    detail = f"{nq} quotes on {d} (feed {feeds}); {runs} sampler runs, {errs} with errors"
    if nq == 0:   # secondary source since 2026-10-01 -> WARN, not FAIL
        add("data", "execution_cost_sampler", "WARN", detail)
    elif runs and errs / runs > 0.10 or runs < 200:
        add("data", "execution_cost_sampler", "WARN", detail + " (expected ~390 runs/session, <10% errors)")
    else:
        add("data", "execution_cost_sampler", "OK", detail)


# ----------------------------------------------------------------- alerting
def send_alert(subject, body):
    host, to = os.environ.get("HEALTH_SMTP_HOST"), os.environ.get("HEALTH_ALERT_TO")
    if host and to:
        try:
            msg = EmailMessage()
            msg["Subject"], msg["From"], msg["To"] = subject, os.environ.get("HEALTH_SMTP_USER", to), to
            msg.set_content(body)
            with smtplib.SMTP(host, int(os.environ.get("HEALTH_SMTP_PORT", "587")), timeout=30) as s:
                s.starttls()
                s.login(os.environ["HEALTH_SMTP_USER"], os.environ["HEALTH_SMTP_PASSWORD"])
                s.send_message(msg)
            return "email sent to " + to
        except Exception as exc:
            channel = f"EMAIL FAILED ({exc}); "
    else:
        channel = "email not configured (set HEALTH_SMTP_HOST/PORT/USER/PASSWORD and HEALTH_ALERT_TO in .env); "
    with open(ALERT_FILE, "w", encoding="utf-8") as f:
        f.write(subject + "\n\n" + body)
    toast = ("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
             "$x=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
             f"$t=$x.GetElementsByTagName('text'); $t.Item(0).AppendChild($x.CreateTextNode('Research health check: FAIL')) > $null;"
             f"$t.Item(1).AppendChild($x.CreateTextNode('See HEALTH_ALERT.txt in Python-Backend')) > $null;"
             "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Python-Backend health check').Show([Windows.UI.Notifications.ToastNotification]::new($x))")
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", toast], timeout=30,
                       capture_output=True, creationflags=NO_WINDOW)
    except Exception:
        pass
    return channel + "wrote HEALTH_ALERT.txt + toast"


def main():
    state = json.loads(read(STATE_FILE) or "{}")
    check_data(state)
    check_tasks(state)
    check_bots()
    check_execution_cost()
    fails = [r for r in results if r["status"] == "FAIL"]
    warns = [r for r in results if r["status"] == "WARN"]
    lines = [f"HEALTH CHECK {NOW_ET:%Y-%m-%d %H:%M %Z} | last closed session {LAST_CLOSED} | "
             f"{len(fails)} FAIL, {len(warns)} WARN, {len(results) - len(fails) - len(warns)} OK"]
    lines += [f"  [{r['status']:4}] {r['group']}/{r['check']}: {r['detail']}" for r in results]
    report = "\n".join(lines)
    print("=" * 100 + "\n" + report)
    alert = "none"
    if fails and "--no-alert" not in sys.argv:
        alert = send_alert(f"[Python-Backend] health check: {len(fails)} FAIL", report)
    elif not fails and os.path.exists(ALERT_FILE) and "--no-alert" not in sys.argv:
        os.remove(ALERT_FILE)
    print("alert:", alert)
    state["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
    if "--no-alert" not in sys.argv:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=1)
    with open(STATUS_FILE, "w") as f:
        json.dump({"checked_at": NOW_ET.isoformat(), "fails": len(fails), "warns": len(warns), "results": results, "alert": alert}, f, indent=1)


if __name__ == "__main__":
    main()

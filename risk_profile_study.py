"""
DESCRIPTIVE RISK STUDY (user-approved 2026-10-06): how bad do two-week (10-trading-day) stretches get for
Cboe index-level option-selling strategies (BXM, PUT, CNDR, BFLY), with the SPX price index as comparator.

NOT a hypothesis test: no trial, no pre-registration, no hash, no ledger row, no verdict, no significance
tests, no p-values, no Sharpe/"edge" claims. Any difference between market states is EXPLORATORY.

Read-only inputs: data_snapshots/vrp_timing_20261002/ (verified against manifest.json first).
Outputs: risk_profile_option_selling_indexes_2026-10-06.md and risk_profile_nonoverlapping_windows_2026-10-06.csv.
No network calls, no broker API, no .env, no database writes.

All definitions below were fixed before any number was computed (user brief B2):
- 10-day return = level[t+10] / level[t] - 1 on the series' OWN trading days (dates in its own file).
- (a) NON-OVERLAPPING blocks start at the range's first usable date, every 10 trading days; the last
  incomplete block is dropped. (b) OVERLAPPING windows start every trading day (strongly dependent).
- COMMON range 2007-01-03..2026-10-01: master calendar = SPX dates; a window [t, t+10] is DROPPED if any
  master date in it is missing from any of BXM, PUT, CNDR, BFLY.
- State S at window start t: SPX close / max(SPX close over the previous 252 SPX trading days incl. t) - 1
  <= -10%; S5 at -5%. Uses SPX data through t only (last SPX date <= t). Undefined for the first 251 SPX
  days (1975), which precede every series. VIX state at t from VIX CLOSE (last VIX date <= t):
  below 15 / 15 to 25 inclusive / above 25; unavailable before VIX history begins.
- Episode: maximal run of S-days (SPX trading days in state S), merging gaps of <= 14 calendar days.
- Episode table: worst peak-to-trough drawdown with peak and trough both inside [episode start, end], and the
  worst 10-day window STARTING inside the episode, both for (a) blocks and (b) overlapping windows, on each
  series' longest range (BXM from 2002-03-22, PUT from 2007-01-03, CNDR/BFLY and SPX from file start).
- Skewness and excess kurtosis: bias-corrected sample estimators (scipy bias=False).
- Percentiles: numpy linear interpolation.
- Max drawdown on daily levels: peak date, trough date, recovery = first date after the trough with level >=
  the peak level, else "not recovered"; days underwater = calendar days from peak to recovery (or to the last
  date if not recovered).
- 5 worst non-overlapping windows: for (a) the 5 lowest blocks; for (b) greedy: take the worst, remove every
  window whose start is within 9 trading days of it, repeat.
"""
import csv
import hashlib
import json
import os
from datetime import date, datetime

import numpy as np
from scipy.stats import kurtosis, skew

ROOT = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(ROOT, "data_snapshots", "vrp_timing_20261002")
OUT_MD = os.path.join(ROOT, "risk_profile_option_selling_indexes_2026-10-06.md")
OUT_CSV = os.path.join(ROOT, "risk_profile_nonoverlapping_windows_2026-10-06.csv")
H = 10
D2002, D2007, END = date(2002, 3, 22), date(2007, 1, 3), date(2026, 10, 1)
SERIES = ["BXM", "PUT", "CNDR", "BFLY"]
EXPECTED_MISSING = [date(2018, 12, 3), date(2019, 7, 5), date(2020, 10, 16)]
LBL_SPX = "SPX price only (excludes dividends)"

LOG = []


def log(s=""):
    LOG.append(s)


# ---------------------------------------------------------------- data loading and checks
def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def load(name, col):
    rows, bad = {}, []
    with open(os.path.join(DIR, f"{name}_History.csv"), newline="") as f:
        for r in csv.DictReader(f):
            try:
                d = datetime.strptime(r["DATE"].strip(), "%m/%d/%Y").date()
                v = float(r[col])
            except (ValueError, TypeError, KeyError):
                bad.append(r)
                continue
            if d in rows:
                bad.append(r)
            rows[d] = v
    return rows, bad


def checks():
    man = json.load(open(os.path.join(DIR, "manifest.json")))
    out = ["| File | Bytes (manifest / actual) | SHA-256 matches manifest | Data rows | First date | Last date | Unparseable or duplicate rows |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    data = {}
    for name, col in [("BXM", "BXM"), ("PUT", "PUT"), ("CNDR", "CNDR"), ("BFLY", "BFLY"), ("SPX", "SPX"), ("VIX", "CLOSE")]:
        fn = f"{name}_History.csv"
        p = os.path.join(DIR, fn)
        m = man["files"][fn]
        ok_sha = sha(p) == m["sha256"]
        size = os.path.getsize(p)
        rows, bad = load(name, col)
        data[name] = rows
        ds = sorted(rows)
        out.append(f"| {fn} | {m['bytes']:,} / {size:,} | {'yes' if ok_sha else '**NO**'} | {len(rows):,} | {ds[0]} | {ds[-1]} | {len(bad)} |")
    return man, data, "\n".join(out)


# ---------------------------------------------------------------- calculations
def windows(dates, lv, overlapping, keep=None):
    """[(start_date, end_date, return, start_index)]; keep(i) -> bool filters by start index (common-range drops)."""
    step = 1 if overlapping else H
    out = []
    for i in range(0, len(dates) - H, step):
        if keep is None or keep(i):
            out.append((dates[i], dates[i + H], lv[i + H] / lv[i] - 1, i))
    return out


def max_dd(dates, lv):
    peak_i, best = 0, (0.0, None, None)
    for i in range(len(lv)):
        if lv[i] > lv[peak_i]:
            peak_i = i
        dd = lv[i] / lv[peak_i] - 1
        if dd < best[0]:
            best = (dd, peak_i, i)
    dd, pi, ti = best
    if pi is None:
        return None
    rec = next((dates[j] for j in range(ti + 1, len(lv)) if lv[j] >= lv[pi]), None)
    end = rec or dates[-1]
    return dd, dates[pi], dates[ti], rec, (end - dates[pi]).days


def worst5(ws, overlapping):
    if not overlapping:
        return sorted(ws, key=lambda w: w[2])[:5]
    left, out = list(range(len(ws))), []
    while left and len(out) < 5:
        k = min(left, key=lambda j: ws[j][2])
        out.append(ws[k])
        left = [j for j in left if abs(ws[j][3] - ws[k][3]) >= H]   # trading-day distance between starts
    return out


def stats(ws, overlapping):
    r = np.array([w[2] for w in ws])
    if len(r) == 0:
        return None
    s = {"n": len(r), "mean": r.mean(), "sd": r.std(ddof=1) if len(r) > 1 else float("nan"),
         "skew": skew(r, bias=False) if len(r) > 2 else float("nan"),
         "kurt": kurtosis(r, fisher=True, bias=False) if len(r) > 3 else float("nan"),
         "min": min(ws, key=lambda w: w[2]), "worst5": worst5(ws, overlapping),
         "pct": np.percentile(r, [1, 5, 25, 50, 75, 95, 99]),
         "lt3": (r < -0.03).mean(), "lt5": (r < -0.05).mean(), "lt10": (r < -0.10).mean()}
    return s


def main():
    man, data, check_table = checks()
    spx_d = sorted(data["SPX"])
    spx_v = np.array([data["SPX"][d] for d in spx_d])
    vix_d = sorted(data["VIX"])

    # PUT stray rows before 2007
    put_pre = sorted(d for d in data["PUT"] if d < D2007)

    # gaps relative to SPX within each series' range
    gap_lines = []
    spx_set = set(spx_d)
    range_start = {"BXM": D2002, "PUT": D2007, "CNDR": min(data["CNDR"]), "BFLY": min(data["BFLY"])}
    for name in SERIES:
        ds = set(data[name])
        lo = range_start[name]
        miss = [d for d in spx_d if lo <= d <= END and d not in ds]
        extra = [d for d in sorted(ds) if lo <= d <= END and d not in spx_set]
        gap_lines.append((name, lo, miss, extra))

    # SPX drawdown state
    dd252 = {}
    for i, d in enumerate(spx_d):
        if i >= 251:
            dd252[d] = spx_v[i] / spx_v[i - 251:i + 1].max() - 1
    import bisect

    def asof(dlist, d):
        k = bisect.bisect_right(dlist, d) - 1
        return dlist[k] if k >= 0 else None

    def state(t):
        sd = asof(spx_d, t)
        x = dd252.get(sd)
        vd = asof(vix_d, t)
        v = data["VIX"][vd] if vd else None
        vb = None if v is None else ("VIX<15" if v < 15 else "VIX 15-25" if v <= 25 else "VIX>25")
        # bool(): numpy booleans fail the `is True` filters used by the splits (bug found in the first run)
        return (None if x is None else bool(x <= -0.10)), (None if x is None else bool(x <= -0.05)), vb

    # episodes
    sdays = [d for d in spx_d if d in dd252 and dd252[d] <= -0.10]
    eps = []
    for d in sdays:
        if eps and (d - eps[-1][-1]).days <= 14:
            eps[-1].append(d)
        else:
            eps.append([d])
    episodes = [(e[0], e[-1], len(e)) for e in eps]

    def ep_of(t):
        for k, (a, b, _) in enumerate(episodes):
            if a <= t <= b:
                return k + 1
        return ""

    # ranges: (label, series, start, calendar-mode)
    def own(name, start):
        ds = [d for d in sorted(data[name]) if start <= d <= END]
        return ds, np.array([data[name][d] for d in ds])

    ranges = [("BXM", "BXM", D2002), ("PUT", "PUT", D2007),
              ("CNDR", "CNDR", D2002), ("CNDR", "CNDR", min(data["CNDR"])),
              ("BFLY", "BFLY", D2002), ("BFLY", "BFLY", min(data["BFLY"])),
              ("SPX", "SPX", min(data["CNDR"])), ("SPX", "SPX", D2002)]

    results = []          # (series, range_label, mode, ws_a, ws_b, mdd)
    for lab, name, start in ranges:
        ds, lv = own(name, start)
        rl = f"{ds[0]} to {ds[-1]} (own calendar)"
        results.append((lab, rl, windows(ds, lv, False), windows(ds, lv, True), max_dd(ds, lv)))

    # common range
    master = [d for d in spx_d if D2007 <= d <= END]
    present = {n: set(data[n]) for n in SERIES}
    bad_master = [i for i, d in enumerate(master) if any(d not in present[n] for n in SERIES)]
    badset = set(bad_master)

    def keep(i):
        return not any(j in badset for j in range(i, i + H + 1))

    drop_a = sum(1 for i in range(0, len(master) - H, H) if not keep(i))
    drop_b = sum(1 for i in range(0, len(master) - H) if not keep(i))
    for name in SERIES + ["SPX"]:
        lv = np.array([data[name].get(d, np.nan) for d in master])
        ok = [i for i in range(len(master)) if not np.isnan(lv[i])]
        mdd = max_dd([master[i] for i in ok], lv[ok])
        results.append((name, f"COMMON {master[0]} to {master[-1]} (SPX calendar, windows touching a missing date dropped)",
                        windows(master, lv, False, keep), windows(master, lv, True, keep), mdd))

    # ---------------------------------------------------------------- CSV of non-overlapping windows
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "range", "window_start", "window_end", "return_10d", "S_dd_le_10pct", "S5_dd_le_5pct", "vix_bin", "S_episode"])
        for name, rl, wa, _, _ in results:
            for (a, b, r, _) in wa:
                s, s5, vb = state(a)
                w.writerow([name, rl, a, b, f"{r:.6f}", s, s5, vb, ep_of(a) if s else ""])

    # ---------------------------------------------------------------- markdown
    pf = lambda x: "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x * 100:.2f}%"
    nf = lambda x: "n/a" if x is None or np.isnan(x) else f"{x:.2f}"
    nm = lambda n: f"{n} ({LBL_SPX})" if n == "SPX" else n
    md = []
    A = md.append
    A("# Option-selling index risk profile: how bad do two-week stretches get? (2026-10-06)")
    A("")
    A("**DESCRIPTIVE RISK STUDY ONLY.** Not a hypothesis test: no trial, pre-registration, hash, ledger row or verdict, "
      "and it doesn't use the hypothesis slot. No significance tests or p-values. Nothing here says whether any strategy "
      "has an edge, and nothing predicts the future. **Every comparison between market states is EXPLORATORY.**")
    A("")
    A(f"Script `risk_profile_study.py`, SHA-256 `{sha(os.path.abspath(__file__)).upper()}`. Run once, then re-run once after a disclosed bug fix "
      "(the state splits were silently empty, and single-day episodes had blank window cells; see section 8). "
      f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} local time.")
    A("")
    A("Not modelled: trading costs, and the gap between a Cboe index and anything you could actually trade "
      "(index returns price every option leg at the bid/ask midpoint and roll on fixed rules).")
    A("")
    A("## 1. Data checks")
    A("")
    A("All files in `data_snapshots/vrp_timing_20261002/`, read-only.")
    A("")
    A(check_table)
    A("")
    A("**What `manifest.json` says about provenance:** for each file it records only the source URL (Cboe "
      "`cdn.cboe.com/api/global/us_indices/daily_prices/...` for the indexes and VIX), the byte count and the SHA-256, "
      f"plus the creation time ({man['created_utc']}) and the experiment it was built for (trial #13). "
      "**It says nothing about whether any series is a total-return index**, and it has no row counts, so rows were "
      "counted here.")
    A("")
    A(f"**PUT rows before 2007-01-03 excluded:** {len(put_pre)} ({', '.join(str(d) for d in put_pre)}).")
    A("")
    A("**Dates missing relative to SPX** (inside each series' range used here, through 2026-10-01):")
    A("")
    for name, lo, miss, extra in gap_lines:
        A(f"- {name} (from {lo}): {len(miss)} SPX dates missing: {', '.join(str(d) for d in miss) or 'none'}. "
          f"Dates present in {name} but not in SPX: {', '.join(str(d) for d in extra) or 'none'}.")
    A("")
    exp_ok = all(all(d in set(m) for d in EXPECTED_MISSING) for n, lo, m, _ in gap_lines if n in ("BXM", "CNDR", "BFLY"))
    A(f"Expected gaps 2018-12-03, 2019-07-05 and 2020-10-16 in BXM, CNDR and BFLY: **{'confirmed' if exp_ok else 'NOT as expected; see list'}**.")
    A("")
    A(f"**Common range** {master[0]} to {master[-1]}: {len(master)} SPX dates, {len(bad_master)} of them missing from at "
      f"least one of BXM/PUT/CNDR/BFLY ({', '.join(str(master[i]) for i in bad_master) or 'none'}). Windows touching those "
      f"dates were dropped: **{drop_a} non-overlapping blocks** and **{drop_b} overlapping windows**.")
    A("")
    A(f"**SPX is a price index** throughout: every SPX number below is \"{LBL_SPX}\". The option-selling indexes include "
      "their own cash flows. No adjustment was made, and equity exposure was not removed.")
    A("")

    A("## 2. Market-state episodes (SPX at least 10% below its 252-day high)")
    A("")
    A("S-days merged into episodes when gaps are 14 calendar days or less. Measured on SPX price only (excludes dividends).")
    A("")
    A("| # | Start | End | S-days |")
    A("| --- | --- | --- | --- |")
    for k, (a, b, n) in enumerate(episodes, 1):
        A(f"| {k} | {a} | {b} | {n} |")
    A("")

    def block(title, idx):
        A(f"## {title}")
        A("")
        A("| Series | Range | Windows | Mean | Std dev | Skew | Excess kurtosis | Worst (start date) | 1% | 5% | 25% | 50% | 75% | 95% | 99% | < −3% | < −5% | < −10% |")
        A("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for name, rl, wa, wb, _ in results:
            s = stats(wa if idx == 0 else wb, idx == 1)
            p = s["pct"]
            A(f"| {nm(name)} | {rl} | {s['n']:,} | {pf(s['mean'])} | {pf(s['sd'])} | {nf(s['skew'])} | {nf(s['kurt'])} | "
              f"{pf(s['min'][2])} ({s['min'][0]}) | " + " | ".join(pf(x) for x in p) +
              f" | {pf(s['lt3'])} | {pf(s['lt5'])} | {pf(s['lt10'])} |")
        A("")
        A("**5 worst non-overlapping windows** (start → end: return):")
        A("")
        for name, rl, wa, wb, _ in results:
            s = stats(wa if idx == 0 else wb, idx == 1)
            A(f"- {nm(name)}, {rl}: " + "; ".join(f"{a} → {b}: {pf(r)}" for a, b, r, _ in s["worst5"]))
        A("")

    block("3. Headline: non-overlapping 10-day blocks (a)", 0)
    block("4. Overlapping 10-day windows (b): strongly dependent, every start day", 1)

    A("## 5. Maximum drawdown on daily levels")
    A("")
    A("| Series | Range | Max drawdown | Peak | Trough | Recovered | Calendar days underwater |")
    A("| --- | --- | --- | --- | --- | --- | --- |")
    for name, rl, _, _, m in results:
        dd, pk, tr, rec, days = m
        A(f"| {nm(name)} | {rl} | {pf(dd)} | {pk} | {tr} | {rec or 'not recovered'} | {days:,}{'' if rec else ' (to ' + str(END) + ')'} |")
    A("")

    A("## 6. Splits by market state at window start (EXPLORATORY)")
    A("")
    A("**EXPLORATORY.** Descriptive splits only: no test of whether the differences are real. Windows in a state are "
      "few and cluster in a handful of episodes, so they are not independent.")
    A("")
    splits = [("S (SPX ≥10% below 252-day high)", lambda st: st[0] is True), ("not S", lambda st: st[0] is False),
              ("S5 (≥5% below)", lambda st: st[1] is True), ("not S5", lambda st: st[1] is False),
              ("VIX<15", lambda st: st[2] == "VIX<15"), ("VIX 15-25", lambda st: st[2] == "VIX 15-25"),
              ("VIX>25", lambda st: st[2] == "VIX>25"), ("VIX unavailable", lambda st: st[2] is None)]
    for idx, wl in ((0, "non-overlapping blocks (a)"), (1, "overlapping windows (b)")):
        A(f"### {wl}")
        A("")
        A("| Series | Range | State | Windows | Mean | Std dev | Skew | Excess kurtosis | Worst (start) | 1% | 5% | 50% | 95% | < −3% | < −5% | < −10% | 5 worst non-overlapping |")
        A("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for name, rl, wa, wb, _ in results:
            ws = wa if idx == 0 else wb
            st = {w[0]: state(w[0]) for w in ws}
            for sl, f in splits:
                sub = [w for w in ws if f(st[w[0]])]
                if not sub:
                    continue
                s = stats(sub, idx == 1)
                p = s["pct"]
                A(f"| {nm(name)} | {rl} | {sl} | {s['n']:,} | {pf(s['mean'])} | {pf(s['sd'])} | {nf(s['skew'])} | {nf(s['kurt'])} | "
                  f"{pf(s['min'][2])} ({s['min'][0]}) | {pf(p[0])} | {pf(p[1])} | {pf(p[3])} | {pf(p[5])} | {pf(s['lt3'])} | {pf(s['lt5'])} | {pf(s['lt10'])} | "
                  + "; ".join(f"{a}: {pf(r)}" for a, _, r, _ in s["worst5"]) + " |")
        A("")

    A("## 7. Per-episode table")
    A("")
    A("Each series on its longest range (BXM from 2002-03-22, PUT from 2007-01-03, CNDR/BFLY and SPX from file start). "
      "\"DD\" = worst peak-to-trough drawdown with both peak and trough inside the episode; \"Worst (a)\" = worst "
      "non-overlapping block starting in the episode; \"Worst (b)\" = worst overlapping window starting in it. "
      "Blank = series not available then. SPX = " + LBL_SPX + ".")
    A("")
    longest = {"BXM": D2002, "PUT": D2007, "CNDR": min(data["CNDR"]), "BFLY": min(data["BFLY"]), "SPX": spx_d[0]}
    cache = {}
    for name in SERIES + ["SPX"]:
        ds, lv = own(name, longest[name])
        cache[name] = (ds, lv, windows(ds, lv, False), windows(ds, lv, True))
    hdr = "| # | Start | End | " + " | ".join(f"{n} DD | {n} worst (a) | {n} worst (b)" for n in SERIES + ["SPX"]) + " |"
    A(hdr)
    A("| " + " | ".join(["---"] * (3 + 3 * 5)) + " |")
    for k, (a, b, n) in enumerate(episodes, 1):
        cells = []
        for name in SERIES + ["SPX"]:
            ds, lv, wa, wb = cache[name]
            ix = [i for i, d in enumerate(ds) if a <= d <= b]
            if not ix:
                cells += ["", "", ""]
                continue
            # bug fix after the first run: single-day episodes still get their worst-window cells
            if len(ix) < 2:
                ddc = "n/a (1 day)"
            else:
                sub = lv[ix[0]:ix[-1] + 1]
                ddc = pf((sub / np.maximum.accumulate(sub) - 1).min())
            sa = [r for (s0, _, r, _) in wa if a <= s0 <= b]
            sb = [r for (s0, _, r, _) in wb if a <= s0 <= b]
            cells += [ddc, pf(min(sa)) if sa else "", pf(min(sb)) if sb else ""]
        A(f"| {k} | {a} | {b} | " + " | ".join(cells) + " |")
    A("")
    A("## 8. What this shows (plain language)")
    A("")
    A("_Written by hand after the single run; see below._")
    A("")
    open(OUT_MD, "w", encoding="utf-8", newline="\n").write("\n".join(md))
    print("wrote", OUT_MD, "and", OUT_CSV)
    print("episodes:", len(episodes), "| common drops a/b:", drop_a, drop_b, "| PUT pre-2007 rows:", len(put_pre))


if __name__ == "__main__":
    main()

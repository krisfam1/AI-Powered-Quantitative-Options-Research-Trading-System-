"""
Dataset builder for trial #13, vix_termstructure_vrp_index_timing_v1_20261002
(hash 188828a66ad359c28692d923a8c7c57d8d91cdd507b1932f6427acb38e488d09; CLAUDE.md Section 63).

  python build_vrp_timing_dataset.py            # download a new snapshot, then verify it
  python build_vrp_timing_dataset.py --verify   # verify the existing snapshot only

Downloads every series the registered design uses into data_snapshots/vrp_timing_<YYYYMMDD>/ and
writes manifest.json with a SHA-256 per file. load_cycles() rebuilds the cycle table from a
snapshot after re-checking every hash, so the analysis can never silently use different bytes.

Cycle rule (registered parameters.cycle_definition): roll R = third Friday, or the preceding
business day if that Friday is an exchange holiday. Business days = dates in Cboe's SPX file. A
third Friday AFTER the last date in the file is never turned into a roll (the earlier
feasibility script did exactly that and miscounted 204 cycles). Signal date S_k = the trading day
before R_k; cycle k runs from the S_k close to the S_{k+1} close.

This script computes no signal-vs-return relationship.
"""
import csv
import hashlib
import io
import json
import math
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SNAP_DIR = ROOT / "data_snapshots"
UA = {"User-Agent": "Mozilla/5.0"}
CBOE = ["VIX", "VIX3M", "VIX6M", "SPX", "CNDR", "BFLY", "PUT", "BXM"]
CBOE_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{}_History.csv"
TSY_URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
           "daily-treasury-rates.csv/{y}/all?type=daily_treasury_bill_rates&field_tdr_date_value={y}&page&_format=csv")
TSY_YEARS = range(2007, 2027)

# Registered Stage 1 window (config.date_range / parameters.stage1_window)
STAGE1_FIRST_SIGNAL = date(2009, 10, 15)
STAGE1_LAST_END = date(2026, 9, 17)
EXPECTED_STAGE1_CYCLES = 203
VIX6M_FIRST_SIGNAL = date(2008, 1, 17)
EXPECTED_VIX6M_CYCLES = 224


def _fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()


def download():
    tag = datetime.now().strftime("%Y%m%d")
    d = SNAP_DIR / f"vrp_timing_{tag}"
    d.mkdir(parents=True, exist_ok=True)
    files = {}
    for s in CBOE:
        files[f"{s}_History.csv"] = (CBOE_URL.format(s), _fetch(CBOE_URL.format(s)))
    for y in TSY_YEARS:
        files[f"treasury_bill_rates_{y}.csv"] = (TSY_URL.format(y=y), _fetch(TSY_URL.format(y=y)))
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "experiment_id": "vix_termstructure_vrp_index_timing_v1_20261002",
                "config_hash": "188828a66ad359c28692d923a8c7c57d8d91cdd507b1932f6427acb38e488d09",
                "files": {}}
    for name, (url, data) in files.items():
        (d / name).write_bytes(data)
        manifest["files"][name] = {"url": url, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    (d / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"snapshot written: {d} ({len(files)} files)")
    return d


def latest_snapshot():
    snaps = sorted(SNAP_DIR.glob("vrp_timing_*"))
    if not snaps:
        raise SystemExit("no snapshot; run without --verify first")
    return snaps[-1]


def _verified_bytes(snap):
    m = json.loads((snap / "manifest.json").read_text(encoding="utf-8"))
    out = {}
    for name, meta in m["files"].items():
        b = (snap / name).read_bytes()
        if hashlib.sha256(b).hexdigest() != meta["sha256"]:
            raise SystemExit(f"SHA-256 MISMATCH for {name}: the snapshot was modified")
        out[name] = b
    return m, out


def _cboe_series(b):
    out = {}
    for r in csv.reader(io.StringIO(b.decode("utf-8-sig"))):
        try:
            out[datetime.strptime(r[0].strip(), "%m/%d/%Y").date()] = float(r[-1])  # last column = close
        except (ValueError, IndexError):
            continue
    return out


def _tsy_4wk(files):
    rates = {}
    for name, b in files.items():
        if not name.startswith("treasury_"):
            continue
        rows = list(csv.reader(io.StringIO(b.decode("utf-8-sig"))))
        col = rows[0].index("4 WEEKS COUPON EQUIVALENT")
        for r in rows[1:]:
            if len(r) > col and r[col].strip():
                rates[datetime.strptime(r[0], "%m/%d/%Y").date()] = float(r[col])
    return rates


def third_friday(y, m):
    d = date(y, m, 15)
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d


def roll_dates(cal):
    days, last = set(cal), cal[-1]
    y, m, out = cal[0].year, cal[0].month, []
    while date(y, m, 1) <= last:
        tf = third_friday(y, m)
        if tf <= last:                       # never infer a roll beyond the data
            r = tf
            while r not in days:
                r -= timedelta(days=1)
            out.append(r)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def load(snap=None):
    """Verified series dict + roll list + T-bill rates."""
    snap = snap or latest_snapshot()
    manifest, files = _verified_bytes(snap)
    S = {s: _cboe_series(files[f"{s}_History.csv"]) for s in CBOE}
    cal = sorted(S["SPX"])
    return snap, manifest, S, cal, roll_dates(cal), _tsy_4wk(files)


def load_cycles(slope_series="VIX3M", first_signal=STAGE1_FIRST_SIGNAL, last_end=STAGE1_LAST_END, snap=None):
    """One row per cycle with signal, controls and excess returns for every payoff."""
    snap, manifest, S, cal, rolls, tsy = load(snap)
    idx = {d: i for i, d in enumerate(cal)}
    tsy_dates = sorted(tsy)

    def rf_on(d):
        k = max(i for i in range(len(tsy_dates)) if tsy_dates[i] <= d) if tsy_dates[0] <= d else None
        if k is None or (d - tsy_dates[k]).days > 7:
            raise ValueError(f"no Treasury 4-week rate within 7 days before {d}")
        return tsy[tsy_dates[k]]

    def vrp_proxy(d):
        i = idx[d]
        closes = [S["SPX"][cal[j]] for j in range(i - 21, i + 1)]           # 22 closes -> 21 returns ending d
        rv = 252 * sum(math.log(b / a) ** 2 for a, b in zip(closes, closes[1:])) / 21
        return (S["VIX"][d] / 100) ** 2 - rv

    sig_dates = [cal[idx[r] - 1] for r in rolls]
    rows = []
    for k in range(len(sig_dates) - 1):
        s0, s1 = sig_dates[k], sig_dates[k + 1]
        if s0 < first_signal or s1 > last_end:
            continue
        rf_rate = rf_on(s0)
        rf = rf_rate / 100 * (s1 - s0).days / 365
        row = {"k": len(rows), "roll": rolls[k], "signal_date": s0, "end_date": s1, "next_roll": rolls[k + 1],
               "slope": math.log(S[slope_series][s0] / S["VIX"][s0]),
               "slope_next": math.log(S[slope_series][s1] / S["VIX"][s1]),
               "ln_vix": math.log(S["VIX"][s0]), "vrp_proxy": vrp_proxy(s0),
               "rf_rate_pct": rf_rate, "rf": rf}
        for p in ("CNDR", "BFLY", "PUT", "BXM"):
            raw = S[p][s1] / S[p][s0] - 1
            row[f"{p}_raw"], row[f"{p}_xs"] = raw, raw - rf
        if k >= 1:  # previous cycle's CNDR excess return (lagged own return), from data before s0
            p0 = sig_dates[k - 1]
            rf_prev = rf_on(p0) / 100 * (s0 - p0).days / 365
            row["CNDR_xs_lag"] = S["CNDR"][s0] / S["CNDR"][p0] - 1 - rf_prev
        rows.append(row)
    return snap, manifest, rows


def verify(snap=None):
    snap, manifest, S, cal, rolls, tsy = load(snap)
    print(f"snapshot {snap.name}: {len(manifest['files'])} files, SHA-256 all match manifest")
    for s in CBOE:
        ds = sorted(S[s])
        print(f"  {s:6} {ds[0]} .. {ds[-1]}  rows={len(ds)}")
    print(f"  Treasury 4-week rates: {min(tsy)} .. {max(tsy)}  rows={len(tsy)}")
    problems = []

    _, _, rows = load_cycles(snap=snap)
    n = len(rows)
    print(f"\nStage 1 cycles (ln VIX3M/VIX): {n}  first signal {rows[0]['signal_date']}, "
          f"last signal {rows[-1]['signal_date']}, last end {rows[-1]['end_date']}")
    if n != EXPECTED_STAGE1_CYCLES:
        problems.append(f"expected {EXPECTED_STAGE1_CYCLES} Stage 1 cycles, got {n}")
    if rows[0]["signal_date"] != STAGE1_FIRST_SIGNAL or rows[-1]["end_date"] != STAGE1_LAST_END:
        problems.append("Stage 1 window endpoints differ from the registered date_range")
    _, _, r6 = load_cycles("VIX6M", first_signal=VIX6M_FIRST_SIGNAL, snap=snap)
    print(f"VIX6M robustness cycles: {len(r6)} (expected {EXPECTED_VIX6M_CYCLES})")
    if len(r6) != EXPECTED_VIX6M_CYCLES:
        problems.append(f"expected {EXPECTED_VIX6M_CYCLES} VIX6M cycles, got {len(r6)}")
    # The registered config annotates these subsamples as "(153)" and "(134)". Those counts came from the
    # feasibility script's fake final roll (same bug as its 204) and are one too high. The subsamples are
    # DEFINED by date (S_k >= 2014-01-01 / 2015-08-03), which is unchanged; true counts are 152 / 133.
    for lbl, d0, exp in (("post-2014", date(2014, 1, 1), 152), ("post-launch", date(2015, 8, 3), 133)):
        m = sum(r["signal_date"] >= d0 for r in rows)
        print(f"{lbl} subsample: {m} (expected {exp})")
        if m != exp:
            problems.append(f"{lbl}: expected {exp}, got {m}")

    # timing / calendar checks
    in_window = [r for r in rows]
    shifted = [r["roll"] for r in in_window if r["roll"].weekday() != 4] + \
              ([in_window[-1]["next_roll"]] if in_window[-1]["next_roll"].weekday() != 4 else [])
    print("holiday-shifted rolls in window:", [str(d) for d in shifted])
    expected_shift = {date(2014, 4, 17), date(2019, 4, 18), date(2022, 4, 14), date(2025, 4, 17), date(2026, 6, 18)}
    if set(shifted) != expected_shift:
        problems.append(f"holiday rolls {sorted(shifted)} != expected {sorted(expected_shift)}")
    idx = {d: i for i, d in enumerate(cal)}
    for r in rows:
        if idx[r["roll"]] - idx[r["signal_date"]] != 1:
            problems.append(f"signal {r['signal_date']} is not the trading day before roll {r['roll']}")
        if idx[r["next_roll"]] - idx[r["end_date"]] != 1:
            problems.append(f"end {r['end_date']} is not the trading day before roll {r['next_roll']}")
        if not (r["roll"].day >= 14 and r["roll"].day <= 21):
            problems.append(f"roll {r['roll']} outside the 3rd-week window")
    for a, b in zip(rows, rows[1:]):
        if a["end_date"] != b["signal_date"]:
            problems.append(f"cycles not contiguous at {a['end_date']}")
    lens = [(r["end_date"] - r["signal_date"]).days for r in rows]
    print(f"cycle length: {min(lens)}..{max(lens)} calendar days; contiguous, each signal = day before its roll")
    if min(lens) < 27 or max(lens) > 36:
        problems.append(f"cycle length {min(lens)}..{max(lens)} outside 27..36 days")
    for r in rows + r6:
        for key, v in r.items():
            if isinstance(v, float) and not math.isfinite(v):
                problems.append(f"non-finite {key} on {r['signal_date']}")
    print(f"T-bill rate used: {min(r['rf_rate_pct'] for r in rows):.2f}% .. {max(r['rf_rate_pct'] for r in rows):.2f}%")
    print(f"last roll in data: {rolls[-1]} (no roll inferred beyond {cal[-1]})")
    if problems:
        print("\nVERIFICATION FAILED:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("\nVERIFICATION PASSED")


if __name__ == "__main__":
    if "--verify" not in sys.argv:
        download()
    verify()

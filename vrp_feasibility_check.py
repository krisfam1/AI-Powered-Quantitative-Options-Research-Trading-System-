"""Data-existence check ONLY for trial #13 (VIX term structure -> Cboe vol-selling index returns).
Counts usable monthly roll cycles and gaps. Never computes any return, slope value, or relationship."""
import csv, io, urllib.request
from datetime import date, datetime, timedelta

UA = {"User-Agent": "Mozilla/5.0"}
SERIES = ["VIX", "VIX3M", "VIX6M", "SPX", "BFLY", "CNDR", "PUT", "BXM"]


def get(sym):
    url = f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{sym}_History.csv"
    txt = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read().decode()
    rows = list(csv.reader(io.StringIO(txt)))
    out = {}
    for r in rows:
        try:
            d = datetime.strptime(r[0].strip(), "%m/%d/%Y").date()
        except (ValueError, IndexError):
            continue
        try:
            v = float(r[-1])
        except ValueError:
            continue
        out[d] = v
    return out


data = {s: get(s) for s in SERIES}
cal = sorted(data["SPX"])  # trading-day calendar (SPX trades every Cboe business day)


def third_friday(y, m):
    d = date(y, m, 15)
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d


def roll_dates(start, end):
    days = set(cal)
    y, m, out = start.year, start.month, []
    while date(y, m, 1) <= end:
        r = third_friday(y, m)
        while r not in days and r > date(y, m, 1):
            r -= timedelta(days=1)
        out.append(r)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def prev_day(d):
    i = cal.index(d)
    return cal[i - 1]


last_close = max(cal)
for s in SERIES:
    ds = sorted(data[s])
    post = [d for d in cal if d >= date(2008, 1, 1)]
    miss = [d for d in post if d not in data[s]]
    print(f"{s:6} {ds[0]} -> {ds[-1]}  rows={len(ds)}  missing SPX-calendar days since 2008: {len(miss)} {miss[:5]}")

rolls = roll_dates(date(2007, 12, 1), last_close)
for sig in ("VIX3M", "VIX6M"):
    first = min(data[sig])
    cyc = []
    for a, b in zip(rolls, rolls[1:]):
        s0, s1 = prev_day(a), prev_day(b)
        if s0 < first or s1 > last_close:
            continue
        ok_sig = s0 in data["VIX"] and s0 in data[sig]
        ok_ret = {k: (s0 in data[k] and s1 in data[k]) for k in ("BFLY", "CNDR", "PUT", "BXM")}
        cyc.append((s0, s1, ok_sig, ok_ret))
    n = len(cyc)
    print(f"\nsignal ln({sig}/VIX): cycles with both endpoints closed = {n} "
          f"(first signal date {cyc[0][0]}, last cycle end {cyc[-1][1]})")
    print("  signal available:", sum(c[2] for c in cyc))
    for k in ("BFLY", "CNDR", "PUT", "BXM"):
        print(f"  {k} return available & signal available: {sum(c[2] and c[3][k] for c in cyc)}")
    post2014 = [c for c in cyc if c[0] >= date(2014, 1, 1)]
    post_launch = [c for c in cyc if c[0] >= date(2015, 8, 3)]
    print(f"  cycles starting 2014-01-01+ (after Johnson's 1996-2013 sample): {len(post2014)};"
          f" starting 2015-08-03+ (after BFLY/CNDR launch): {len(post_launch)}")
print("\nholiday-shifted rolls:", [r for r in rolls if r.weekday() != 4])

from dotenv import load_dotenv
load_dotenv()

"""
Rebalance calendar for the cross-sectional straddle hypothesis (CLAUDE.md Section 62).

Goyal-Saretto convention: each cycle opens on the first trading day after a standard monthly
expiration (the third Friday, or the prior trading day if that Friday is a market holiday) and
holds the straddle to the NEXT monthly expiration (~4-5 weeks). Two snapshot dates per cycle:
  entry  -- first trading day after expiration X_k
  exit   -- last trading day before expiration X_{k+1} (the "close the day before" variant)

Windows (fixed 2026-10-01, before any snapshot data existed):
  DEV   : cycles whose target expiration is <= 2025-09-30 (exploration allowed)
  BLIND : cycles whose target expiration is  > 2025-09-30 (pipeline go/no-go gate only; untouched)
"""
import os
from datetime import date, datetime, timedelta
from functools import lru_cache

DATA_START = date(2023, 10, 2)        # EODHD options depth cliff (Section 60)
DEV_END_EXPIRY = date(2025, 9, 30)


@lru_cache(maxsize=1)
def trading_days(start=date(2023, 1, 1), end=None):
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetCalendarRequest
    end = end or date.today() + timedelta(days=400)
    tc = TradingClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"], paper=True)
    return tuple(c.date for c in tc.get_calendar(GetCalendarRequest(start=start, end=end)))


def monthly_expiration(year, month):
    d = date(year, month, 1)
    fridays = [d + timedelta(days=i) for i in range(31)
               if (d + timedelta(days=i)).month == month and (d + timedelta(days=i)).weekday() == 4]
    third = fridays[2]
    days = set(trading_days())
    while third not in days:          # holiday (e.g. Good Friday) -> prior trading day
        third -= timedelta(days=1)
    return third


def cycles(last_entry=None):
    """[{'entry','exit','expiry','prev_expiry','window'}] for all cycles with data available."""
    days = trading_days()
    exps, y, m = [], 2023, 10
    while date(y, m, 1) <= (last_entry or date.today()) + timedelta(days=40):
        exps.append(monthly_expiration(y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    out = []
    for prev, nxt in zip(exps, exps[1:]):
        entry = next(d for d in days if d > prev)
        exit_ = max(d for d in days if d < nxt)
        if entry < DATA_START or (last_entry and entry > last_entry):
            continue
        out.append({"entry": entry, "exit": exit_, "expiry": nxt, "prev_expiry": prev,
                    "window": "dev" if nxt <= DEV_END_EXPIRY else "blind"})
    return out


if __name__ == "__main__":
    cs = cycles(last_entry=date.today())
    for c in cs:
        print(c["window"], c["entry"], "->", c["exit"], "| expiry", c["expiry"])
    print(f"dev cycles: {sum(c['window'] == 'dev' for c in cs)}, blind cycles: {sum(c['window'] == 'blind' for c in cs)}")

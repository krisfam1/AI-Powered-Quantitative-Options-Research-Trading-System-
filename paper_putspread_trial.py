"""
Paper put-spread trial (user-approved 2026-10-06). PAPER-ONLY forward trial on the Alpaca PAPER account.

This is an operations and risk track record, NOT a hypothesis test: no hypothesis slot, no ledger row, no
hash, no verdict, no claim of an edge. Rules are fixed as of 2026-10-06 (RULES_VERSION) and documented in
paper_putspread_trial/README.md. Do not change them after seeing any result.

PHASE 1 = build and DRY-RUN only. This file contains NO order-submission code. build_entry_order_request()
constructs an Alpaca multi-leg order object so the shape can be checked, and nothing ever sends it.

  python paper_putspread_trial.py --dry-run                                   # today, live paper quotes
  python paper_putspread_trial.py --dry-run --source stored --date 2026-09-08 --equity 93392.13
  python paper_putspread_trial.py --exit-selftest                             # hand-made position

Live mode makes read-only calls only (account, calendar, option chain snapshot). Stored mode reads the SPY
chains the GEX task already keeps in gex_data_cache.db, opened read-only (EODHD end-of-day quotes).
Credentials come from .env via python-dotenv, like every other module here, and are never printed.
"""
import argparse
import json
import math
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(HERE, "paper_putspread_trial")
GEX_DB = os.path.join(HERE, "gex_data_cache.db")
SPX_SESSIONS_CSV = os.path.join(HERE, "data_snapshots", "vrp_timing_20261002", "SPX_History.csv")

# ---- Fixed rules (2026-10-06). Do not edit after seeing results. ----
RULES_VERSION = "2026-10-06"
UNDERLYING = "SPY"
WIDTH = 5.0                       # long strike = short strike - $5
TARGET_DELTA, DELTA_MIN, DELTA_MAX = 0.15, 0.10, 0.20
DTE_MIN, DTE_MAX = 10, 14         # calendar days from entry to expiry
ENTRY_CLOCK = time(10, 30)        # Monday 10:30 ET (next trading day if a holiday)
MAX_WIDTH_FRAC = 0.15             # full spread bid/ask width must be <= 15% of mid credit
RISK_FRAC = 0.01                  # contracts = floor(1% equity / max loss per contract), minimum 1
MAX_ONE_CONTRACT_FRAC = 0.015     # skip if 1 contract's max loss > 1.5% equity
MAX_TOTAL_RISK_FRAC = 0.02        # total open max loss <= 2% equity
TAKE_PROFIT_FRAC = 0.50           # close when cost to close <= 50% of credit
STOP_MULT = 2.0                   # close when cost to close >= 2.0 x credit
TIME_EXIT_SESSIONS_BEFORE = 2     # close at 15:45 ET two trading days before expiry
TIME_EXIT_CLOCK = time(15, 45)
PAUSE_DRAWDOWN = 0.05             # no new spreads when equity <= 95% of the running peak
FILL_K = {"conservative": 0.5, "stress": 1.0}   # fraction of the full spread width worse than mid
HEADLINE_FILL = "conservative"


class PaperOnlyError(SystemExit):
    pass


# ---------------------------------------------------------------- paper-only assertion
def assert_paper_client(client):
    """Abort unless the Alpaca TradingClient points at the PAPER endpoint."""
    url = getattr(client, "_base_url", None)
    val = str(getattr(url, "value", url) or "")
    if "paper-api.alpaca.markets" not in val:
        raise PaperOnlyError("ABORT: Alpaca client is not on the PAPER endpoint (got %r). This trial is paper-only."
                             % (val or None))


def assert_paper_account(account):
    """Second check on the account itself: Alpaca paper account numbers start with 'PA'."""
    num = str(getattr(account, "account_number", "") or "")
    if not num.startswith("PA"):
        raise PaperOnlyError("ABORT: account is not an Alpaca PAPER account (number does not start with 'PA').")


# ---------------------------------------------------------------- quotes
@dataclass
class Leg:
    symbol: str
    strike: float
    delta: float | None
    bid: float | None
    ask: float | None
    quote_ts: str | None = None

    @property
    def two_sided(self):
        return self.bid is not None and self.ask is not None and self.bid > 0 and self.ask >= self.bid

    @property
    def mid(self):
        return (self.bid + self.ask) / 2 if self.two_sided else None

    def as_log(self):
        return {"symbol": self.symbol, "strike": self.strike, "delta": self.delta, "bid": self.bid,
                "ask": self.ask, "mid": None if self.mid is None else round(self.mid, 4), "quote_ts": self.quote_ts}


def spread_open_quote(short, long):
    """Quote for SELLING the spread: bid = short.bid - long.ask, ask = short.ask - long.bid."""
    bid, ask = short.bid - long.ask, short.ask - long.bid
    return {"bid": round(bid, 4), "ask": round(ask, 4), "mid": round((bid + ask) / 2, 4), "width": round(ask - bid, 4)}


def spread_close_quote(short, long):
    """Quote for BUYING BACK the spread. natural = short.ask - long.bid (the price you can close at now)."""
    q = spread_open_quote(short, long)
    return {"natural": q["ask"], "mid": q["mid"], "width": q["width"], "bid": q["bid"]}


# ---------------------------------------------------------------- calendar
def week_monday(d):
    return d - timedelta(days=d.weekday())


def entry_session(d, sessions):
    """The week's entry session: Monday, or the next trading day of that week if Monday is a holiday."""
    mon = week_monday(d)
    for i in range(5):
        day = mon + timedelta(days=i)
        if day in sessions:
            return day
    return None


def time_exit_session(expiry, sessions):
    """The trading session two sessions before expiry (sessions = sorted list of trading dates)."""
    s = sorted(sessions)
    if expiry not in s:
        raise ValueError(f"expiry {expiry} is not a trading session in the calendar")
    i = s.index(expiry)
    if i < TIME_EXIT_SESSIONS_BEFORE:
        raise ValueError("calendar does not reach back far enough before expiry")
    return s[i - TIME_EXIT_SESSIONS_BEFORE]


def time_exit_clock(close_time):
    """15:45 ET, or 15 minutes before an early close."""
    if close_time is None or close_time >= time(16, 0):
        return TIME_EXIT_CLOCK
    c = datetime.combine(date(2000, 1, 3), close_time) - timedelta(minutes=15)
    return c.time()


def exit_check_times(close_time=time(16, 0)):
    """Hourly on the hour during market hours, plus the time-exit clock (15:45, or close - 15 min)."""
    out = [time(h, 0) for h in range(10, 16) if time(h, 0) < close_time]
    tx = time_exit_clock(close_time)
    return sorted(set(out + [tx]))


# ---------------------------------------------------------------- entry rules
def choose_expiry(entry, expirations):
    ok = sorted(e for e in expirations if DTE_MIN <= (e - entry).days <= DTE_MAX)
    return ok[0] if ok else None


def select_short_put(puts):
    """Strike whose |delta| is closest to 0.15. Ties go to the LOWER strike. Returns (leg or None, skip reason)."""
    with_delta = [p for p in puts if p.delta is not None]
    if not with_delta:
        return None, "greeks missing for every put at this expiry"
    best = min(with_delta, key=lambda p: (abs(abs(p.delta) - TARGET_DELTA), p.strike))
    if not (DELTA_MIN <= abs(best.delta) <= DELTA_MAX):
        return None, f"no strike with |delta| in [{DELTA_MIN}, {DELTA_MAX}] (closest {abs(best.delta):.3f})"
    return best, None


def size_position(equity, credit, open_max_loss=0.0):
    """Returns (contracts, max_loss_per_contract, skip reason or None)."""
    if credit is None or credit <= 0:
        return 0, None, "mid credit is not positive"
    if credit >= WIDTH:
        return 0, None, "mid credit >= spread width (bad quote)"
    mlpc = (WIDTH - credit) * 100.0
    if mlpc > MAX_ONE_CONTRACT_FRAC * equity:
        return 0, mlpc, f"1 contract max loss ${mlpc:,.2f} > 1.5% of equity (${MAX_ONE_CONTRACT_FRAC * equity:,.2f})"
    n = max(math.floor(RISK_FRAC * equity / mlpc), 1)
    room = MAX_TOTAL_RISK_FRAC * equity - open_max_loss
    fit = math.floor(room / mlpc + 1e-9) if room > 0 else 0
    if fit < 1:
        return 0, mlpc, (f"total open max loss cap: ${open_max_loss:,.2f} open + ${mlpc:,.2f} > 2% of equity "
                         f"(${MAX_TOTAL_RISK_FRAC * equity:,.2f})")
    return min(n, fit), mlpc, None


def pause_active(equity, peak):
    return peak is not None and peak > 0 and equity <= (1 - PAUSE_DRAWDOWN) * peak


def evaluate_entry(entry, equity, peak, open_max_loss, puts_by_expiry, already_entered_this_week=False):
    """Apply every entry rule. Returns a decision dict with action 'open' or 'skip' and all logged fields."""
    d = {"rules_version": RULES_VERSION, "entry_date": entry.isoformat(), "equity": round(equity, 2),
         "equity_peak": None if peak is None else round(peak, 2), "open_max_loss": round(open_max_loss, 2)}

    def skip(reason, **kw):
        d.update(kw, action="skip", skip_reason=reason)
        return d

    if pause_active(equity, peak):
        return skip(f"PAUSE RULE: equity ${equity:,.2f} is >= 5% below peak ${peak:,.2f}; report to user")
    if already_entered_this_week:
        return skip("a spread was already opened this week")
    expiry = choose_expiry(entry, puts_by_expiry.keys())
    d["expirations_seen"] = sorted(e.isoformat() for e in puts_by_expiry)
    if expiry is None:
        return skip(f"no listed expiration {DTE_MIN}-{DTE_MAX} calendar days after entry")
    d["expiry"], d["dte_calendar"] = expiry.isoformat(), (expiry - entry).days
    puts = puts_by_expiry[expiry]
    short, why = select_short_put(puts)
    if short is None:
        return skip(why)
    d["short"] = short.as_log()
    long = next((p for p in puts if abs(p.strike - (short.strike - WIDTH)) < 1e-6), None)
    if long is None:
        return skip(f"long strike {short.strike - WIDTH:g} not listed")
    d["long"] = long.as_log()
    for name, leg in (("short", short), ("long", long)):
        if leg.bid is None or leg.bid <= 0:
            return skip(f"{name} leg has no bid > 0")
        if leg.ask is None or leg.ask < leg.bid:
            return skip(f"{name} leg quote not valid (ask missing or below bid)")
    q = spread_open_quote(short, long)
    d["spread_quote"] = q
    if q["mid"] <= 0:
        return skip("mid credit is not positive")
    d["width_pct_of_mid"] = round(100 * q["width"] / q["mid"], 2)
    if round(q["width"], 4) > round(MAX_WIDTH_FRAC * q["mid"], 4):
        return skip(f"spread width {q['width']:.2f} > 15% of mid credit {q['mid']:.2f} ({d['width_pct_of_mid']}%)")
    n, mlpc, why = size_position(equity, q["mid"], open_max_loss)
    d["max_loss_per_contract"] = None if mlpc is None else round(mlpc, 2)
    if why:
        return skip(why)
    d.update(action="open", intended_credit=q["mid"], contracts=n, max_loss=round(n * mlpc, 2),
             collateral=round(n * mlpc, 2), max_loss_pct_equity=round(100 * n * mlpc / equity, 3),
             credit_received_mid_dollars=round(n * q["mid"] * 100, 2),
             fill_assumption_credits={k: round(fill_credit(q["mid"], q["width"], k), 4) for k in FILL_K})
    return d


# ---------------------------------------------------------------- exit rules
def check_exit(pos, now_et, short, long, sessions):
    """pos: dict with expiry (date), credit (per-share credit received). sessions: {date: close time}.
    Returns dict(action 'close'|'hold', reason, triggered list, quote fields). Priority: stop, take_profit, time_exit."""
    out = {"checked_at": now_et.isoformat(), "credit": pos["credit"], "triggered": []}
    if short is not None and long is not None and short.two_sided and long.two_sided:
        q = spread_close_quote(short, long)
        out.update(close_natural=q["natural"], close_mid=q["mid"], close_width=q["width"],
                   short=short.as_log(), long=long.as_log())
        if q["natural"] >= round(STOP_MULT * pos["credit"], 4):
            out["triggered"].append("stop")
        if q["natural"] <= round(TAKE_PROFIT_FRAC * pos["credit"], 4):
            out["triggered"].append("take_profit")
    else:
        out["quote_problem"] = "no valid two-sided quote on both legs; profit/stop not evaluable this check"
    tx_day = time_exit_session(pos["expiry"], sorted(sessions))
    tx_clock = time_exit_clock(sessions.get(tx_day))
    out["time_exit_at"] = f"{tx_day.isoformat()} {tx_clock.strftime('%H:%M')} ET"
    if now_et.date() > tx_day or (now_et.date() == tx_day and now_et.time() >= tx_clock):
        out["triggered"].append("time_exit")
    out["action"] = "close" if out["triggered"] else "hold"
    out["reason"] = out["triggered"][0] if out["triggered"] else None
    return out


# ---------------------------------------------------------------- fills, P&L, benchmarks
def fill_credit(mid, width, assumption):
    return mid - FILL_K[assumption] * width


def fill_debit(mid, width, assumption):
    return mid + FILL_K[assumption] * width


def pnl_three(contracts, entry_mid, entry_width, exit_mid, exit_width, paper_credit=None, paper_debit=None):
    """P&L in dollars under the three fill assumptions. 'paper_actual' needs real paper fills (Phase 2)."""
    out = {}
    for k in FILL_K:
        out[k] = round((fill_credit(entry_mid, entry_width, k) - fill_debit(exit_mid, exit_width, k)) * 100 * contracts, 2)
    out["paper_actual"] = (None if paper_credit is None or paper_debit is None
                           else round((paper_credit - paper_debit) * 100 * contracts, 2))
    out["headline"] = out[HEADLINE_FILL]
    return out


def tbill_benchmark(collateral, annual_rate, start, end):
    """Simple interest on the collateral (max loss) at the T-bill rate, actual/365."""
    return round(collateral * annual_rate * (end - start).days / 365.0, 2)


def spy_buy_hold_return(spy_start, spy_end):
    return spy_end / spy_start - 1.0


# ---------------------------------------------------------------- order shape (never submitted)
def build_entry_order_request(decision):
    """Construct (do NOT submit) the Alpaca multi-leg limit order for a decision. Phase 1 only prints it.
    The limit_price sign convention for an mleg CREDIT order is UNVERIFIED and must be confirmed before Phase 2."""
    from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest
    from alpaca.trading.enums import OrderClass, OrderSide, PositionIntent, TimeInForce
    return LimitOrderRequest(
        qty=decision["contracts"], order_class=OrderClass.MLEG, time_in_force=TimeInForce.DAY,
        limit_price=round(decision["intended_credit"], 2),
        legs=[OptionLegRequest(symbol=decision["short"]["symbol"], ratio_qty=1, side=OrderSide.SELL,
                               position_intent=PositionIntent.SELL_TO_OPEN),
              OptionLegRequest(symbol=decision["long"]["symbol"], ratio_qty=1, side=OrderSide.BUY,
                               position_intent=PositionIntent.BUY_TO_OPEN)])


# ---------------------------------------------------------------- data loading
def parse_occ(symbol):
    tail = symbol[-15:]
    return (date(2000 + int(tail[0:2]), int(tail[2:4]), int(tail[4:6])),
            "put" if tail[6] == "P" else "call", int(tail[7:]) / 1000.0)


def load_live(today):
    """Read-only: paper account, trading calendar, SPY put chain snapshot (Alpaca indicative feed)."""
    from dotenv import load_dotenv
    load_dotenv(os.path.join(HERE, ".env"))
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetCalendarRequest
    from alpaca.trading.enums import ContractType
    from alpaca.data.historical.option import OptionHistoricalDataClient
    from alpaca.data.requests import OptionChainRequest
    from alpaca.data.enums import OptionsFeed
    key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
    tc = TradingClient(key, secret, paper=True)
    assert_paper_client(tc)
    acct = tc.get_account()
    assert_paper_account(acct)
    cal = tc.get_calendar(GetCalendarRequest(start=today - timedelta(days=10), end=today + timedelta(days=40)))
    sessions = {c.date: c.close.time() if isinstance(c.close, datetime) else c.close for c in cal}
    oc = OptionHistoricalDataClient(key, secret)
    chain = oc.get_option_chain(OptionChainRequest(
        underlying_symbol=UNDERLYING, feed=OptionsFeed.INDICATIVE, type=ContractType.PUT,
        expiration_date_gte=today + timedelta(days=DTE_MIN), expiration_date_lte=today + timedelta(days=DTE_MAX)))
    puts = {}
    for sym, snap in chain.items():
        exp, typ, strike = parse_occ(sym)
        if typ != "put":
            continue
        q, g = snap.latest_quote, snap.greeks
        puts.setdefault(exp, []).append(Leg(sym, strike, getattr(g, "delta", None) if g else None,
                                            None if q is None else q.bid_price, None if q is None else q.ask_price,
                                            None if q is None or q.timestamp is None else
                                            q.timestamp.astimezone(ET).isoformat(timespec="seconds")))
    info = {"source": "alpaca paper, INDICATIVE options feed (OPRA not signed)",
            "equity": float(acct.equity), "options_approved_level": acct.options_approved_level,
            "options_trading_level": acct.options_trading_level}
    return info, sessions, puts


def load_stored(d):
    """Read-only: SPY puts from gex_data_cache.db raw_records whose id-date == d (EODHD end-of-day quotes)."""
    # Session calendar: SPX daily closes (NYSE sessions, through 2026-10-01). The chain's own id-dates are not
    # a calendar: it holds records stamped 2026-09-07 (Labor Day).
    with open(SPX_SESSIONS_CSV, encoding="utf-8") as f:
        next(f)
        days = {datetime.strptime(line.split(",")[0], "%m/%d/%Y").date() for line in f if line.strip()}
    if d not in days:
        raise SystemExit(f"{d} is not an NYSE session in {os.path.basename(SPX_SESSIONS_CSV)}")
    con = sqlite3.connect(f"file:{GEX_DB}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT contract, raw_json FROM raw_records WHERE ticker=? AND option_type='put' "
                           "AND id_suffix_date=? ORDER BY fetched_at", (UNDERLYING, d.isoformat())).fetchall()
    finally:
        con.close()
    by_contract = {}
    for contract, raw in rows:
        by_contract[contract] = json.loads(raw)
    puts = {}
    for contract, r in by_contract.items():
        exp = date.fromisoformat(r["exp_date"])
        if not (DTE_MIN <= (exp - d).days <= DTE_MAX):
            continue
        puts.setdefault(exp, []).append(Leg(contract, float(r["strike"]), r.get("delta"), r.get("bid"), r.get("ask"),
                                            f"{d.isoformat()} EOD"))
    info = {"source": "stored EODHD end-of-day chain (gex_data_cache.db, read-only); NOT a 10:30 ET quote"}
    return info, {s: time(16, 0) for s in days}, puts


# ---------------------------------------------------------------- CLI
def print_decision(dec):
    print(json.dumps(dec, indent=2, default=str))
    if dec["action"] == "open":
        s, l = dec["short"], dec["long"]
        print(f"\nWOULD OPEN (dry run, no order): {dec['contracts']} x SPY {dec['expiry']} "
              f"{s['strike']:g}/{l['strike']:g} put spread; short delta {s['delta']}; mid credit "
              f"${dec['intended_credit']:.2f}; max loss ${dec['max_loss']:,.2f} "
              f"({dec['max_loss_pct_equity']}% of equity); collateral ${dec['collateral']:,.2f}")
        req = build_entry_order_request(dec)
        print("Order object that Phase 2 would send (NOT sent):", req.to_request_fields())
    else:
        print(f"\nWOULD SKIP: {dec['skip_reason']}")


def run_dry(args):
    if args.source == "live":
        now = datetime.now(ET)
        today = now.date()
        info, sessions, puts = load_live(today)
        equity = info["equity"]
    else:
        today = date.fromisoformat(args.date)
        now = datetime.combine(today, ENTRY_CLOCK, ET)
        info, sessions, puts = load_stored(today)
        equity = args.equity
    print(f"=== paper_putspread_trial DRY RUN (rules {RULES_VERSION}); no orders are placed ===")
    print(json.dumps({k: v for k, v in info.items()}, default=str))
    sess = entry_session(today, sessions)
    print(f"date {today} | this week's entry session: {sess} at {ENTRY_CLOCK.strftime('%H:%M')} ET")
    if today != sess:
        print("Not an entry session: no new spread would be opened today. "
              "WHAT-IF below: the entry rules applied to the latest quotes as if today were the entry session.")
    elif args.source == "live" and now.time() < ENTRY_CLOCK:
        print("Before 10:30 ET: nothing would happen yet. WHAT-IF below uses the latest quotes.")
    # Phase 1: no state file exists; the running peak starts at the current equity and nothing is open.
    dec = evaluate_entry(today, equity, equity, 0.0, puts)
    dec["mode"], dec["event"], dec["logged_at"] = "dry_run", "entry_decision", now.isoformat(timespec="seconds")
    print_decision(dec)


def run_exit_selftest():
    """Hand-made position: 2 x SPY 650/645 put spread opened for $0.80 credit, expiring Fri 2026-10-16."""
    sessions = {date(2026, 10, 5) + timedelta(days=i): time(16, 0) for i in range(14)
                if (date(2026, 10, 5) + timedelta(days=i)).weekday() < 5}
    pos = {"expiry": date(2026, 10, 16), "credit": 0.80}
    cases = [
        ("quiet, hold", datetime(2026, 10, 7, 11, 0, tzinfo=ET), (1.00, 1.05), (0.40, 0.45)),
        ("take profit (natural 0.40 <= 0.40)", datetime(2026, 10, 8, 12, 0, tzinfo=ET), (0.60, 0.61), (0.21, 0.22)),
        ("stop (natural 1.60 >= 1.60)", datetime(2026, 10, 9, 14, 0, tzinfo=ET), (2.50, 2.60), (1.00, 1.05)),
        ("time exit 10-14 15:45", datetime(2026, 10, 14, 15, 45, tzinfo=ET), (0.90, 0.95), (0.30, 0.35)),
        ("10-14 15:00, before time exit", datetime(2026, 10, 14, 15, 0, tzinfo=ET), (0.90, 0.95), (0.30, 0.35)),
    ]
    print("=== exit-rule self-test on a hand-made position (no market data, no orders) ===")
    print(f"position: {pos}; exit checks run at {[t.strftime('%H:%M') for t in exit_check_times()]} ET")
    for label, now, (sb, sa), (lb, la) in cases:
        r = check_exit(pos, now, Leg("S", 650, -0.15, sb, sa), Leg("L", 645, -0.10, lb, la), sessions)
        print(f"  {label:38} -> {r['action']:5} {r['reason'] or '':12} natural {r['close_natural']:.2f} "
              f"time exit at {r['time_exit_at']}")
    for eq, pk in ((95001, 100000), (95000, 100000)):
        print(f"  pause rule equity {eq} peak {pk}: {'PAUSED' if pause_active(eq, pk) else 'not paused'}")


def main(argv=None):
    p = argparse.ArgumentParser(description="Paper put-spread trial. Phase 1: dry run only.")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--exit-selftest", action="store_true")
    p.add_argument("--source", choices=["live", "stored"], default="live")
    p.add_argument("--date", help="stored mode: the entry date to evaluate (YYYY-MM-DD)")
    p.add_argument("--equity", type=float, default=100000.0, help="stored mode: account equity to size against")
    a = p.parse_args(argv)
    if a.exit_selftest:
        return run_exit_selftest()
    if not a.dry_run:
        sys.exit("Phase 1: only --dry-run (and --exit-selftest) exist. Order placement is not implemented.")
    if a.source == "stored" and not a.date:
        sys.exit("--source stored needs --date")
    run_dry(a)


if __name__ == "__main__":
    main()

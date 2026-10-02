"""
Cost-aware backtester for the cross-sectional straddle hypothesis (CLAUDE.md Section 62).

Inputs : option_snapshots.db (entry/exit chain snapshots), daily_prices.db (SIP raw + split-adjusted
         closes), earnings_dates.db (EDGAR). Nothing here calls an API.
Output : one row per (cycle, ticker) with the signal, eligibility, and returns for every variant, in
         straddle_backtest.db:trades (and a DataFrame-like list from run()).

Conventions (fixed in Phase 0, Section 62):
  * signal   = HV252 - IV_ATM. HV from split-adjusted closes; IV = mean of the ATM call/put EODHD IV.
  * ATM      = strike of the target expiration nearest the RAW entry close with both legs quoted.
  * costs    = fraction f of the half-spread paid on every leg, f in {0 (mid), 0.5, 1 (quoted bid/ask)}.
  * long     = ATM straddle. Return on premium paid.
  * short    = iron butterfly: short ATM straddle, long |delta|~0.10 call/put wings. Return on max-loss
               capital (wing width - net credit).
  * exits    = 'expiry': intrinsic at the RAW expiry close (no exit cost; physical settlement ignored)
               'day_before': close of the exit snapshot at bid (long) / ask (short), same f.
  * hedge    = optional daily-close stock hedge of the LONG straddle, BS delta at entry IV, 1 bp cost.
  * splits   = cycles whose holding window contains a split are excluded.
The BLIND window is refused unless allow_blind=True (Section 62: not examined until the go/no-go gate).
"""
import math, os, sqlite3
from datetime import date
from statistics import median

ROOT = os.path.dirname(os.path.abspath(__file__))
SNAP_DB = os.path.join(ROOT, "option_snapshots.db")
EARN_DB = os.path.join(ROOT, "earnings_dates.db")
OUT_DB = os.path.join(ROOT, "straddle_backtest.db")
R = 0.04
COST_LEVELS = (0.0, 0.5, 1.0)
MAX_SPREAD = 0.05            # liquidity rule: median full straddle spread <= 5% of mid
MIN_LEG_OI, MIN_EXP_OI = 100, 1000
SPREAD_LOOKBACK = 6          # current + up to 5 previous entry snapshots
HEDGE_COST_BP = 1.0
WING_DELTA = 0.10


# ----------------------------------------------------------------- pure pieces (unit-tested)
def fill(bid, ask, side, f):
    """Price paid (side='buy') or received (side='sell') when paying fraction f of the half-spread."""
    mid, half = (bid + ask) / 2, (ask - bid) / 2
    return mid + f * half if side == "buy" else mid - f * half


def hv252(split_closes):
    """Annualized stdev of daily log returns over the last 252 returns (needs 253 closes)."""
    if len(split_closes) < 253:
        return None
    px = split_closes[-253:]
    rets = [math.log(b / a) for a, b in zip(px, px[1:])]
    m = sum(rets) / len(rets)
    return math.sqrt(sum((x - m) ** 2 for x in rets) / (len(rets) - 1)) * math.sqrt(252)


def has_split(ratios, tol=0.005):
    """raw/split-adjusted close ratios over a window; a change > tol means a split inside it."""
    return any(abs(b / a - 1) > tol for a, b in zip(ratios, ratios[1:]))


def straddle_payoff(S, K):
    return abs(S - K)


def iron_fly_payoff(S, K, Kp, Kc):
    """Value owed by the short iron butterfly at expiry (>= 0): short straddle minus long wings."""
    return abs(S - K) - max(S - Kc, 0.0) - max(Kp - S, 0.0)


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def straddle_delta(S, K, T, sigma, r=R):
    if T <= 0:
        return 1.0 if S > K else (-1.0 if S < K else 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return 2 * norm_cdf(d1) - 1          # call delta + put delta


def hedge_pnl(path, K, sigma, expiry_days, cost_bp=HEDGE_COST_BP):
    """Daily-close delta hedge of ONE long straddle. path = [(days_to_expiry, S), ...] from entry close
    to the expiry close. Holds -delta shares from each close to the next. Returns (pnl, cost)."""
    pnl = cost = 0.0
    h_prev = 0.0
    for (dte, S), (_, S_next) in zip(path, path[1:]):
        h = -straddle_delta(S, K, dte / 365.0, sigma)
        cost += abs(h - h_prev) * S * cost_bp / 1e4
        pnl += h * (S_next - S)
        h_prev = h
    cost += abs(h_prev) * path[-1][1] * cost_bp / 1e4      # unwind at expiry
    return pnl, cost


def liquidity_ok(spread_history, leg_ois, exp_oi):
    """Missing OI is UNKNOWN, not zero (EODHD leaves OI null on many half-dollar strikes; found on the
    first measured snapshot, 2026-10-01, before any result existed): a leg with None skips the per-leg
    floor. The expiration-level floor (sum of known OI) and the spread rule always apply."""
    if not spread_history or median(spread_history) > MAX_SPREAD:
        return False
    known = [x for x in leg_ois if x is not None]
    return all(x >= MIN_LEG_OI for x in known) and exp_oi >= MIN_EXP_OI


def group_sizes(n):
    """Quintiles when >= 25 eligible names, otherwise terciles (fixed in Phase 0)."""
    return 5 if n >= 25 else 3


# ----------------------------------------------------------------- data access
def _chain(c, ticker, obs, kind, expiry):
    rows = c.execute("SELECT option_type, strike, bid, ask, open_interest, iv, delta FROM chain "
                     "WHERE ticker=? AND obs_date=? AND kind=? AND exp_date=?",
                     (ticker, obs.isoformat(), kind, expiry.isoformat())).fetchall()
    out = {}
    for typ, k, b, a, oi, iv, d in rows:
        out[(typ, float(k))] = {"bid": b or 0.0, "ask": a or 0.0, "oi": oi, "iv": iv, "delta": d}   # oi may be None
    return out


def _quoted(q):
    return q is not None and q["bid"] > 0 and q["ask"] >= q["bid"]


def evaluate(c, ticker, cyc, prices, earnings, spread_hist):
    """One (cycle, ticker). Returns a dict (with 'excluded' set when not tradeable)."""
    res = {"ticker": ticker, "entry": cyc["entry"].isoformat(), "expiry": cyc["expiry"].isoformat(),
           "window": cyc["window"], "excluded": None}
    days = sorted(d for d in prices if cyc["entry"] <= d <= cyc["expiry"])
    if not days or days[0] != cyc["entry"] or days[-1] != cyc["expiry"]:
        res["excluded"] = "missing_prices"; return res
    if has_split([prices[d][0] / prices[d][1] for d in days]):
        res["excluded"] = "split_in_window"; return res
    S0, ST = prices[cyc["entry"]][0], prices[cyc["expiry"]][0]
    hist = [prices[d][1] for d in sorted(prices) if d <= cyc["entry"]]
    hv = hv252(hist)
    if hv is None:
        res["excluded"] = "insufficient_history"; return res
    ch = _chain(c, ticker, cyc["entry"], "entry", cyc["expiry"])
    strikes = sorted({k for (t, k) in ch if _quoted(ch.get(("call", k))) and _quoted(ch.get(("put", k)))},
                     key=lambda k: abs(k - S0))
    if not strikes:
        res["excluded"] = "no_atm_quotes"; return res
    K = strikes[0]
    cl, pu = ch[("call", K)], ch[("put", K)]
    if not cl["iv"] or not pu["iv"]:
        res["excluded"] = "no_atm_iv"; return res
    iv = (cl["iv"] + pu["iv"]) / 2
    mid = (cl["bid"] + cl["ask"] + pu["bid"] + pu["ask"]) / 2
    spread = (cl["ask"] + pu["ask"] - cl["bid"] - pu["bid"]) / mid
    spread_hist.setdefault(ticker, []).append(spread)
    exp_oi = sum(q["oi"] or 0 for q in ch.values())
    known_leg = [x for x in (cl["oi"], pu["oi"]) if x is not None]
    res.update(signal=hv - iv, hv=hv, iv=iv, K=K, S0=S0, ST=ST, straddle_mid=mid, full_spread=spread,
               leg_oi_min=min(known_leg) if known_leg else None, leg_oi_missing=2 - len(known_leg), exp_oi=exp_oi,
               earnings_in_window=None if earnings.get(ticker) is None else
               int(any(cyc["entry"] < e <= cyc["expiry"] for e in earnings[ticker])))
    res["eligible"] = int(liquidity_ok(spread_hist[ticker][-SPREAD_LOOKBACK:], (cl["oi"], pu["oi"]), exp_oi))

    # wings for the iron butterfly (|delta| nearest 0.10, strictly outside K, quoted)
    calls = [(k, q) for (t, k), q in ch.items() if t == "call" and k > K and _quoted(q) and q["delta"] is not None]
    puts = [(k, q) for (t, k), q in ch.items() if t == "put" and k < K and _quoted(q) and q["delta"] is not None]
    wc = min(calls, key=lambda x: abs(abs(x[1]["delta"]) - WING_DELTA)) if calls else None
    wp = min(puts, key=lambda x: abs(abs(x[1]["delta"]) - WING_DELTA)) if puts else None

    ex = _chain(c, ticker, cyc["exit"], "exit", cyc["expiry"])
    for f in COST_LEVELS:
        tag = f"f{int(f * 100):03d}"
        cost = fill(cl["bid"], cl["ask"], "buy", f) + fill(pu["bid"], pu["ask"], "buy", f)
        res[f"long_exp_{tag}"] = (straddle_payoff(ST, K) - cost) / cost
        # short straddle (Goyal-Saretto straddle basis, NOT implementable here): return on premium received
        credit_s = fill(cl["bid"], cl["ask"], "sell", f) + fill(pu["bid"], pu["ask"], "sell", f)
        if credit_s > 0:
            res[f"shortstrad_exp_{tag}"] = (credit_s - straddle_payoff(ST, K)) / credit_s
        ecl, epu = ex.get(("call", K)), ex.get(("put", K))
        # exit: a $0.00 bid is a valid quote (the leg is worth ~nothing), so only require ask >= bid >= 0
        if all(q is not None and q["ask"] > 0 and q["ask"] >= q["bid"] >= 0 for q in (ecl, epu)):
            val = fill(ecl["bid"], ecl["ask"], "sell", f) + fill(epu["bid"], epu["ask"], "sell", f)
            res[f"long_db_{tag}"] = (val - cost) / cost
        if wc and wp:
            (Kc, qc), (Kp, qp) = wc, wp
            credit = (fill(cl["bid"], cl["ask"], "sell", f) + fill(pu["bid"], pu["ask"], "sell", f)
                      - fill(qc["bid"], qc["ask"], "buy", f) - fill(qp["bid"], qp["ask"], "buy", f))
            max_loss = max(Kc - K, K - Kp) - credit
            if max_loss > 0:
                res[f"fly_exp_{tag}"] = (credit - iron_fly_payoff(ST, K, Kp, Kc)) / max_loss
                res["wing_call"], res["wing_put"] = Kc, Kp
    # daily-close delta hedge of the long straddle (cost level f=1 entry, expiry exit)
    path = [((cyc["expiry"] - d).days, prices[d][0]) for d in days]
    hp, hc = hedge_pnl(path, K, iv, (cyc["expiry"] - cyc["entry"]).days)
    cost1 = cl["ask"] + pu["ask"]
    res["long_exp_hedged_f100"] = (straddle_payoff(ST, K) - cost1 + hp - hc) / cost1
    return res


def run(window="dev", allow_blind=False):
    if window != "dev" and not allow_blind:
        raise PermissionError("BLIND window is not to be examined until the go/no-go gate (Section 62)")
    from straddle_schedule import cycles
    from daily_prices import load
    from generate_broader_universe_volatility_dataset import TICKERS
    e = sqlite3.connect(EARN_DB)
    known = {t for (t,) in e.execute("SELECT ticker FROM edgar_coverage WHERE status='ok'")}
    earnings = {t: None for t in TICKERS}
    for t in known:
        earnings[t] = [date.fromisoformat(d) for (d,) in e.execute("SELECT session_date FROM earnings WHERE ticker=?", (t,))]
    e.close()
    c = sqlite3.connect(SNAP_DB)
    have = {(t, d) for t, d in c.execute("SELECT ticker, obs_date FROM snapshot_summary WHERE kind='entry' AND complete=1")}
    cyc = [x for x in cycles(last_entry=date.today()) if x["window"] == window and x["expiry"] < date.today()]
    prices = {t: load(t) for t in TICKERS}
    spread_hist, rows = {}, []
    for x in cyc:
        for t in TICKERS:
            if (t, x["entry"].isoformat()) not in have:
                rows.append({"ticker": t, "entry": x["entry"].isoformat(), "expiry": x["expiry"].isoformat(),
                             "window": window, "excluded": "no_snapshot"})
                continue
            rows.append(evaluate(c, t, x, prices[t], earnings, spread_hist))
    c.close()
    _save(rows)
    return rows


def _save(rows):
    cols = sorted({k for r in rows for k in r})
    with sqlite3.connect(OUT_DB) as o:
        o.execute("DROP TABLE IF EXISTS trades")
        o.execute(f"CREATE TABLE trades ({', '.join(cols)})")
        o.executemany(f"INSERT INTO trades ({', '.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                      [tuple(r.get(k) for k in cols) for r in rows])


if __name__ == "__main__":
    rows = run("dev")
    ok = [r for r in rows if not r["excluded"]]
    print(f"{len(rows)} ticker-cycles, {len(ok)} evaluated, {sum(r.get('eligible', 0) for r in ok)} eligible")

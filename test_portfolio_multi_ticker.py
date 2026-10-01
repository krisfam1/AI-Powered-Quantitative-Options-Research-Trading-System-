from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timezone, timedelta
from portfolio_backtest import run_portfolio_backtest

end = datetime.now(timezone.utc)
start = end - timedelta(days=30)

TICKERS = ["AAPL", "MSFT", "NVDA", "SMCI", "MSTR", "AMD"]
STARTING_CAPITAL = 100000.0

print("=" * 70)
print("MULTI-TICKER RUN -- " + ", ".join(TICKERS))
print("=" * 70)
multi_result = run_portfolio_backtest(
    TICKERS, start, end, starting_capital=STARTING_CAPITAL, fixed_direction="call"
)
print("Result dict top-level keys: " + str(sorted(multi_result.keys())))
print("Total trades: " + str(multi_result["total_trades"]))

multi_trades = multi_result["closed_trades"]
if multi_trades:
    print("Trade record keys: " + str(sorted(multi_trades[0].keys())))

print("\nTrades per ticker (multi-ticker run):")
by_ticker_multi = {}
for t in multi_trades:
    by_ticker_multi.setdefault(t["ticker"], []).append(t)
for tk in TICKERS:
    trades = by_ticker_multi.get(tk, [])
    dates = sorted(str(t["entry_date"]) for t in trades)
    print(f"  {tk}: {len(trades)} trades -- {dates}")

# --- Check 1: does running a ticker alongside others change its own trades? ---
print("\n" + "=" * 70)
print("CHECK 1: SOLO vs CONCURRENT -- does each ticker trade the same way alone?")
print("=" * 70)

for tk in TICKERS:
    solo_result = run_portfolio_backtest(
        [tk], start, end, starting_capital=STARTING_CAPITAL, fixed_direction="call"
    )
    solo_trades = solo_result["closed_trades"]
    solo_dates = sorted(str(t["entry_date"]) for t in solo_trades)
    multi_dates = sorted(str(t["entry_date"]) for t in by_ticker_multi.get(tk, []))

    print(f"\n  {tk}:")
    print(f"    Solo run entry dates:       {solo_dates}")
    print(f"    Concurrent run entry dates: {multi_dates}")
    if solo_dates == multi_dates:
        print(f"    -> MATCH: {tk}'s trades are unaffected by running alongside other tickers.")
    else:
        only_solo = sorted(set(solo_dates) - set(multi_dates))
        only_multi = sorted(set(multi_dates) - set(solo_dates))
        print(f"    -> DIFFERS.")
        if only_solo:
            print(f"       Entries present SOLO but MISSING when concurrent: {only_solo}")
            print(f"       (Possible cause: insufficient cash when other tickers held positions)")
        if only_multi:
            print(f"       Entries present CONCURRENT but MISSING when solo: {only_multi}")
            print(f"       (This would be unexpected -- flag for investigation)")

# --- Check 2: was capital ever over-committed across overlapping positions? ---
print("\n" + "=" * 70)
print("CHECK 2: CAPITAL SAFETY -- do overlapping positions ever exceed starting capital?")
print("=" * 70)

events = []
for t in multi_trades:
    cost = t.get("cost")
    entry_d = t.get("entry_date")
    exit_d = t.get("exit_date")
    if cost is None or entry_d is None or exit_d is None:
        continue
    events.append((entry_d, "open", cost, t["ticker"]))
    events.append((exit_d, "close", cost, t["ticker"]))

events.sort(key=lambda e: (e[0], 0 if e[1] == "close" else 1))

committed = 0.0
max_committed = 0.0
violation_found = False
for d, kind, cost, tk in events:
    if kind == "open":
        committed += cost
        if committed > max_committed:
            max_committed = committed
        if committed > STARTING_CAPITAL:
            violation_found = True
            print(f"  [!] {d}: committed capital ${committed:,.2f} EXCEEDS starting capital ${STARTING_CAPITAL:,.2f} (opening {tk})")
    else:
        committed -= cost

print(f"\n  Peak committed capital during backtest: ${max_committed:,.2f} (starting capital: ${STARTING_CAPITAL:,.2f})")
if not violation_found:
    print("  No capital over-commitment detected across overlapping positions.")

utilization_pct = (max_committed / STARTING_CAPITAL) * 100
print(f"  Peak capital utilization: {utilization_pct:.1f}%")
if utilization_pct < 20:
    print("  NOTE: utilization is very low. This means positions rarely/never")
    print("  competed for cash, so Check 1 above doesn't meaningfully test")
    print("  capital-sharing logic under pressure. Running a second, deliberately")
    print("  constrained scenario below to force real competition...")

# --- Check 3: force real capital competition with a much smaller pool ---
print("\n" + "=" * 70)
print("CHECK 3: CAPITAL COMPETITION UNDER PRESSURE (small starting capital)")
print("=" * 70)

TIGHT_CAPITAL = 3000.0  # small enough that tickers should have to compete
print(f"Re-running with starting_capital=${TIGHT_CAPITAL:,.2f} to force real competition for cash.\n")

tight_result = run_portfolio_backtest(
    TICKERS, start, end, starting_capital=TIGHT_CAPITAL, fixed_direction="call"
)
tight_trades = tight_result["closed_trades"]
print(f"Total trades under tight capital: {tight_result['total_trades']}")

by_ticker_tight = {}
for t in tight_trades:
    by_ticker_tight.setdefault(t["ticker"], []).append(t)

for tk in TICKERS:
    solo_result = run_portfolio_backtest(
        [tk], start, end, starting_capital=TIGHT_CAPITAL, fixed_direction="call"
    )
    solo_dates = sorted(str(t["entry_date"]) for t in solo_result["closed_trades"])
    tight_dates = sorted(str(t["entry_date"]) for t in by_ticker_tight.get(tk, []))
    missing = sorted(set(solo_dates) - set(tight_dates))
    print(f"\n  {tk}:")
    print(f"    Solo (tight capital) entry dates: {solo_dates}")
    print(f"    Concurrent (tight capital) dates: {tight_dates}")
    if missing:
        print(f"    -> {len(missing)} entr{'y' if len(missing)==1 else 'ies'} skipped due to capital competition: {missing}")
    else:
        print(f"    -> No entries skipped (this ticker never lost the capital race)")

# Re-check capital safety under the tight scenario too
events2 = []
for t in tight_trades:
    cost = t.get("cost")
    entry_d = t.get("entry_date")
    exit_d = t.get("exit_date")
    if cost is None or entry_d is None or exit_d is None:
        continue
    events2.append((entry_d, "open", cost, t["ticker"]))
    events2.append((exit_d, "close", cost, t["ticker"]))
events2.sort(key=lambda e: (e[0], 0 if e[1] == "close" else 1))

committed2 = 0.0
max_committed2 = 0.0
violation2 = False
for d, kind, cost, tk in events2:
    if kind == "open":
        committed2 += cost
        max_committed2 = max(max_committed2, committed2)
        if committed2 > TIGHT_CAPITAL:
            violation2 = True
            print(f"  [!] {d}: committed ${committed2:,.2f} EXCEEDS tight capital ${TIGHT_CAPITAL:,.2f} (opening {tk})")
    else:
        committed2 -= cost

print(f"\n  Peak committed capital (tight scenario): ${max_committed2:,.2f} (limit: ${TIGHT_CAPITAL:,.2f})")
if not violation2:
    print("  No capital over-commitment detected -- engine correctly declined trades it couldn't afford.")

# --- Check 4: step down through capital tiers to find where can_afford actually fires ---
# NOTE: contracts = max(int(risk_dollars / (entry_premium * 100)), 1) -- the max(...,1)
# floor means position size never shrinks with capital. So capital has to get small
# enough that even ONE contract (roughly entry_premium * 100, ~$300-700 here) can't
# be afforded before we'll ever see a real decline. $3,000 wasn't tight enough.
print("\n" + "=" * 70)
print("CHECK 4: FINDING THE ACTUAL CAPITAL-COMPETITION THRESHOLD")
print("=" * 70)

for tier_capital in [1500.0, 800.0, 500.0, 250.0, 100.0]:
    tier_result = run_portfolio_backtest(
        TICKERS, start, end, starting_capital=tier_capital, fixed_direction="call"
    )
    tier_trades = tier_result["closed_trades"]
    tier_total = tier_result["total_trades"]

    # capital safety check at this tier
    tevents = []
    for t in tier_trades:
        cost = t.get("cost")
        if cost is None:
            continue
        tevents.append((t["entry_date"], "open", cost))
        tevents.append((t["exit_date"], "close", cost))
    tevents.sort(key=lambda e: (e[0], 0 if e[1] == "close" else 1))
    tcommitted = 0.0
    tmax = 0.0
    tviolation = False
    for d, kind, cost in tevents:
        if kind == "open":
            tcommitted += cost
            tmax = max(tmax, tcommitted)
            if tcommitted > tier_capital:
                tviolation = True
        else:
            tcommitted -= cost

    baseline_total = multi_result["total_trades"]  # from the original $100k run
    skipped = baseline_total - tier_total
    status = "OVER-COMMITTED (BUG)" if tviolation else "safe"
    print(f"  capital=${tier_capital:>8,.2f}  trades={tier_total:>3} (vs {baseline_total} at $100k, {skipped} fewer)  "
          f"peak_committed=${tmax:>8,.2f}  [{status}]")

print("\n  If 'trades' never drops below the $100k baseline even at very low capital,")
print("  that itself is worth investigating -- it would mean can_afford is either")
print("  never being checked, or entry_premium/cost values are smaller than expected.")

# --- Check 5: read REAL cash values from equity_history instead of ---
# --- reconstructing overlap from date-only entry/exit fields.       ---
# The earlier Check 2/3/4 "over-commitment" flags were a false positive
# caused by day-level date reconstruction not capturing true intraday
# overlap. equity_history logs the account's actual self.cash at every
# timestamp during the real run, which is ground truth.
print("\n" + "=" * 70)
print("CHECK 5: REAL CASH TRACKING (from equity_history, ground truth)")
print("=" * 70)

for tier_capital in [800.0, 500.0, 250.0, 100.0]:
    tier_result = run_portfolio_backtest(
        TICKERS, start, end, starting_capital=tier_capital, fixed_direction="call"
    )
    hist = tier_result.get("equity_history", [])
    if not hist:
        print(f"  capital=${tier_capital:,.2f}: no equity_history returned -- cannot verify")
        continue
    cash_values = [h["cash"] for h in hist if "cash" in h]
    if not cash_values:
        print(f"  capital=${tier_capital:,.2f}: equity_history entries have no 'cash' field")
        continue
    min_cash = min(cash_values)
    max_cash = max(cash_values)
    negative = min_cash < 0
    status = "NEGATIVE CASH (real bug)" if negative else "safe -- cash never went negative"
    print(f"  capital=${tier_capital:>8,.2f}  min_cash=${min_cash:>10,.2f}  max_cash=${max_cash:>10,.2f}  [{status}]")

print("\n  This reads the engine's own self.cash value at every timestamp,")
print("  not a reconstruction -- if min_cash is never negative here, the")
print("  capital guard is confirmed safe under real conditions.")
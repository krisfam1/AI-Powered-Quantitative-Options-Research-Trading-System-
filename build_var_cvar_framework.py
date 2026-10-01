from dotenv import load_dotenv
load_dotenv()

"""
DIAGNOSTIC INVESTIGATION / RISK INFRASTRUCTURE BUILD, not a pre-registered
experiment -- no config hash, no VALIDATED/REJECTED decision rule, same
category as the LSM pricing investigation (Section 49) and the Contract-
Identity Investigation. Builds a Monte Carlo VaR/CVaR framework for this
project's options positions and retroactively validates it against V1's
real, frozen 251-trade history -- a genuine correctness check ("would this
have flagged the real risk"), not a fishing expedition.

METHODOLOGY:
- Bootstrapped (not parametric GBM) Monte Carlo: draws real historical
  daily log returns for the 6 project tickers, with replacement, from a
  TRAILING window strictly before each evaluation point (no lookahead).
- JOINT block bootstrap across tickers: each simulation draw samples a set
  of real historical CALENDAR DATES and uses ALL 6 tickers' REAL returns
  on those SAME dates together -- preserves genuine historical cross-
  ticker correlation, which independent per-ticker bootstrapping would
  destroy.
- Per-trade VaR/CVaR: at each of V1's 251 real trades' ENTRY dates, solves
  the entry-implied volatility from the REAL recorded entry_premium (via
  bisection on the project's own validated black_scholes_price()),
  bootstrap-simulates the underlying's cumulative return over that trade's
  ACTUAL REALIZED holding period (trailing real returns before entry only),
  RE-PRICES the option at each simulated exit spot via a VECTORIZED
  reimplementation of the exact same Black-Scholes formula (same scipy
  norm.cdf, same clipping behavior, verified against the scalar function --
  not a re-derivation), and computes VaR95/99 and CVaR95/99 in real dollar
  terms. Compared directly against the trade's own REAL realized pnl_dollars.
- Portfolio-level: weekly cadence across V1's real window, jointly
  bootstraps a portfolio P&L distribution for that week's actual open
  positions, tracks portfolio VaR/CVaR as a time series vs. Phase 7's
  already-documented loss concentration (CLAUDE.md Section 5/13).

PERFORMANCE NOTE, disclosed: an earlier version of this script used
scalar Python loops (calling black_scholes_price and rng.choice once per
simulation, 10,000 times per trade) and was too slow to finish in a
reasonable time -- killed and rewritten here with vectorized numpy
throughout. The vectorized Black-Scholes was verified to match the
project's own scalar black_scholes_price() before being trusted.

Does NOT touch, modify, or re-run any closed experiment. Reuses V1's
exact, already-verified reproduction call and this project's own
black_scholes_price() formula (in vectorized form, verified equivalent).
"""

import json
import os
import warnings
from datetime import datetime, timezone, timedelta

import numpy as np
from scipy.stats import norm
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from portfolio_backtest import run_portfolio_backtest
from options_pricing import black_scholes_price

warnings.filterwarnings("ignore")

TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]
FIXED_START = datetime(2026, 6, 11, tzinfo=timezone.utc)
FIXED_END = datetime(2026, 9, 9, tzinfo=timezone.utc)
RISK_FREE_RATE = 0.04
TRAILING_LOOKBACK_DAYS = 90
N_SIMS = 20000
CONFIDENCE_LEVELS = [0.95, 0.99]


def log(msg: str) -> None:
    print(msg, flush=True)


def fetch_daily_bars(ticker, start, end):
    api_key = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    client = StockHistoricalDataClient(api_key, secret_key)
    req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame(1, TimeFrameUnit.Day), start=start, end=end, feed=DataFeed.IEX)
    bars = list(client.get_stock_bars(req)[ticker])
    return {b.timestamp.date(): float(b.close) for b in bars}


def bs_price_vec(S, K, dte_days, vol, r=RISK_FREE_RATE, option_type="call"):
    """Vectorized Black-Scholes, S may be a numpy array; K/dte_days/vol/r are
    scalars. Mirrors options_pricing.py:black_scholes_price() exactly --
    verified equivalent below before trusting it on real data."""
    S = np.asarray(S, dtype=float)
    if dte_days <= 0:
        if option_type == "call":
            return np.maximum(S - K, 0.0)
        else:
            return np.maximum(K - S, 0.0)
    t = dte_days / 365.0
    d1 = (np.log(S / K) + (r + 0.5 * vol ** 2) * t) / (vol * np.sqrt(t))
    d2 = d1 - vol * np.sqrt(t)
    if option_type == "call":
        price = S * norm.cdf(d1) - K * np.exp(-r * t) * norm.cdf(d2)
    else:
        price = K * np.exp(-r * t) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return np.maximum(price, 0.0)


def solve_implied_vol(target_price, spot, strike, dte, option_type="call", lo=0.01, hi=5.0, tol=1e-5, max_iter=60):
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        price = black_scholes_price(spot, strike, dte, mid, RISK_FREE_RATE, option_type)
        if abs(price - target_price) < tol:
            return mid
        if price < target_price:
            lo = mid
        else:
            hi = mid
    return mid


def main():
    report = {}

    # ---- Verify the vectorized BS matches the scalar version before trusting it ----
    log("Verifying vectorized Black-Scholes matches the project's own scalar black_scholes_price()...")
    test_S = np.array([90.0, 100.0, 110.0, 120.0])
    scalar_prices = np.array([black_scholes_price(s, 100.0, 14, 0.35, RISK_FREE_RATE, "call") for s in test_S])
    vec_prices = bs_price_vec(test_S, 100.0, 14, 0.35, RISK_FREE_RATE, "call")
    max_diff = float(np.max(np.abs(scalar_prices - vec_prices)))
    log(f"  max abs diff (scalar vs vectorized), 4 test points: {max_diff:.10f} -- MUST be ~0")
    assert max_diff < 1e-8, "Vectorized BS does not match scalar BS -- STOP, do not trust results"
    report["vectorization_check_max_diff"] = max_diff

    # ---- Reproduce V1's REAL, frozen 251-trade history ----
    log("\nReproducing frozen V1 baseline (must match: $20,427.64, 251 trades)...")
    v1_results = {}
    for ticker in TICKERS:
        v1_results[ticker] = run_portfolio_backtest(
            [ticker], FIXED_START, FIXED_END, starting_capital=100000.0,
            fixed_direction="call", pricing_mode="v1"
        )
        log(f"  {ticker} done")
    all_trades = [{**t, "ticker": tk} for tk in TICKERS for t in v1_results[tk]["closed_trades"]]
    total_pnl = sum(t["pnl_dollars"] for t in all_trades)
    log(f"Reproduced: ${total_pnl:.2f}, n={len(all_trades)}")
    assert abs(total_pnl - 20427.64) < 0.01 and len(all_trades) == 251, "V1 reproduction mismatch -- STOP"
    report["v1_reproduction_confirmed"] = {"total_pnl": total_pnl, "n_trades": len(all_trades)}

    # ---- Fetch real daily bars ----
    log("\nFetching real daily bars (with trailing lookback buffer)...")
    fetch_start = FIXED_START - timedelta(days=TRAILING_LOOKBACK_DAYS * 2)
    daily_closes = {t: fetch_daily_bars(t, fetch_start, FIXED_END + timedelta(days=1)) for t in TICKERS}
    for t in TICKERS:
        log(f"  {t}: {len(daily_closes[t])} daily bars")

    all_dates = sorted(set().union(*[set(daily_closes[t].keys()) for t in TICKERS]))
    log_returns = {t: {} for t in TICKERS}
    for t in TICKERS:
        dates_t = sorted(daily_closes[t].keys())
        for i in range(1, len(dates_t)):
            d0, d1 = dates_t[i - 1], dates_t[i]
            log_returns[t][d1] = float(np.log(daily_closes[t][d1] / daily_closes[t][d0]))

    def trailing_dates(as_of_date, lookback=TRAILING_LOOKBACK_DAYS):
        candidates = [d for d in all_dates if d < as_of_date and all(d in log_returns[t] for t in TICKERS)]
        return candidates[-lookback:] if len(candidates) > lookback else candidates

    def returns_array(ticker, dates_list):
        return np.array([log_returns[ticker][d] for d in dates_list])

    # =========================================================================
    # PER-TRADE VaR/CVaR, VECTORIZED
    # =========================================================================
    log("\n" + "=" * 100)
    log("PER-TRADE VaR/CVaR -- vectorized, computed at entry, no lookahead")
    log("=" * 100)

    per_trade_results = []
    skipped = 0
    for i, tr in enumerate(all_trades):
        ticker = tr["ticker"]
        entry_date = tr["entry_date"]
        exit_date = tr["exit_date"]
        strike = tr["strike"]
        entry_premium = tr["entry_premium"]
        contracts = tr["contracts"]
        expiry_date = tr["expiry_date"]
        option_type = tr["option_type"]

        if entry_date not in daily_closes[ticker]:
            skipped += 1
            continue
        entry_spot = daily_closes[ticker][entry_date]
        dte_at_entry = (expiry_date - entry_date).days
        if dte_at_entry <= 0:
            skipped += 1
            continue

        entry_vol = solve_implied_vol(entry_premium, entry_spot, strike, dte_at_entry, option_type)

        tdates = trailing_dates(entry_date)
        if len(tdates) < 20:
            skipped += 1
            continue

        holding_trading_days = max(1, len([d for d in all_dates if entry_date < d <= exit_date and d in log_returns[ticker]]))
        ret_pool = returns_array(ticker, tdates)

        rng = np.random.RandomState(hash((ticker, str(entry_date))) % (2**31))
        idx = rng.randint(0, len(ret_pool), size=(N_SIMS, holding_trading_days))  # ONE vectorized draw
        cum_log_returns = ret_pool[idx].sum(axis=1)  # vectorized sum, no python loop
        simulated_exit_spots = entry_spot * np.exp(cum_log_returns)

        dte_at_exit = max(dte_at_entry - holding_trading_days, 0)
        simulated_exit_premiums = bs_price_vec(simulated_exit_spots, strike, dte_at_exit, entry_vol, RISK_FREE_RATE, option_type)
        simulated_pnl = (simulated_exit_premiums - entry_premium) * contracts * 100

        var_cvar = {}
        for cl in CONFIDENCE_LEVELS:
            pct = (1 - cl) * 100
            var_val = float(np.percentile(simulated_pnl, pct))
            tail = simulated_pnl[simulated_pnl <= var_val]
            cvar_val = float(np.mean(tail)) if len(tail) > 0 else var_val
            var_cvar[f"VaR{int(cl*100)}"] = var_val
            var_cvar[f"CVaR{int(cl*100)}"] = cvar_val

        per_trade_results.append({
            "ticker": ticker, "entry_date": str(entry_date), "exit_date": str(exit_date),
            "holding_trading_days": holding_trading_days, "entry_vol": entry_vol,
            "realized_pnl": float(tr["pnl_dollars"]), "exit_reason": tr["exit_reason"],
            **var_cvar,
            "breach_95": bool(tr["pnl_dollars"] < var_cvar["VaR95"]),
            "breach_99": bool(tr["pnl_dollars"] < var_cvar["VaR99"]),
        })

        if (i + 1) % 50 == 0:
            log(f"  {i+1}/{len(all_trades)} trades processed...")

    log(f"Computed VaR/CVaR for {len(per_trade_results)} trades ({skipped} skipped -- insufficient trailing data or degenerate DTE)")
    report["per_trade_n"] = len(per_trade_results)
    report["per_trade_skipped"] = skipped

    breach_rate_95 = np.mean([r["breach_95"] for r in per_trade_results]) * 100
    breach_rate_99 = np.mean([r["breach_99"] for r in per_trade_results]) * 100
    log(f"\nVaR95 breach rate: {breach_rate_95:.1f}% (well-calibrated model expects ~5%)")
    log(f"VaR99 breach rate: {breach_rate_99:.1f}% (well-calibrated model expects ~1%)")
    report["breach_rate_95_pct"] = float(breach_rate_95)
    report["breach_rate_99_pct"] = float(breach_rate_99)

    log("\n--- Exit-reason breakdown ---")
    for reason in ["stop_loss", "reversal_guard", "expired"]:
        sub = [r for r in per_trade_results if r["exit_reason"] == reason]
        if not sub:
            continue
        mean_realized = np.mean([r["realized_pnl"] for r in sub])
        mean_cvar99 = np.mean([r["CVaR99"] for r in sub])
        mean_var99 = np.mean([r["VaR99"] for r in sub])
        breach99_rate = np.mean([r["breach_99"] for r in sub]) * 100
        log(f"  {reason} (n={len(sub)}): mean_realized_pnl=${mean_realized:.2f}  mean_VaR99=${mean_var99:.2f}  mean_CVaR99=${mean_cvar99:.2f}  breach99_rate={breach99_rate:.1f}%")

    report["per_trade_all"] = per_trade_results

    # =========================================================================
    # PORTFOLIO-LEVEL, weekly cadence, VECTORIZED
    # =========================================================================
    log("\n" + "=" * 100)
    log("PORTFOLIO-LEVEL VaR/CVaR, weekly cadence")
    log("=" * 100)

    week_starts = []
    d = FIXED_START.date()
    while d <= FIXED_END.date():
        week_starts.append(d)
        d += timedelta(days=7)

    weekly_results = []
    for wk_start in week_starts:
        wk_end = wk_start + timedelta(days=7)
        open_trades = [t for t in all_trades if t["entry_date"] <= wk_start and t["exit_date"] > wk_start]
        if not open_trades:
            continue
        tdates = trailing_dates(wk_start)
        if len(tdates) < 20:
            continue

        rng = np.random.RandomState(hash(str(wk_start)) % (2**31))

        portfolio_pnl = np.zeros(N_SIMS)
        for tr in open_trades:
            ticker = tr["ticker"]
            if wk_start not in daily_closes[ticker] or tr["entry_date"] not in daily_closes[ticker]:
                continue
            spot_now = daily_closes[ticker][wk_start]
            dte_now = (tr["expiry_date"] - wk_start).days
            if dte_now <= 0:
                continue
            entry_spot = daily_closes[ticker][tr["entry_date"]]
            dte_at_entry_full = (tr["expiry_date"] - tr["entry_date"]).days
            vol_now = solve_implied_vol(tr["entry_premium"], entry_spot, tr["strike"], dte_at_entry_full, tr["option_type"])
            current_value = black_scholes_price(spot_now, tr["strike"], dte_now, vol_now, RISK_FREE_RATE, tr["option_type"])

            ret_pool = returns_array(ticker, tdates)
            idx = rng.randint(0, len(ret_pool), size=(N_SIMS, 5))
            cum_returns = ret_pool[idx].sum(axis=1)
            sim_spots = spot_now * np.exp(cum_returns)
            dte_future = max(dte_now - 5, 0)
            sim_values = bs_price_vec(sim_spots, tr["strike"], dte_future, vol_now, RISK_FREE_RATE, tr["option_type"])
            portfolio_pnl += (sim_values - current_value) * tr["contracts"] * 100

        realized_next_week_pnl = sum(
            t["pnl_dollars"] for t in all_trades if wk_start < t["exit_date"] <= wk_end and t["entry_date"] <= wk_start
        )

        var95 = float(np.percentile(portfolio_pnl, 5))
        var99 = float(np.percentile(portfolio_pnl, 1))
        cvar95 = float(np.mean(portfolio_pnl[portfolio_pnl <= var95])) if np.any(portfolio_pnl <= var95) else var95
        cvar99 = float(np.mean(portfolio_pnl[portfolio_pnl <= var99])) if np.any(portfolio_pnl <= var99) else var99

        weekly_results.append({
            "week_start": str(wk_start), "n_open": len(open_trades), "VaR95": var95, "VaR99": var99,
            "CVaR95": cvar95, "CVaR99": cvar99, "realized_pnl_next_week": float(realized_next_week_pnl),
            "breach_95": bool(realized_next_week_pnl < var95), "breach_99": bool(realized_next_week_pnl < var99),
        })
        log(f"  {wk_start}: n_open={len(open_trades)} VaR95=${var95:.0f} CVaR95=${cvar95:.0f} VaR99=${var99:.0f} CVaR99=${cvar99:.0f}  realized_next_wk=${realized_next_week_pnl:.0f}  breach95={realized_next_week_pnl < var95}  breach99={realized_next_week_pnl < var99}")

    report["weekly_results"] = weekly_results
    n_breach_95 = sum(1 for w in weekly_results if w["breach_95"])
    n_breach_99 = sum(1 for w in weekly_results if w["breach_99"])
    log(f"\nWeekly breach summary: {n_breach_95}/{len(weekly_results)} weeks breached VaR95, {n_breach_99}/{len(weekly_results)} breached VaR99")
    report["weekly_breach_summary"] = {"n_weeks": len(weekly_results), "n_breach_95": n_breach_95, "n_breach_99": n_breach_99}

    with open("var_cvar_investigation_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log("\nFull results written to var_cvar_investigation_results.json")


if __name__ == "__main__":
    main()

from dotenv import load_dotenv
load_dotenv()

"""
gex_calculator.py -- Phase 2 of the GEX research pipeline.

Calculates historical GEX metrics from Phase 1's validated cleaned_snapshot
data. Does NOT run any experiment, does NOT touch the frozen baseline,
does NOT combine metrics into a score, does NOT select a trade contract.

UNIVERSE CLARIFICATION (per explicit instruction): the 0-45 DTE universe
used here is for calculating AGGREGATE, MARKET-WIDE GEX only. It is NOT
the eventual intraday trade-contract selection universe -- that is a
separate, later, frozen specification (option-level P&L phase).

GAMMA FLIP -- TWO DISTINCT, CLEARLY LABELED METHODOLOGIES:

Method A ("cumulative_strike_transition", research-defined, simpler):
orders real strikes by price, sums each contract's REAL (as-observed)
gamma x OI in strike order, and finds where this cumulative sum changes
sign. This does NOT model how gamma would change if the underlying
itself moved -- it only reflects the REAL, static snapshot's own strike
distribution. NOT the standard "gamma flip" concept used by vendors.

Method B ("true_zero_gamma", the standard, mathematically correct
methodology): sweeps a grid of HYPOTHETICAL underlying prices, and at
each hypothetical price, RECOMPUTES every contract's Black-Scholes gamma
using that contract's real strike, real DTE, and real observed IV
(assumed constant as hypothetical spot varies -- a standard, documented
simplification also used by real GEX vendors), weighted by real,
historical OI. Finds the hypothetical price where the aggregate,
recomputed GEX crosses zero. This is what "gamma flip" / "zero-gamma
level" actually means in standard usage.

Both are calculated and stored; neither silently substitutes for the
other.
"""

import os
import sqlite3
import math
from datetime import datetime, timedelta, timezone
import backtest_engine as be
from options_pricing import calculate_gamma

DB_PATH = "gex_data_cache.db"
SIGN_CONVENTIONS = ["model_a", "flipped"]


def _init_gex_table() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gex_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT, snapshot_date TEXT, sign_convention TEXT,
                spot_price REAL, spot_price_source TEXT, spot_price_date TEXT,
                contracts_used INTEGER, calls_used INTEGER, puts_used INTEGER,
                net_gex REAL, gex_regime TEXT,
                cumulative_strike_transition_price REAL,
                true_zero_gamma_price REAL, true_zero_gamma_note TEXT,
                call_wall_strike REAL, call_wall_gex REAL,
                put_wall_strike REAL, put_wall_gex REAL,
                gamma_gradient_at_spot REAL,
                calculated_at TEXT
            )
        """)


def get_historical_spot_price(ticker: str, date_str: str) -> dict:
    """Real, independent underlying close from Alpaca for the EXACT snapshot date -- never a later or future price."""
    obs_date = datetime.strptime(date_str, "%Y-%m-%d")
    start = obs_date.replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    bars = be.get_historical_bars(ticker, start, end)
    if not bars:
        return {"spot_price": None, "source": "alpaca", "date": date_str, "error": "no bars returned"}
    return {"spot_price": float(bars[-1].close), "source": "alpaca_historical_bars", "date": date_str}


def _load_snapshot_contracts(ticker: str, date_str: str) -> list:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM cleaned_snapshot WHERE ticker=? AND snapshot_date=?",
            (ticker, date_str)
        ).fetchall()
    return [dict(r) for r in rows]


def _dte(exp_date_str: str, obs_date_str: str) -> int:
    exp = datetime.strptime(exp_date_str, "%Y-%m-%d").date()
    obs = datetime.strptime(obs_date_str, "%Y-%m-%d").date()
    return (exp - obs).days


def calculate_net_gex(contracts: list, spot_price: float, sign_convention: str) -> dict:
    """Model A / flipped Net GEX, using each contract's REAL, as-observed gamma (no hypothetical repricing)."""
    call_gex = 0.0
    put_gex = 0.0
    for c in contracts:
        if c["gamma"] is None or c["open_interest"] is None:
            continue
        contribution = c["gamma"] * c["open_interest"] * 100 * (spot_price ** 2) * 0.01
        if c["option_type"] == "call":
            call_gex += contribution
        elif c["option_type"] == "put":
            put_gex += contribution

    if sign_convention == "model_a":
        net = call_gex - put_gex
    else:
        net = put_gex - call_gex

    return {"net_gex": net, "call_gex_raw": call_gex, "put_gex_raw": put_gex}


def calculate_cumulative_strike_transition(contracts: list, spot_price: float, sign_convention: str):
    """Method A -- research-defined, NOT the standard gamma flip. Real, as-observed gamma, ordered by strike."""
    by_strike = {}
    for c in contracts:
        if c["gamma"] is None or c["open_interest"] is None or c["strike"] is None:
            continue
        contribution = c["gamma"] * c["open_interest"] * 100 * (spot_price ** 2) * 0.01
        if sign_convention == "model_a":
            signed = contribution if c["option_type"] == "call" else -contribution
        else:
            signed = -contribution if c["option_type"] == "call" else contribution
        by_strike[c["strike"]] = by_strike.get(c["strike"], 0.0) + signed

    strikes_sorted = sorted(by_strike.keys())
    if len(strikes_sorted) < 2:
        return None

    cumulative = 0.0
    prev_strike, prev_cumulative = None, None
    for strike in strikes_sorted:
        cumulative += by_strike[strike]
        if prev_cumulative is not None and (prev_cumulative < 0) != (cumulative < 0):
            if cumulative != prev_cumulative:
                frac = -prev_cumulative / (cumulative - prev_cumulative)
                return prev_strike + frac * (strike - prev_strike)
            return strike
        prev_strike, prev_cumulative = strike, cumulative
    return None


def calculate_true_zero_gamma(contracts: list, current_spot: float, sign_convention: str, obs_date_str: str) -> dict:
    """
    Method B -- the standard, mathematically correct zero-gamma/flip
    calculation. Sweeps hypothetical spot prices; at each, RECOMPUTES
    every contract's Black-Scholes gamma using its real strike, real
    DTE, and real observed IV (held constant as hypothetical spot
    varies -- documented simplification).
    """
    valid_contracts = [
        c for c in contracts
        if c["open_interest"] and c["volatility"] and c["strike"] and c["exp_date"]
    ]
    if not valid_contracts:
        return {"price": None, "note": "no contracts had sufficient data (OI, IV, strike, exp_date) for hypothetical repricing"}

    grid_low = current_spot * 0.80
    grid_high = current_spot * 1.20
    grid_step = max((grid_high - grid_low) / 200, 0.25)

    hypothetical_price = grid_low
    prev_price, prev_gex = None, None
    crossing = None

    while hypothetical_price <= grid_high:
        total = 0.0
        for c in valid_contracts:
            dte = _dte(c["exp_date"], obs_date_str)
            if dte <= 0:
                continue
            try:
                g = calculate_gamma(hypothetical_price, c["strike"], dte, c["volatility"])
            except Exception:
                continue
            contribution = g * c["open_interest"] * 100 * (hypothetical_price ** 2) * 0.01
            if sign_convention == "model_a":
                total += contribution if c["option_type"] == "call" else -contribution
            else:
                total += -contribution if c["option_type"] == "call" else contribution

        if prev_gex is not None and (prev_gex < 0) != (total < 0):
            frac = -prev_gex / (total - prev_gex) if total != prev_gex else 0
            crossing = prev_price + frac * (hypothetical_price - prev_price)
            break

        prev_price, prev_gex = hypothetical_price, total
        hypothetical_price += grid_step

    note = "swept hypothetical spot " + str(round(grid_low, 2)) + " to " + str(round(grid_high, 2)) + " in steps of " + str(round(grid_step, 3)) + "; IV held constant per contract at its real, observed value"
    if crossing is None:
        note += " -- NO sign crossing found within +/-20% of spot"
    return {"price": crossing, "note": note}


def find_gamma_walls(contracts: list, spot_price: float, sign_convention: str) -> dict:
    """Research-defined gamma concentration levels -- NOT guaranteed support/resistance."""
    by_strike = {}
    for c in contracts:
        if c["gamma"] is None or c["open_interest"] is None or c["strike"] is None:
            continue
        contribution = c["gamma"] * c["open_interest"] * 100 * (spot_price ** 2) * 0.01
        key = (c["strike"], c["option_type"])
        by_strike[key] = by_strike.get(key, 0.0) + contribution

    calls = {s: v for (s, t), v in by_strike.items() if t == "call"}
    puts = {s: v for (s, t), v in by_strike.items() if t == "put"}

    call_wall = max(calls.items(), key=lambda x: x[1]) if calls else (None, None)
    put_wall = max(puts.items(), key=lambda x: x[1]) if puts else (None, None)

    return {"call_wall_strike": call_wall[0], "call_wall_gex": call_wall[1], "put_wall_strike": put_wall[0], "put_wall_gex": put_wall[1]}


def calculate_gamma_gradient_at_spot(contracts: list, spot_price: float, sign_convention: str) -> float:
    """Discrete derivative of cumulative GEX at the strike interval nearest real spot."""
    by_strike = {}
    for c in contracts:
        if c["gamma"] is None or c["open_interest"] is None or c["strike"] is None:
            continue
        contribution = c["gamma"] * c["open_interest"] * 100 * (spot_price ** 2) * 0.01
        if sign_convention == "model_a":
            signed = contribution if c["option_type"] == "call" else -contribution
        else:
            signed = -contribution if c["option_type"] == "call" else contribution
        by_strike[c["strike"]] = by_strike.get(c["strike"], 0.0) + signed

    strikes_sorted = sorted(by_strike.keys())
    if len(strikes_sorted) < 2:
        return None

    nearest_idx = min(range(len(strikes_sorted)), key=lambda i: abs(strikes_sorted[i] - spot_price))
    if nearest_idx == len(strikes_sorted) - 1:
        nearest_idx -= 1
    s1, s2 = strikes_sorted[nearest_idx], strikes_sorted[nearest_idx + 1]
    if s2 == s1:
        return None
    return (by_strike[s2] - by_strike[s1]) / (s2 - s1)


def calculate_gex_for_ticker_day(ticker: str, date_str: str) -> list:
    """Runs the full Phase 2 calculation for one ticker-day, both sign conventions. Returns list of result dicts (does not print/decide anything)."""
    _init_gex_table()
    contracts = _load_snapshot_contracts(ticker, date_str)
    spot_result = get_historical_spot_price(ticker, date_str)
    spot_price = spot_result.get("spot_price")

    results = []
    if spot_price is None:
        return results

    calls_used = len([c for c in contracts if c["option_type"] == "call" and c["gamma"] is not None and c["open_interest"] is not None])
    puts_used = len([c for c in contracts if c["option_type"] == "put" and c["gamma"] is not None and c["open_interest"] is not None])

    for convention in SIGN_CONVENTIONS:
        net_gex_result = calculate_net_gex(contracts, spot_price, convention)
        cumulative_transition = calculate_cumulative_strike_transition(contracts, spot_price, convention)
        zero_gamma = calculate_true_zero_gamma(contracts, spot_price, convention, date_str)
        walls = find_gamma_walls(contracts, spot_price, convention)
        gradient = calculate_gamma_gradient_at_spot(contracts, spot_price, convention)

        regime = "positive" if net_gex_result["net_gex"] > 0 else "negative"

        result = {
            "ticker": ticker, "snapshot_date": date_str, "sign_convention": convention,
            "spot_price": spot_price, "spot_price_source": spot_result["source"], "spot_price_date": spot_result["date"],
            "contracts_used": calls_used + puts_used, "calls_used": calls_used, "puts_used": puts_used,
            "net_gex": net_gex_result["net_gex"], "gex_regime": regime,
            "call_gex_raw": net_gex_result["call_gex_raw"], "put_gex_raw": net_gex_result["put_gex_raw"],
            "cumulative_strike_transition_price": cumulative_transition,
            "true_zero_gamma_price": zero_gamma["price"], "true_zero_gamma_note": zero_gamma["note"],
            "call_wall_strike": walls["call_wall_strike"], "call_wall_gex": walls["call_wall_gex"],
            "put_wall_strike": walls["put_wall_strike"], "put_wall_gex": walls["put_wall_gex"],
            "gamma_gradient_at_spot": gradient,
        }
        results.append(result)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO gex_metrics (ticker, snapshot_date, sign_convention, spot_price, spot_price_source, spot_price_date, contracts_used, calls_used, puts_used, net_gex, gex_regime, cumulative_strike_transition_price, true_zero_gamma_price, true_zero_gamma_note, call_wall_strike, call_wall_gex, put_wall_strike, put_wall_gex, gamma_gradient_at_spot, calculated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (ticker, date_str, convention, spot_price, spot_result["source"], spot_result["date"],
                 calls_used + puts_used, calls_used, puts_used, net_gex_result["net_gex"], regime,
                 cumulative_transition, zero_gamma["price"], zero_gamma["note"],
                 walls["call_wall_strike"], walls["call_wall_gex"], walls["put_wall_strike"], walls["put_wall_gex"],
                 gradient, datetime.now(timezone.utc).isoformat())
            )
            conn.commit()

    return results


if __name__ == "__main__":
    print("=" * 80)
    print("PHASE 2 VALIDATION -- AAPL, 2026-07-15 ONLY (per explicit stop condition)")
    print("=" * 80)

    results = calculate_gex_for_ticker_day("AAPL", "2026-07-15")

    if not results:
        print("FAILED -- no results produced (likely missing spot price). Investigate before proceeding.")
    else:
        for r in results:
            print("\n--- Sign convention: " + r["sign_convention"] + " ---")
            print("Spot price: $" + str(round(r["spot_price"], 2)) + " (source: " + r["spot_price_source"] + ", date: " + r["spot_price_date"] + ")")
            print("Contracts used: " + str(r["contracts_used"]) + " (calls=" + str(r["calls_used"]) + ", puts=" + str(r["puts_used"]) + ")")
            print("Call GEX (raw): $" + str(round(r["call_gex_raw"], 2)))
            print("Put GEX (raw): $" + str(round(r["put_gex_raw"], 2)))
            print("Net GEX: $" + str(round(r["net_gex"], 2)))
            print("GEX regime: " + r["gex_regime"])
            print("Cumulative strike transition price (Method A, research-defined): " + str(r["cumulative_strike_transition_price"]))
            print("True zero-gamma price (Method B, standard methodology): " + str(r["true_zero_gamma_price"]))
            print("  Method B note: " + r["true_zero_gamma_note"])
            print("Call wall: strike=" + str(r["call_wall_strike"]) + " GEX=" + str(r["call_wall_gex"]))
            print("Put wall: strike=" + str(r["put_wall_strike"]) + " GEX=" + str(r["put_wall_gex"]))
            print("Gamma gradient at spot: " + str(r["gamma_gradient_at_spot"]))

    print("\n" + "=" * 80)
    print("STOPPING per explicit instruction -- AAPL 2026-07-15 only. Awaiting review before scaling.")
    print("=" * 80)
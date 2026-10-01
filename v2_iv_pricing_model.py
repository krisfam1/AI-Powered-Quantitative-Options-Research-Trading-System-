from dotenv import load_dotenv
load_dotenv()

"""
Model V2 -- Historical EODHD Implied-Volatility Black-Scholes Pricing.

ISOLATED, VERSIONED research module. Does NOT modify or replace the
existing realized-volatility implementation (Model V1, unchanged in
options_backtest_engine.py). The ONLY intended difference from V1 is
the volatility input: V2 uses real, historical EODHD implied
volatility for the specific contract/snapshot date; V1 uses the
existing realized-volatility estimate.

Does not touch: strategy entry rules, entry score threshold, breakout
gate, GEX, ML, option-selection logic, exit rules, stop loss, take
profit, portfolio logic.

Handles unavailable near-target expirations HONESTLY: selects only
contracts that actually exist under the established selection rules
(closest real strike + DTE combination). Never fabricates a 14-DTE
contract when none exists. Logs target DTE vs. actual DTE for every
calculation.

TERMINOLOGY: this remains "Historical EOD Options Pricing Validation."
EODHD provides EOD-only historical option quotes -- this does NOT
establish what an intraday trade would have filled at the exact
5-minute entry/exit timestamp.
"""

import os
import sqlite3
import requests
from datetime import datetime, timezone, timedelta
from options_backtest_engine import black_scholes_price  # V1's formula, reused unchanged -- only the vol input differs

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
LOG_DB_PATH = "v2_pricing_log.db"

MODEL_VERSION = "V2_historical_IV"
RISK_FREE_RATE = 0.04  # same as V1, unchanged
DIVIDEND_ASSUMPTION = "not modeled (0%), same as V1 -- confirmed absent from black_scholes_price"


def _init_log_db():
    with sqlite3.connect(LOG_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS v2_pricing_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_version TEXT, ticker TEXT, signal_date TEXT, contract TEXT,
                option_type TEXT, target_strike REAL, real_strike REAL,
                expiration TEXT, target_dte INTEGER, actual_dte INTEGER,
                volatility_source TEXT, volatility_value REAL,
                underlying_price REAL, risk_free_rate REAL, dividend_assumption TEXT,
                calculated_price REAL, real_bid REAL, real_ask REAL, real_midpoint REAL,
                calculated_at TEXT
            )
        """)


def _select_real_contract(ticker, date_str, target_strike, option_type="call", target_dte=14):
    """Selects the real, existing contract closest to (target_strike, target_dte).
    Returns None if no valid contract exists on this date -- NEVER fabricates."""
    obs_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    params = {
        "filter[underlying_symbol]": ticker, "filter[tradetime_from]": date_str, "filter[tradetime_to]": date_str,
        "filter[exp_date_from]": obs_date.isoformat(), "filter[exp_date_to]": (obs_date + timedelta(days=45)).isoformat(),
        "api_token": EODHD_API_TOKEN, "page[limit]": 1000,
    }
    resp = requests.get(BASE_URL, params=params, timeout=90)
    resp.raise_for_status()
    records = resp.json().get("data", [])
    valid = []
    for r in records:
        a = r.get("attributes", {})
        if a.get("type") != option_type:
            continue
        parts = r.get("id", "").split("-", 1)
        if len(parts) != 2:
            continue
        try:
            id_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
        except ValueError:
            continue
        if id_date != obs_date or a.get("bid") is None or a.get("ask") is None or a.get("volatility") is None:
            continue
        exp_date = datetime.strptime(a["exp_date"], "%Y-%m-%d").date()
        a["_actual_dte"] = (exp_date - obs_date).days
        valid.append(a)
    if not valid:
        return None
    return min(valid, key=lambda a: abs(a["strike"] - target_strike) / target_strike + (abs(a["_actual_dte"] - target_dte) / target_dte) * 0.5)


def calculate_v2_price(ticker, signal_date, target_strike, underlying_price, option_type="call", target_dte=14):
    """
    The core V2 function. Selects a real historical contract, prices it
    using V1's UNCHANGED Black-Scholes formula but with real historical
    IV substituted for the volatility input, and logs every calculation
    comprehensively.

    Returns a dict with the calculated price and full metadata, or None
    if no valid real contract exists (never substitutes/fabricates).
    """
    _init_log_db()
    real_contract = _select_real_contract(ticker, signal_date, target_strike, option_type, target_dte)

    if real_contract is None:
        with sqlite3.connect(LOG_DB_PATH) as conn:
            conn.execute(
                "INSERT INTO v2_pricing_log (model_version, ticker, signal_date, contract, option_type, target_strike, target_dte, volatility_source, calculated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (MODEL_VERSION, ticker, signal_date, None, option_type, target_strike, target_dte, "UNAVAILABLE -- no real contract found, not fabricated", datetime.now(timezone.utc).isoformat())
            )
        return None

    real_iv = real_contract["volatility"]
    real_strike = real_contract["strike"]
    actual_dte = real_contract["_actual_dte"]

    calculated_price = black_scholes_price(underlying_price, real_strike, actual_dte, real_iv, RISK_FREE_RATE, option_type)

    with sqlite3.connect(LOG_DB_PATH) as conn:
        conn.execute(
            "INSERT INTO v2_pricing_log (model_version, ticker, signal_date, contract, option_type, target_strike, real_strike, expiration, target_dte, actual_dte, volatility_source, volatility_value, underlying_price, risk_free_rate, dividend_assumption, calculated_price, real_bid, real_ask, real_midpoint, calculated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (MODEL_VERSION, ticker, signal_date, real_contract["contract"], option_type, target_strike, real_strike,
             real_contract["exp_date"], target_dte, actual_dte, "EODHD_historical_IV", real_iv, underlying_price,
             RISK_FREE_RATE, DIVIDEND_ASSUMPTION, calculated_price, real_contract["bid"], real_contract["ask"],
             real_contract["midpoint"], datetime.now(timezone.utc).isoformat())
        )

    return {
        "model_version": MODEL_VERSION, "ticker": ticker, "signal_date": signal_date,
        "contract": real_contract["contract"], "real_strike": real_strike, "expiration": real_contract["exp_date"],
        "target_dte": target_dte, "actual_dte": actual_dte, "volatility_source": "EODHD_historical_IV",
        "volatility_value": real_iv, "underlying_price": underlying_price, "calculated_price": calculated_price,
        "real_bid": real_contract["bid"], "real_ask": real_contract["ask"], "real_midpoint": real_contract["midpoint"],
    }

def get_v2_entry_iv(ticker, signal_timestamp, target_strike, option_type="call", target_dte=14):
    """
    V2 Phase 1, entry-only: looks up real historical EODHD implied
    volatility for a signal at signal_timestamp, using the exact
    validated methodology from the 126-trade diagnostic:
    - Real trading calendar T-1 (never same-day, never future)
    - Authoritative record-ID snapshot-date rule (never tradetime)
    - Contract matched to target_strike + target_dte=14 (not the
      selected real contract's own strike/DTE -- matches the exact
      methodology that was mechanically reproduced at 8.8% median error)

    Returns {"historical_iv": ..., "contract": ..., "snapshot_date": ...}
    or None if no valid historical IV is available -- NEVER fabricates
    or substitutes a fallback value.
    """
    from gex_data_loader import get_previous_trading_day
    signal_date = signal_timestamp.date()
    t_minus_1 = get_previous_trading_day(signal_date, reference_ticker=ticker)

    real_contract = _select_real_contract(ticker, t_minus_1.isoformat(), target_strike, option_type, target_dte)
    if real_contract is None:
        return None

    return {
        "historical_iv": real_contract["volatility"],
        "contract": real_contract["contract"],
        "snapshot_date": t_minus_1.isoformat(),
        "real_strike": real_contract["strike"],
        "actual_dte": real_contract["_actual_dte"],
    }

def get_v2_checkpoint_iv(ticker, contract_symbol, exp_date_str, checkpoint_date):
    """
    Corrected V2 checkpoint/exit valuation: looks up the SAME contract's
    (fixed at entry, never re-selected) historical EODHD IV at the most
    recent valid snapshot strictly before checkpoint_date (T-1 real
    trading day). Uses the authoritative record-ID snapshot-date rule,
    never tradetime. Returns the IV value, or None if genuinely
    unavailable -- NEVER falls back to V1 vol, never interpolates,
    never fabricates.
    """
    from gex_data_loader import get_previous_trading_day
    t_minus_1 = get_previous_trading_day(checkpoint_date, reference_ticker=ticker)

    obs_date = t_minus_1
    date_str = obs_date.isoformat()
    params = {
        "filter[underlying_symbol]": ticker, "filter[tradetime_from]": date_str, "filter[tradetime_to]": date_str,
        "filter[exp_date_from]": exp_date_str, "filter[exp_date_to]": exp_date_str,
        "api_token": EODHD_API_TOKEN, "page[limit]": 1000,
    }
    import time
    resp = None
    for attempt in range(3):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=60)
            resp.raise_for_status()
            break
        except requests.exceptions.RequestException:
            if attempt == 2:
                raise
            time.sleep(2)

    records = resp.json().get("data", [])
    for r in records:
        a = r.get("attributes", {})
        if a.get("contract") != contract_symbol:
            continue
        parts = r.get("id", "").split("-", 1)
        if len(parts) != 2:
            continue
        try:
            id_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
        except ValueError:
            continue
        if id_date != obs_date:
            continue
        if a.get("volatility") is None:
            return None
        return {"iv": a["volatility"], "snapshot_date": date_str}
    return None
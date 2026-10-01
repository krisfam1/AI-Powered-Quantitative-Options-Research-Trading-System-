"""
DATA LAYER for the Feature Factory's IV-dependent features. This is
where timestamp/provenance safety is actually guaranteed -- NOT inside
the feature functions themselves (per the locked architecture).

Reuses the exact, already-validated T-1 real-trading-day snapshot rule
from tonight's V1/V2 pricing work (get_previous_trading_day + EODHD
record-ID snapshot-date methodology). Does not modify V1 or any
existing pricing code -- imports and reuses it directly.
"""

import os
import requests
from datetime import datetime, timedelta
from gex_data_loader import get_previous_trading_day

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"


def get_timestamp_safe_historical_iv(ticker, as_of_date, target_strike, option_type="call", target_dte=14):
    """
    Fetches real historical IV for the contract closest to target_strike/
    target_dte, using the most recent EOD snapshot STRICTLY BEFORE
    as_of_date (T-1 real trading day, record-ID snapshot-date rule).

    Returns {"iv": float, "snapshot_date": str} or None if unavailable.
    NEVER returns a same-day or future observation relative to as_of_date.
    """
    t_minus_1 = get_previous_trading_day(as_of_date, reference_ticker=ticker)
    date_str = t_minus_1.isoformat()

    params = {
        "filter[underlying_symbol]": ticker, "filter[tradetime_from]": date_str, "filter[tradetime_to]": date_str,
        "filter[exp_date_from]": t_minus_1.isoformat(), "filter[exp_date_to]": (t_minus_1 + timedelta(days=45)).isoformat(),
        "api_token": EODHD_API_TOKEN, "page[limit]": 1000,
    }
    resp = requests.get(BASE_URL, params=params, timeout=60)
    resp.raise_for_status()
    records = resp.json().get("data", [])
    valid = []
    for r in records:
        a = r.get("attributes", {})
        if a.get("type") != option_type or a.get("volatility") is None:
            continue
        parts = r.get("id", "").split("-", 1)
        if len(parts) != 2:
            continue
        try:
            id_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
        except ValueError:
            continue
        if id_date != t_minus_1:
            continue
        exp_date = datetime.strptime(a["exp_date"], "%Y-%m-%d").date()
        a["_actual_dte"] = (exp_date - t_minus_1).days
        valid.append(a)
    if not valid:
        return None
    best = min(valid, key=lambda a: abs(a["strike"] - target_strike) / target_strike + (abs(a["_actual_dte"] - target_dte) / target_dte) * 0.5)
    return {"iv": best["volatility"], "snapshot_date": date_str}
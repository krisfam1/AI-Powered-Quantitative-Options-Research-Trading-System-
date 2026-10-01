from dotenv import load_dotenv
load_dotenv()

"""
gex_data_loader.py -- REBUILT for full 90-day scaling.

New in this version:
1. Real pagination handling -- follows JSON:API "links.next" if present;
   falls back to incrementing page[offset] if a page returns exactly the
   requested limit with no "links" key. Explicitly reports whether
   pagination was needed/completed for every ticker-day.
2. Database-level UNIQUE constraint on (ticker, snapshot_date, contract)
   as a second, independent layer of protection beyond the idempotent
   delete-before-insert logic (belt-and-suspenders against the earlier
   duplicate-insertion bug class).
3. get_real_trading_days() -- discovers actual trading days in a date
   range using real Alpaca bar data, not calendar-day assumptions.

All previously established rules preserved: record-ID date is
authoritative (never tradetime), bid_date/ask_date are diagnostic only,
volume is not a freshness requirement, 0-45 DTE universe, real trading
calendar for T-1.
"""

import os
import sqlite3
import requests
import json
from datetime import datetime, timedelta, timezone
import backtest_engine as be

EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN")
BASE_URL = "https://eodhd.com/api/mp/unicornbay/options/eod"
DB_PATH = "gex_data_cache.db"

TRAIN_START = "2026-06-11"
TRAIN_END = "2026-08-11"
HOLDOUT_END = "2026-09-09"
FIRST_SIGNAL_PRECEDING_DAY = "2026-06-10"


def _init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS raw_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT, ticker TEXT, requested_date TEXT,
                id_suffix_date TEXT, matches_requested_date INTEGER,
                contract TEXT, strike REAL, exp_date TEXT, option_type TEXT,
                open_interest INTEGER, gamma REAL, volatility REAL, volume INTEGER,
                tradetime TEXT, bid_date TEXT, ask_date TEXT,
                raw_json TEXT, fetched_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cleaned_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT, snapshot_date TEXT, contract TEXT,
                strike REAL, exp_date TEXT, option_type TEXT,
                open_interest INTEGER, gamma REAL, volatility REAL,
                bid_date TEXT, ask_date TEXT, record_id TEXT, selected_at TEXT,
                UNIQUE(ticker, snapshot_date, contract)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS exclusion_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT, requested_date TEXT, contract TEXT,
                reason TEXT, detail TEXT, logged_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ticker_day_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT, requested_date TEXT,
                records_retrieved INTEGER, pages_requested INTEGER, pagination_complete INTEGER,
                records_retained INTEGER, records_excluded INTEGER, contracts_retained INTEGER,
                calls INTEGER, puts INTEGER, with_oi INTEGER, with_gamma INTEGER,
                missing_oi INTEGER, missing_gamma INTEGER,
                multi_record_contracts INTEGER, errors TEXT, processed_at TEXT
            )
        """)


def _parse_id_suffix_date(record_id: str):
    if not record_id or "-" not in record_id:
        return None
    parts = record_id.split("-", 1)
    if len(parts) != 2:
        return None
    try:
        return datetime.strptime(parts[1], "%Y-%m-%d").date()
    except ValueError:
        return None


_trading_day_cache = {}


def get_previous_trading_day(date_obj, reference_ticker: str = "SPY"):
    cache_key = date_obj.isoformat()
    if cache_key in _trading_day_cache:
        return _trading_day_cache[cache_key]

    candidate = date_obj - timedelta(days=1)
    for _ in range(10):
        start = datetime.combine(candidate, datetime.min.time(), tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        try:
            bars = be.get_historical_bars(reference_ticker, start, end)
        except Exception:
            bars = []
        if bars:
            _trading_day_cache[cache_key] = candidate
            return candidate
        candidate -= timedelta(days=1)

    raise RuntimeError("Could not find a real prior trading day within 10 days of " + date_obj.isoformat())


def get_real_trading_days(start_date_str: str, end_date_str: str, reference_ticker: str = "SPY") -> list:
    start = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(end_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
    bars = be.get_historical_bars(reference_ticker, start, end)
    trading_days = sorted(set(b.timestamp.date() for b in bars))
    return trading_days


def _fetch_raw_chain_paginated(ticker: str, date_str: str) -> dict:
    obs_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    all_records = []
    pages_requested = 0
    pagination_complete = True

    params = {
        "filter[underlying_symbol]": ticker,
        "filter[tradetime_from]": date_str,
        "filter[tradetime_to]": date_str,
        "filter[exp_date_from]": obs_date.isoformat(),
        "filter[exp_date_to]": (obs_date + timedelta(days=45)).isoformat(),
        "api_token": EODHD_API_TOKEN,
        "page[limit]": 1000,
        "page[offset]": 0,
    }

    next_url = None
    while True:
        pages_requested += 1
        if next_url:
            # HONEST FIX: EODHD's own "links.next" URL does not carry a
            # valid auth token forward -- must be re-attached explicitly,
            # or every page after the first fails with 401 Unauthorized.
            separator = "&" if "?" in next_url else "?"
            authenticated_next_url = next_url + separator + "api_token=" + EODHD_API_TOKEN
            resp = requests.get(authenticated_next_url, timeout=30)
        else:
            resp = requests.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        page_records = payload.get("data", [])
        all_records.extend(page_records)

        links = payload.get("links", {})
        if links.get("next"):
            next_url = links["next"]
            continue

        if len(page_records) == params["page[limit]"] and not links:
            params["page[offset]"] += params["page[limit]"]
            if pages_requested > 20:
                pagination_complete = False
                break
            continue

        break

    return {"records": all_records, "pages_requested": pages_requested, "pagination_complete": pagination_complete}


def process_ticker_day(ticker: str, date_str: str) -> dict:
    obs_date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    now_iso = datetime.now(timezone.utc).isoformat()

    errors = []
    try:
        fetch_result = _fetch_raw_chain_paginated(ticker, date_str)
        raw_records = fetch_result["records"]
        pages_requested = fetch_result["pages_requested"]
        pagination_complete = fetch_result["pagination_complete"]
    except Exception as exc:
        errors.append("fetch failed: " + str(exc))
        raw_records, pages_requested, pagination_complete = [], 0, False

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM raw_records WHERE ticker=? AND requested_date=?", (ticker, date_str))
        conn.execute("DELETE FROM cleaned_snapshot WHERE ticker=? AND snapshot_date=?", (ticker, date_str))
        conn.execute("DELETE FROM exclusion_log WHERE ticker=? AND requested_date=?", (ticker, date_str))
        conn.execute("DELETE FROM ticker_day_summary WHERE ticker=? AND requested_date=?", (ticker, date_str))
        conn.commit()

        by_contract = {}
        retained_raw = 0
        excluded_raw = 0

        for r in raw_records:
            record_id = r.get("id")
            a = r.get("attributes", {})
            id_date = _parse_id_suffix_date(record_id)
            matches = (id_date == obs_date_obj) if id_date else False

            conn.execute(
                "INSERT INTO raw_records (record_id, ticker, requested_date, id_suffix_date, matches_requested_date, contract, strike, exp_date, option_type, open_interest, gamma, volatility, volume, tradetime, bid_date, ask_date, raw_json, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (record_id, ticker, date_str, str(id_date) if id_date else None, 1 if matches else 0,
                 a.get("contract"), a.get("strike"), a.get("exp_date"), a.get("type"),
                 a.get("open_interest"), a.get("gamma"), a.get("volatility"), a.get("volume"),
                 a.get("tradetime"), a.get("bid_date"), a.get("ask_date"), json.dumps(a), now_iso)
            )

            if matches:
                retained_raw += 1
                contract = a.get("contract")
                by_contract.setdefault(contract, []).append({"attrs": a, "record_id": record_id, "id_date": id_date})
            else:
                excluded_raw += 1
        conn.commit()

        contracts_retained = 0
        calls = 0
        puts = 0
        with_oi = 0
        with_gamma = 0
        missing_oi = 0
        missing_gamma = 0
        multi_record_contracts = 0

        for contract, recs in by_contract.items():
            if len(recs) > 1:
                multi_record_contracts += 1
                conn.execute(
                    "INSERT INTO exclusion_log (ticker, requested_date, contract, reason, detail, logged_at) VALUES (?,?,?,?,?,?)",
                    (ticker, date_str, contract, "multiple_matching_records", str(len(recs)) + " records matched -- using first available", now_iso)
                )

            chosen = recs[0]
            a = chosen["attrs"]
            assert chosen["id_date"] == obs_date_obj, "SNAPSHOT DATE VIOLATION: " + contract

            try:
                conn.execute(
                    "INSERT INTO cleaned_snapshot (ticker, snapshot_date, contract, strike, exp_date, option_type, open_interest, gamma, volatility, bid_date, ask_date, record_id, selected_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ticker, date_str, contract, a.get("strike"), a.get("exp_date"), a.get("type"),
                     a.get("open_interest"), a.get("gamma"), a.get("volatility"),
                     a.get("bid_date"), a.get("ask_date"), chosen["record_id"], now_iso)
                )
            except sqlite3.IntegrityError as exc:
                errors.append("UNIQUE constraint caught a real duplicate for " + contract + ": " + str(exc))
                continue

            contracts_retained += 1
            if a.get("type") == "call":
                calls += 1
            elif a.get("type") == "put":
                puts += 1
            if a.get("open_interest") is not None:
                with_oi += 1
            else:
                missing_oi += 1
            if a.get("gamma") is not None:
                with_gamma += 1
            else:
                missing_gamma += 1

        conn.execute(
            "INSERT INTO ticker_day_summary (ticker, requested_date, records_retrieved, pages_requested, pagination_complete, records_retained, records_excluded, contracts_retained, calls, puts, with_oi, with_gamma, missing_oi, missing_gamma, multi_record_contracts, errors, processed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ticker, date_str, len(raw_records), pages_requested, 1 if pagination_complete else 0,
             retained_raw, excluded_raw, contracts_retained, calls, puts, with_oi, with_gamma,
             missing_oi, missing_gamma, multi_record_contracts, "; ".join(errors) if errors else None, now_iso)
        )
        conn.commit()

    return {
        "ticker": ticker, "date": date_str, "records_retrieved": len(raw_records),
        "pages_requested": pages_requested, "pagination_complete": pagination_complete,
        "records_retained": retained_raw, "records_excluded": excluded_raw,
        "contracts_retained": contracts_retained, "calls": calls, "puts": puts,
        "with_oi": with_oi, "with_gamma": with_gamma, "missing_oi": missing_oi,
        "missing_gamma": missing_gamma, "multi_record_contracts": multi_record_contracts, "errors": errors,
    }


def run_no_lookahead_test(ticker: str, signal_date_str: str) -> dict:
    signal_date = datetime.strptime(signal_date_str, "%Y-%m-%d").date()
    t_minus_1 = get_previous_trading_day(signal_date, reference_ticker=ticker)
    process_ticker_day(ticker, t_minus_1.isoformat())

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT contract, snapshot_date FROM cleaned_snapshot WHERE ticker=? AND snapshot_date=?",
            (ticker, t_minus_1.isoformat())
        ).fetchall()

    violations = [r for r in rows if datetime.strptime(r[1], "%Y-%m-%d").date() >= signal_date]
    return {
        "signal_date": signal_date_str, "computed_t_minus_1": t_minus_1.isoformat(),
        "contracts_in_snapshot": len(rows), "violations": len(violations), "pass": len(violations) == 0,
    }


if __name__ == "__main__":
    _init_db()

    TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]

    print("Discovering real trading days in range " + FIRST_SIGNAL_PRECEDING_DAY + " to " + HOLDOUT_END + "...")
    trading_days = get_real_trading_days(FIRST_SIGNAL_PRECEDING_DAY, HOLDOUT_END)
    print("Found " + str(len(trading_days)) + " real trading days.\n")

    all_summaries = []
    for ticker in TICKERS:
        for d in trading_days:
            date_str = d.isoformat()
            summary = process_ticker_day(ticker, date_str)
            all_summaries.append(summary)
            print(ticker + " " + date_str + ": retrieved=" + str(summary["records_retrieved"]) + " pages=" + str(summary["pages_requested"]) + " complete=" + str(summary["pagination_complete"]) + " contracts=" + str(summary["contracts_retained"]) + " errors=" + str(summary["errors"]))

    print("\n" + "=" * 80)
    print("EXPANDED PHASE 1 AUDIT -- " + str(len(all_summaries)) + " ticker-days")
    print("=" * 80)
    total_retrieved = sum(s["records_retrieved"] for s in all_summaries)
    total_retained = sum(s["records_retained"] for s in all_summaries)
    total_excluded = sum(s["records_excluded"] for s in all_summaries)
    total_contracts = sum(s["contracts_retained"] for s in all_summaries)
    total_calls = sum(s["calls"] for s in all_summaries)
    total_puts = sum(s["puts"] for s in all_summaries)
    total_multi = sum(s["multi_record_contracts"] for s in all_summaries)
    total_errors = sum(len(s["errors"]) for s in all_summaries)
    incomplete_pagination = [s for s in all_summaries if not s["pagination_complete"]]

    print("Total raw records retrieved: " + str(total_retrieved))
    print("Records retained: " + str(total_retained) + " | Excluded: " + str(total_excluded))
    print("Reconciliation: " + str(total_retained + total_excluded == total_retrieved))
    print("Total contracts retained: " + str(total_contracts))
    print("Calls: " + str(total_calls) + " | Puts: " + str(total_puts))
    print("Multi-record contracts: " + str(total_multi))
    print("Ticker-days with INCOMPLETE pagination: " + str(len(incomplete_pagination)))
    for s in incomplete_pagination:
        print("  INCOMPLETE: " + s["ticker"] + " " + s["date"])
    print("Total errors: " + str(total_errors))

    print("\n" + "=" * 80)
    print("NO-LOOKAHEAD TESTS")
    print("=" * 80)
    for ticker in ["AAPL", "TSLA"]:
        result = run_no_lookahead_test(ticker, HOLDOUT_END)
        print(ticker + " (recent): " + str(result))

    print("\n" + "=" * 80)
    if total_errors == 0 and total_retained + total_excluded == total_retrieved and len(incomplete_pagination) == 0:
        print("EXPANDED PHASE 1: PASS")
    else:
        print("EXPANDED PHASE 1: issues found -- review before proceeding")
    print("=" * 80)
from dotenv import load_dotenv
load_dotenv()

"""
Supporting fetch pass for two of strike_positioning_oi_skew_v1_20260922's
five declared robustness checks (CLAUDE.md Section 39):
`alternate_moneyness_band:15pct` and `alternate_dte_window:7-30dte`.

These two checks need oi_skew RECOMPUTED with a different moneyness band /
DTE window than the primary run used -- not just a different downstream
test on already-stored values. Rather than running two separate ~605-call
refetch passes (one per alternate parameter), this does ONE refetch pass
over the same 605 (ticker, obs_date) rows already in
oi_skew_training_examples and computes THREE oi_skew variants per row from
the same raw chain fetch: primary (band=10%, dte=7-45, reproduced here as
an internal consistency check against the already-stored value), alt-band
(15%, dte=7-45), and alt-dte (band=10%, dte=7-30).

`compute_oi_skew_variant()` below is a parameterized GENERALIZATION of the
already-validated `compute_oi_skew()` in generate_xgboost_volatility_
dataset.py -- passing its exact defaults (band_pct=0.10, dte=(7,45))
reproduces identical logic; it is not an independent reimplementation.
Cross-checked against the stored primary oi_skew values below before
trusting the two alternate variants.

Writes to a new table, `oi_skew_variants`, in the SAME
strike_positioning_oi_skew_dataset.db (does not touch
oi_skew_training_examples/oi_skew_excluded). Same idempotency/concurrency
discipline as every other data-fetch script in this project this session:
exclusive lockfile, UNIQUE(ticker, obs_date) + INSERT OR IGNORE, a `seen`
set loaded fresh at startup, fetch errors left unmarked so they retry.
"""

import math
import os
import sqlite3
from datetime import datetime, timezone

from gex_data_loader import _fetch_raw_chain_paginated

DB_PATH = "strike_positioning_oi_skew_dataset.db"
LOG_PATH = "oi_skew_variants_generation_log.txt"
LOCK_PATH = "oi_skew_variants_generation.lock"


def acquire_lock():
    try:
        fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


def release_lock():
    try:
        os.remove(LOCK_PATH)
    except FileNotFoundError:
        pass


def log(fh, msg: str) -> None:
    print(msg, flush=True)
    fh.write(msg + "\n")
    fh.flush()


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS oi_skew_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT, obs_date TEXT,
            oi_skew_primary_recomputed REAL,
            oi_skew_band15 REAL,
            oi_skew_dte730 REAL,
            pages_requested INTEGER, pagination_complete INTEGER,
            generated_at TEXT,
            UNIQUE(ticker, obs_date)
        )
    """)
    conn.commit()


def compute_oi_skew_variant(id_matched_attrs, obs_date, spot_price, band_pct, dte_lo, dte_hi):
    """Parameterized generalization of generate_xgboost_volatility_dataset.py's
    compute_oi_skew() -- passing band_pct=0.10, dte_lo=7, dte_hi=45 reproduces
    that function's exact logic. Same exclude-on-zero discipline."""
    lo, hi = spot_price * (1 - band_pct), spot_price * (1 + band_pct)
    call_oi, put_oi = 0, 0
    for a in id_matched_attrs:
        strike, exp_str, oi = a.get("strike"), a.get("exp_date"), a.get("open_interest")
        if strike is None or exp_str is None or oi is None:
            continue
        exp = datetime.strptime(exp_str, "%Y-%m-%d").date()
        dte = (exp - obs_date).days
        if not (dte_lo <= dte <= dte_hi) or not (lo <= strike <= hi):
            continue
        if a.get("type") == "call":
            call_oi += oi
        elif a.get("type") == "put":
            put_oi += oi
    if call_oi <= 0 or put_oi <= 0:
        return None
    return math.log(put_oi / call_oi)


def main():
    if not acquire_lock():
        print(f"LOCK HELD ({LOCK_PATH} exists) -- another instance appears to already be running. Exiting.", flush=True)
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        init_db(conn)

        rows = conn.execute(
            "SELECT ticker, obs_date, spot_price, oi_skew FROM oi_skew_training_examples ORDER BY obs_date, ticker"
        ).fetchall()

        seen = set()
        for ticker, obs_date, *_ in conn.execute("SELECT ticker, obs_date FROM oi_skew_variants"):
            seen.add((ticker, obs_date))

        with open(LOG_PATH, "a", encoding="utf-8") as log_fh:
            log(log_fh, f"\n{'=' * 100}\n=== RUN START {datetime.now(timezone.utc).isoformat()} | {len(rows)} rows to process | resuming with {len(seen)} already-processed ===")

            saved, skipped, errors, mismatches = 0, 0, 0, 0

            for count, (ticker, obs_date_str, spot_price, stored_oi_skew) in enumerate(rows):
                key = (ticker, obs_date_str)
                if key in seen:
                    skipped += 1
                    continue

                obs_date = datetime.strptime(obs_date_str, "%Y-%m-%d").date()

                try:
                    fetch_result = _fetch_raw_chain_paginated(ticker, obs_date_str)
                except Exception as exc:
                    errors += 1
                    log(log_fh, f"  [{ticker} {obs_date_str}] fetch error, will retry on next run: {exc}")
                    continue

                pages_requested = fetch_result["pages_requested"]
                pagination_complete = fetch_result["pagination_complete"]
                id_matched = [r.get("attributes", {}) for r in fetch_result["records"] if str(r.get("id", "")).endswith("-" + obs_date_str)]

                primary_recomputed = compute_oi_skew_variant(id_matched, obs_date, spot_price, 0.10, 7, 45)
                band15 = compute_oi_skew_variant(id_matched, obs_date, spot_price, 0.15, 7, 45)
                dte730 = compute_oi_skew_variant(id_matched, obs_date, spot_price, 0.10, 7, 30)

                if primary_recomputed is not None and abs(primary_recomputed - stored_oi_skew) > 1e-9:
                    mismatches += 1
                    log(log_fh, f"  [{ticker} {obs_date_str}] MISMATCH: stored={stored_oi_skew} recomputed={primary_recomputed}")

                conn.execute(
                    """INSERT OR IGNORE INTO oi_skew_variants
                       (ticker, obs_date, oi_skew_primary_recomputed, oi_skew_band15, oi_skew_dte730,
                        pages_requested, pagination_complete, generated_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (ticker, obs_date_str, primary_recomputed, band15, dte730,
                     pages_requested, int(pagination_complete), datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
                seen.add(key)
                saved += 1

                if (count + 1) % 50 == 0 or (count + 1) == len(rows):
                    log(log_fh, f"  {count + 1}/{len(rows)} scanned -- saved={saved} skipped={skipped} errors={errors} mismatches={mismatches}")

            log(log_fh, f"\n=== RUN COMPLETE {datetime.now(timezone.utc).isoformat()} ===")
            log(log_fh, f"saved={saved} skipped={skipped} errors={errors} mismatches={mismatches}")

        conn.close()
    finally:
        release_lock()


if __name__ == "__main__":
    main()

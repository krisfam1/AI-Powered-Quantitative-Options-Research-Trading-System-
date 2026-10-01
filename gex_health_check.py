from dotenv import load_dotenv
load_dotenv()

"""
READ-ONLY health check of the GEX data pipeline. Only SELECT queries
are used throughout -- zero INSERT/UPDATE/DELETE, confirmed by
inspection. Safe to run at any time without affecting any data.
"""

import sqlite3
import os
from datetime import datetime, date

print("=" * 100)
print("GEX PIPELINE HEALTH CHECK (READ-ONLY)")
print("=" * 100)
print("Run at: " + datetime.now().isoformat())

# ============================================================
# PART 1: Historical GEX database (gex_data_cache.db)
# ============================================================
print("\n" + "=" * 100)
print("PART 1: HISTORICAL GEX DATABASE (gex_data_cache.db)")
print("=" * 100)

if not os.path.exists("gex_data_cache.db"):
    print("File not found -- skipping.")
else:
    with sqlite3.connect("gex_data_cache.db") as conn:
        conn.row_factory = sqlite3.Row
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print("Tables found: " + str(tables))

        for table in tables:
            count = conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
            print("\n--- " + table + " ---")
            print("Row count: " + str(count))

        if "cleaned_snapshot" in tables:
            date_range = conn.execute("SELECT MIN(snapshot_date), MAX(snapshot_date) FROM cleaned_snapshot").fetchone()
            print("\ncleaned_snapshot date range: " + str(date_range[0]) + " to " + str(date_range[1]))
            tickers = [r[0] for r in conn.execute("SELECT DISTINCT ticker FROM cleaned_snapshot ORDER BY ticker").fetchall()]
            print("Tickers present: " + str(tickers))
            ticker_day_count = conn.execute("SELECT COUNT(DISTINCT ticker || snapshot_date) FROM cleaned_snapshot").fetchone()[0]
            print("Distinct ticker-days: " + str(ticker_day_count))

            # Duplicate check
            dupes = conn.execute("""
                SELECT ticker, snapshot_date, contract, COUNT(*) as cnt FROM cleaned_snapshot
                GROUP BY ticker, snapshot_date, contract HAVING cnt > 1
            """).fetchall()
            print("Duplicate (ticker, date, contract) rows: " + str(len(dupes)))

            missing_oi = conn.execute("SELECT COUNT(*) FROM cleaned_snapshot WHERE open_interest IS NULL").fetchone()[0]
            missing_gamma = conn.execute("SELECT COUNT(*) FROM cleaned_snapshot WHERE gamma IS NULL").fetchone()[0]
            print("Rows with missing OI: " + str(missing_oi) + " | missing gamma: " + str(missing_gamma))

        if "gex_metrics" in tables:
            gex_count = conn.execute("SELECT COUNT(*) FROM gex_metrics").fetchone()[0]
            print("\ngex_metrics row count: " + str(gex_count))
            conventions = [r[0] for r in conn.execute("SELECT DISTINCT sign_convention FROM gex_metrics").fetchall()]
            print("Sign conventions present: " + str(conventions))
            regime_dist = conn.execute("SELECT gex_regime, COUNT(*) FROM gex_metrics WHERE sign_convention='model_a' GROUP BY gex_regime").fetchall()
            print("Regime distribution (model_a): " + str(dict(regime_dist)))

# ============================================================
# PART 2: Prospective (live, forward-only) pipeline
# ============================================================
print("\n" + "=" * 100)
print("PART 2: PROSPECTIVE PIPELINE (prospective_gex_validation.db)")
print("=" * 100)

if not os.path.exists("prospective_gex_validation.db"):
    print("File not found -- skipping.")
else:
    with sqlite3.connect("prospective_gex_validation.db") as conn:
        conn.row_factory = sqlite3.Row
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print("Tables found: " + str(tables))

        if "raw_signals" in tables:
            total = conn.execute("SELECT COUNT(*) FROM raw_signals").fetchone()[0]
            print("\nTotal signals logged: " + str(total))

            date_range = conn.execute("SELECT MIN(trading_date), MAX(trading_date) FROM raw_signals").fetchone()
            print("Date range: " + str(date_range[0]) + " to " + str(date_range[1]))

            days_covered = conn.execute("SELECT COUNT(DISTINCT trading_date) FROM raw_signals").fetchone()[0]
            print("Distinct trading days with logged signals: " + str(days_covered))

            by_ticker = conn.execute("SELECT ticker, COUNT(*) FROM raw_signals GROUP BY ticker ORDER BY ticker").fetchall()
            print("Signals by ticker: " + str(dict(by_ticker)))

            backfilled = conn.execute("SELECT COUNT(*) FROM raw_signals WHERE returns_backfilled = 1").fetchone()[0]
            pending = conn.execute("SELECT COUNT(*) FROM raw_signals WHERE returns_backfilled = 0").fetchone()[0]
            print("Forward-returns backfilled: " + str(backfilled) + " | still pending: " + str(pending))

            skipped_gex = conn.execute("SELECT COUNT(*) FROM raw_signals WHERE gex_available = 0").fetchone()[0]
            print("Signals skipped (GEX unavailable at logging time): " + str(skipped_gex))

            # Duplicate check
            dupes = conn.execute("""
                SELECT ticker, signal_timestamp, COUNT(*) as cnt FROM raw_signals
                GROUP BY ticker, signal_timestamp HAVING cnt > 1
            """).fetchall()
            print("Duplicate (ticker, signal_timestamp) records: " + str(len(dupes)))

            # Most recent entries
            recent = conn.execute("SELECT ticker, trading_date, entry_score, gex_snapshot_date FROM raw_signals ORDER BY logged_at DESC LIMIT 5").fetchall()
            print("\nMost recently logged signals:")
            for r in recent:
                print("  " + r["ticker"] + " " + r["trading_date"] + " score=" + str(r["entry_score"]) + " gex_snapshot=" + str(r["gex_snapshot_date"]))

            # Staleness check -- how long since last collection run?
            last_logged = conn.execute("SELECT MAX(logged_at) FROM raw_signals").fetchone()[0]
            if last_logged:
                last_dt = datetime.fromisoformat(last_logged)
                days_since = (datetime.now(last_dt.tzinfo) - last_dt).days
                print("\nMost recent collection run: " + str(last_logged) + " (" + str(days_since) + " days ago)")
                if days_since > 3:
                    print("  NOTE: pipeline may not have been run recently -- consider running daily_collection_run.py")

print("\n" + "=" * 100)
print("HEALTH CHECK COMPLETE -- READ-ONLY, NO DATA MODIFIED")
print("=" * 100)
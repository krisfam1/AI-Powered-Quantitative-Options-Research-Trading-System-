from dotenv import load_dotenv
load_dotenv()

import sqlite3
from datetime import datetime, timezone, timedelta
from options_confluence_modifier import calculate_size_modifier
from gamma_regime import calculate_net_gamma_regime
import backtest_engine as be


DB_PATH = "gamma_forward_test.db"


def init_forward_test_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS forward_test_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                logged_at TEXT,
                ticker TEXT,
                price_at_log REAL,
                modifier REAL,
                reasons TEXT,
                gamma_regime TEXT
            )
        """)


def log_today_modifiers(tickers: list[str]):
    init_forward_test_db()
    now = datetime.now(timezone.utc)

    with sqlite3.connect(DB_PATH) as conn:
        for ticker in tickers:
            try:
                bars = be.get_historical_bars(ticker, now - timedelta(days=5), now)
                if not bars:
                    print(f"  {ticker}: no bars available, skipping")
                    continue
                current_price = float(bars[-1].close)

                result = calculate_size_modifier(ticker, current_price, direction="long")
                try:
                    regime_result = calculate_net_gamma_regime(ticker, current_price)
                    regime = regime_result["regime"]
                except Exception:
                    regime = "unknown"

                conn.execute(
                    "INSERT INTO forward_test_log (logged_at, ticker, price_at_log, modifier, reasons, gamma_regime) VALUES (?, ?, ?, ?, ?, ?)",
                    (now.isoformat(), ticker, current_price, result["modifier"], "; ".join(result["reasons"]), regime)
                )
                print(f"  {ticker}: price=${current_price:.2f}, modifier={result['modifier']}x — {'; '.join(result['reasons'])}")
            except Exception as exc:
                print(f"  {ticker}: error — {exc}")

        conn.commit()


if __name__ == "__main__":
    from main import LIVE_TICKERS
    tickers = LIVE_TICKERS
    print(f"Logging gamma/charm modifiers for {', '.join(tickers)}...")
    log_today_modifiers(tickers)
    print("\nDone. Run this again on future days to build a forward-test dataset.")
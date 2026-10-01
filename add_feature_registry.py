import sqlite3
import json
from datetime import datetime, timezone

DB_PATH = "research_database.db"

with sqlite3.connect(DB_PATH) as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feature_registry (
            feature_name TEXT,
            version TEXT,
            module TEXT,
            formula_description TEXT,
            input_requirements TEXT,
            lookback TEXT,
            output_type TEXT,
            output_units TEXT,
            added_at TEXT,
            deprecated_at TEXT,
            lookahead_safe INTEGER,
            external_data_required INTEGER,
            input_provenance TEXT,
            runnable INTEGER DEFAULT 1,
            PRIMARY KEY (feature_name, version)
        )
    """)
    conn.commit()
print("feature_registry table created.\n")

NOW = datetime.now(timezone.utc).isoformat()

FEATURES = [
    ("past_return_n", "1.0", "underlying", "(close[index] - close[index-n]) / close[index-n]",
     "bars, index, n(default=20)", "n bars", "continuous", "decimal_return", NOW, None, 1, 0, None, 1),
    ("breakout_strength", "1.0", "underlying", "(close[index] - max(high[index-lookback:index])) / max(high[index-lookback:index])",
     "bars, index, lookback(default=20)", "20 bars", "continuous", "decimal", NOW, None, 1, 0, None, 1),
    ("atr_normalized", "1.0", "underlying", "14-period ATR / close[index]",
     "bars, index, period(default=14)", "period+1 bars", "continuous", "decimal_pct_of_price", NOW, None, 1, 0, None, 1),

    ("dte_at_index", "1.0", "options", "(expiration_date - bar_date(index)).days",
     "bars, index, expiration_date", "none", "integer", "days", NOW, None, 1, 0, None, 1),
    ("delta_at_index", "1.0", "options", "calculate_delta(spot, strike, dte, vol)",
     "bars, index, strike, dte, vol, vol_source(REQUIRED)", "none", "continuous", "delta_-1_to_1", NOW, None, 1, 0, "vol_source required: historical_iv OR realized_vol, no default", 1),
    ("iv_vs_realized_vol", "1.0", "options", "(historical_iv - realized_vol) / realized_vol",
     "bars, index, historical_iv(pre-fetched)", "per calculate_historical_volatility", "continuous", "decimal_ratio", NOW, None, 1, 1, "historical_iv snapshot date must be recorded", 1),
    ("iv_percentile", "1.0", "options", "rank of current_iv within historical_iv_series trailing window",
     "current_iv, historical_iv_series(pre-filtered), lookback(default=252)", "252 obs", "continuous", "percentile_0_to_1", NOW, None, 1, 1, "historical_iv_series must be timestamp-filtered by data layer", 1),

    ("spy_trend_state", "1.0", "regime", "wraps get_daily_regime('SPY', as_of_timestamp)",
     "as_of_timestamp", "50-day (internal to get_daily_regime)", "categorical", "bullish/bearish/neutral", NOW, None, 1, 0, None, 1),
    ("vix_regime", "1.0", "regime", "categorical bucket from supplied VIX level",
     "vix_level, low_threshold(15), high_threshold(25)", "none", "categorical", "low/normal/high", NOW, None, 1, 1, None, 0),
    ("relative_strength_vs_spy", "1.0", "regime", "past_return_n(ticker) - past_return_n(SPY), matched by TIMESTAMP not index",
     "ticker_bars, spy_bars, index, n(default=20)", "n bars on both series", "continuous", "decimal", NOW, None, 1, 0, None, 1),
    ("vwap_distance", "1.0", "regime", "(close[index] - session_VWAP[index]) / session_VWAP[index]",
     "bars, index", "current trading day only", "continuous", "decimal_pct", NOW, None, 1, 0, None, 1),
]

with sqlite3.connect(DB_PATH) as conn:
    for f in FEATURES:
        conn.execute("INSERT OR REPLACE INTO feature_registry VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", f)
    conn.commit()

print("11 features registered.\n")

with sqlite3.connect(DB_PATH) as conn:
    rows = conn.execute("SELECT feature_name, module, runnable, external_data_required FROM feature_registry ORDER BY module, feature_name").fetchall()
    for r in rows:
        print("  [" + r[1] + "] " + r[0] + (" (NOT RUNNABLE)" if not r[2] else "") + (" (external data required)" if r[3] else ""))

print("\nFeature registry setup complete.")
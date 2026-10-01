import sqlite3

conn = sqlite3.connect('gex_data_cache.db')
cur = conn.cursor()

print("=" * 80)
print("GEX REGIME DISTRIBUTION -- PER TICKER (model_a)")
print("=" * 80)
cur.execute("""
    SELECT ticker, gex_regime, COUNT(*) FROM gex_metrics
    WHERE sign_convention='model_a'
    GROUP BY ticker, gex_regime
    ORDER BY ticker, gex_regime
""")
rows = cur.fetchall()
by_ticker = {}
for ticker, regime, count in rows:
    by_ticker.setdefault(ticker, {})[regime] = count

for ticker, regimes in sorted(by_ticker.items()):
    pos = regimes.get("positive", 0)
    neg = regimes.get("negative", 0)
    total = pos + neg
    pct_neg = round(neg / total * 100, 1) if total else 0
    print(ticker + ": positive=" + str(pos) + " negative=" + str(neg) + " (negative=" + str(pct_neg) + "%)")

print("\n" + "=" * 80)
print("NEGATIVE-REGIME DATES (model_a) -- checking if clustered or scattered")
print("=" * 80)
cur.execute("""
    SELECT ticker, snapshot_date FROM gex_metrics
    WHERE sign_convention='model_a' AND gex_regime='negative'
    ORDER BY snapshot_date, ticker
""")
for ticker, date in cur.fetchall():
    print(" ", date, ticker)

print("\n" + "=" * 80)
print("CALL vs PUT OI TOTALS ON NEGATIVE-REGIME DAYS vs POSITIVE-REGIME DAYS")
print("=" * 80)
cur.execute("""
    SELECT gm.gex_regime, SUM(cs.open_interest)
    FROM gex_metrics gm
    JOIN cleaned_snapshot cs ON gm.ticker = cs.ticker AND gm.snapshot_date = cs.snapshot_date
    WHERE gm.sign_convention='model_a' AND cs.option_type='call'
    GROUP BY gm.gex_regime
""")
call_oi = dict(cur.fetchall())
cur.execute("""
    SELECT gm.gex_regime, SUM(cs.open_interest)
    FROM gex_metrics gm
    JOIN cleaned_snapshot cs ON gm.ticker = cs.ticker AND gm.snapshot_date = cs.snapshot_date
    WHERE gm.sign_convention='model_a' AND cs.option_type='put'
    GROUP BY gm.gex_regime
""")
put_oi = dict(cur.fetchall())
print("On POSITIVE-regime days: total call OI=" + str(call_oi.get("positive", 0)) + " total put OI=" + str(put_oi.get("positive", 0)))
print("On NEGATIVE-regime days: total call OI=" + str(call_oi.get("negative", 0)) + " total put OI=" + str(put_oi.get("negative", 0)))

conn.close()
import sqlite3

DB_PATH = "iv_correction_diagnostic.db"
BUCKETS = [(0, 0.40, "Low (<40%)"), (0.40, 0.70, "Moderate (40-70%)"), (0.70, 1.00, "High (70-100%)"), (1.00, 999, "Extreme (>100%)")]

with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    all_rows = conn.execute("SELECT * FROM diagnostic").fetchall()

print("Total rows in complete dataset: " + str(len(all_rows)))

for low, high, label in BUCKETS:
    bucket_rows = [r for r in all_rows if r["historical_iv"] is not None and low <= r["historical_iv"] < high]
    n = len(bucket_rows)
    if n == 0:
        print("\n" + label + ": no observations")
        continue
    errs = sorted(r["corrected_pct_err"] for r in bucket_rows)
    median_err = errs[n // 2]
    mean_err = sum(errs) / n
    residual_rate = len([e for e in errs if e > 20]) / n * 100
    tickers_in_bucket = {}
    for r in bucket_rows:
        tickers_in_bucket[r["ticker"]] = tickers_in_bucket.get(r["ticker"], 0) + 1
    avg_oi = sum(r["open_interest"] or 0 for r in bucket_rows) / n

    print("\n" + label + " (n=" + str(n) + "):")
    print("  Median abs error: " + str(round(median_err, 1)) + "% | Mean: " + str(round(mean_err, 1)) + "%")
    print("  Residual rate (>20% error): " + str(round(residual_rate, 1)) + "%")
    print("  Ticker distribution: " + str(tickers_in_bucket))
    print("  Avg OI: " + str(round(avg_oi, 0)))

print("\n" + "=" * 100)
print("LOW-IV vs HIGH-IV DIRECT COMPARISON (threshold: 70%, pre-specified)")
print("=" * 100)
low_iv = [r for r in all_rows if r["historical_iv"] is not None and r["historical_iv"] < 0.70]
high_iv = [r for r in all_rows if r["historical_iv"] is not None and r["historical_iv"] >= 0.70]
for label, group in [("LOW IV (<70%)", low_iv), ("HIGH IV (>=70%)", high_iv)]:
    n = len(group)
    if n == 0:
        continue
    errs = sorted(r["corrected_pct_err"] for r in group)
    print(label + " (n=" + str(n) + "): median_err=" + str(round(errs[n//2], 1)) + "% mean_err=" + str(round(sum(errs)/n, 1)) + "%")

print("\n" + "=" * 100)
print("TICKER-LEVEL CHECK: does the SMCI/MSTR/AMD pattern hold across ALL their trades?")
print("=" * 100)
for ticker in ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]:
    ticker_rows = [r for r in all_rows if r["ticker"] == ticker]
    n = len(ticker_rows)
    if n == 0:
        continue
    errs = sorted(r["corrected_pct_err"] for r in ticker_rows)
    iv_vals = [r["historical_iv"] for r in ticker_rows if r["historical_iv"]]
    avg_iv = sum(iv_vals) / len(iv_vals) if iv_vals else None
    print(ticker + " (n=" + str(n) + "): median_err=" + str(round(errs[n//2], 1)) + "% avg_historical_IV=" + str(round(avg_iv, 3) if avg_iv else None))

print("\nPHASE 2 ANALYSIS COMPLETE.")
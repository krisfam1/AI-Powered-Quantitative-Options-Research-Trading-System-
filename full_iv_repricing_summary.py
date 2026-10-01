import sqlite3
import statistics

DB_PATH = "full_iv_repricing.db"

with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM repriced_trades").fetchall()

print("=" * 100)
print("FULL-POPULATION HISTORICAL-IV REPRICING -- FINAL RESULTS (n=" + str(len(rows)) + ")")
print("=" * 100)

synthetic_total = sum(r["synthetic_pnl"] for r in rows)
iv_total = sum(r["iv_repriced_pnl"] for r in rows if r["iv_repriced_pnl"] is not None)
n_valid = len([r for r in rows if r["iv_repriced_pnl"] is not None])

print("\nTotal synthetic P&L: $" + str(round(synthetic_total, 2)))
print("Total realistic IV-repriced P&L: $" + str(round(iv_total, 2)) + " (n=" + str(n_valid) + ")")
print("Difference: $" + str(round(synthetic_total - iv_total, 2)))

synth_returns = [r["synthetic_return_pct"] for r in rows]
iv_returns = [r["iv_repriced_return_pct"] for r in rows if r["iv_repriced_return_pct"] is not None]
print("\nAverage synthetic return: " + str(round(statistics.mean(synth_returns),2)) + "% | Median: " + str(round(statistics.median(synth_returns),2)) + "%")
print("Average IV-repriced return: " + str(round(statistics.mean(iv_returns),2)) + "% | Median: " + str(round(statistics.median(iv_returns),2)) + "%")

print("\n" + "=" * 100)
print("CONCENTRATION -- SYNTHETIC vs IV-REPRICED")
print("=" * 100)
sorted_synth = sorted(rows, key=lambda r: -r["synthetic_pnl"])
sorted_iv = sorted([r for r in rows if r["iv_repriced_pnl"] is not None], key=lambda r: -r["iv_repriced_pnl"])

for n in [1, 5, 10, 20]:
    top_n_synth = sum(r["synthetic_pnl"] for r in sorted_synth[:n])
    top_n_iv = sum(r["iv_repriced_pnl"] for r in sorted_iv[:n])
    print("Top " + str(n) + ": synthetic=$" + str(round(top_n_synth,2)) + " (" + str(round(top_n_synth/synthetic_total*100,1)) + "%) | IV-repriced=$" + str(round(top_n_iv,2)) + " (" + str(round(top_n_iv/iv_total*100,1) if iv_total else 0) + "%)")
    excl_synth = synthetic_total - top_n_synth
    excl_iv = iv_total - top_n_iv
    print("  Excluding top " + str(n) + ": synthetic=$" + str(round(excl_synth,2)) + " | IV-repriced=$" + str(round(excl_iv,2)))

print("\n" + "=" * 100)
print("TOP 5 (BY SYNTHETIC RANKING) -- SYNTHETIC vs REPRICED")
print("=" * 100)
for r in sorted_synth[:5]:
    print("  " + r["ticker"] + " " + r["entry_date"] + ": synthetic=$" + str(round(r["synthetic_pnl"],2)) + " (" + str(round(r["synthetic_return_pct"],1)) + "%) | IV_repriced=$" + str(round(r["iv_repriced_pnl"],2) if r["iv_repriced_pnl"] else None) + " (" + str(round(r["iv_repriced_return_pct"],1) if r["iv_repriced_return_pct"] else None) + "%)")

print("\n" + "=" * 100)
print("TOP 20 SUMMARY")
print("=" * 100)
top20_synth_sum = sum(r["synthetic_pnl"] for r in sorted_synth[:20])
top20_iv_sum = sum(r["iv_repriced_pnl"] for r in sorted_iv[:20])
print("Top 20 synthetic total: $" + str(round(top20_synth_sum,2)))
print("Top 20 IV-repriced total: $" + str(round(top20_iv_sum,2)))

print("\n" + "=" * 100)
print("REMAINING (NON-TOP-20) TRADES")
print("=" * 100)
remaining_synth = synthetic_total - top20_synth_sum
remaining_iv = iv_total - top20_iv_sum
print("Remaining 231 trades, synthetic: $" + str(round(remaining_synth,2)))
print("Remaining 231 trades, IV-repriced: $" + str(round(remaining_iv,2)))

print("\n" + "=" * 100)
print("DOES THE CONCENTRATION PROBLEM SURVIVE REALISTIC PRICING?")
print("=" * 100)
print("Synthetic: top 20 = " + str(round(top20_synth_sum/synthetic_total*100,1)) + "% of total, remaining 231 = $" + str(round(remaining_synth,2)))
print("IV-repriced: top 20 = " + str(round(top20_iv_sum/iv_total*100,1) if iv_total else 0) + "% of total, remaining 231 = $" + str(round(remaining_iv,2)))
if remaining_iv < 0 and remaining_synth < 0:
    print("CONFIRMED: concentration problem SURVIVES realistic pricing -- remaining trades are net negative under BOTH methodologies.")
elif remaining_iv >= 0 and remaining_synth < 0:
    print("NOTABLE: remaining trades flip from negative (synthetic) to non-negative (IV-repriced) -- concentration less severe under realistic pricing.")
else:
    print("See figures above for direct comparison.")

print("\nSUMMARY COMPLETE.")
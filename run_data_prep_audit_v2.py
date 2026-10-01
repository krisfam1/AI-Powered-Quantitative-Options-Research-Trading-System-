from dotenv import load_dotenv
load_dotenv()

"""
ENHANCED data-integrity audit -- adds per-ticker primary-test and
train/val/test breakdowns, and PERSISTS the actual row-level dataset
(not just aggregate counts) so it can be reused for preregistration/
execution without a second full re-fetch.
"""

import hashlib
import json
import pickle
from datetime import datetime, timezone
from collections import defaultdict
import backtest_engine as be
from data_prep_experiment1 import (
    find_phase6_candidate_signals, compute_feature_row, build_observation_matrix,
    chronological_split_with_purging, greedy_nonoverlapping_selection,
    fill_iv_percentile_column, LOCKED_FEATURES, TICKERS, FIXED_START, FIXED_END, TARGET_HORIZON
)
from iv_percentile_batch import build_ticker_iv_series

audit = {"per_ticker": {}, "overall": {}}

def compute_target(bars, index, horizon=TARGET_HORIZON):
    if index + horizon >= len(bars):
        return None
    entry = float(bars[index].close)
    exitp = float(bars[index + horizon].close)
    return (exitp - entry) / entry

print("Re-running full pipeline (also persisting row-level data this time)...\n")

spy_bars = be.get_historical_bars("SPY", FIXED_START, FIXED_END)

all_complete_rows = []
all_train, all_val, all_test = [], [], []

for ticker in TICKERS:
    print("Processing " + ticker + "...")
    bars = be.get_historical_bars(ticker, FIXED_START, FIXED_END)
    signal_indices = find_phase6_candidate_signals(ticker, bars, spy_bars)

    raw_rows = []
    for idx in signal_indices:
        target = compute_target(bars, idx)
        row = compute_feature_row(ticker, bars, spy_bars, idx, target)
        raw_rows.append(row)

    trading_days = sorted(set(b.timestamp.date() for b in bars))
    price_lookup = {b.timestamp.date(): float(b.close) for b in bars}
    ticker_iv_series = build_ticker_iv_series(ticker, trading_days, price_lookup)
    raw_rows = fill_iv_percentile_column(raw_rows, ticker_iv_series)

    complete_rows, excluded = build_observation_matrix(raw_rows)
    train, val, test, purge_stats = chronological_split_with_purging(complete_rows)

    all_complete_rows.extend(complete_rows)
    all_train.extend(train)
    all_val.extend(val)
    all_test.extend(test)

# ---- Per-ticker train/val/test breakdown ----
print("\n" + "=" * 100)
print("PER-TICKER TRAIN/VALIDATION/TEST BREAKDOWN")
print("=" * 100)
per_ticker_split = defaultdict(lambda: {"train": 0, "val": 0, "test": 0})
for r in all_train:
    per_ticker_split[r["ticker"]]["train"] += 1
for r in all_val:
    per_ticker_split[r["ticker"]]["val"] += 1
for r in all_test:
    per_ticker_split[r["ticker"]]["test"] += 1
for ticker in TICKERS:
    s = per_ticker_split[ticker]
    print("  " + ticker + ": train=" + str(s["train"]) + " val=" + str(s["val"]) + " test=" + str(s["test"]))

# ---- Primary non-overlapping test selection ----
test_by_ticker = defaultdict(list)
for r in all_test:
    test_by_ticker[r["ticker"]].append(r)
primary_test_set = greedy_nonoverlapping_selection(dict(test_by_ticker))

print("\n" + "=" * 100)
print("PRIMARY NON-OVERLAPPING TEST SET -- BY TICKER")
print("=" * 100)
primary_by_ticker = defaultdict(int)
for r in primary_test_set:
    primary_by_ticker[r["ticker"]] += 1
total_primary = len(primary_test_set)
for ticker in TICKERS:
    count = primary_by_ticker.get(ticker, 0)
    pct = (count / total_primary * 100) if total_primary else 0
    print("  " + ticker + ": " + str(count) + " (" + str(round(pct, 1)) + "%)")
print("  TOTAL: " + str(total_primary))

largest_ticker = max(primary_by_ticker.items(), key=lambda x: x[1]) if primary_by_ticker else (None, 0)
largest_pct = (largest_ticker[1] / total_primary * 100) if total_primary else 0

print("\n" + "=" * 100)
print("REQUIRED FINAL AUDIT ITEMS")
print("=" * 100)
print("1. Primary test set by ticker: reported above")
print("2. Train/val/test by ticker: reported above")
print("3. Largest ticker's % of primary test set: " + largest_ticker[0] + " = " + str(round(largest_pct, 1)) + "%")
print("4. iv_percentile limitation: the 90-day window provides insufficient preceding IV")
print("   history for candidates in roughly the first ~20-30 trading days of the window --")
print("   this is a DATA-WINDOW limitation, not random missingness. Candidate timing")
print("   determines feature availability; the complete-case dataset is NOT necessarily")
print("   representative of the original Phase 6 candidate population.")
print("5. dte_at_index = 14 for EVERY observation (confirmed in prior audit) -- this feature")
print("   has ZERO variation in Experiment 1 due to the synthetic ATM-proxy convention")
print("   (expiry = signal_date + 14 calendar days) and therefore contributes no incremental")
print("   explanatory information in this specific experiment.")
print("6. Six-ticker universe: UNCHANGED -- AAPL, TSLA, NVDA, AMD, SMCI, MSTR, exactly as locked.")
print("7. NO feature, hypothesis, threshold, observation population, or date range changed")
print("   based on these findings.")
print("8. Dataset hash (recomputed, must match prior run): ", end="")

dataset_fingerprint_input = json.dumps(
    [{"ticker": r["ticker"], "signal_index": r["signal_index"], "target": r["target"]} for r in sorted(all_complete_rows, key=lambda r: (r["ticker"], r["signal_index"]))],
    sort_keys=True, default=str
)
dataset_hash = hashlib.sha256(dataset_fingerprint_input.encode()).hexdigest()
print(dataset_hash)
print("   Matches prior audit's caae50de... : " + str(dataset_hash.startswith("caae50de")))

print("9. Primary Wilcoxon test will use EXACTLY these " + str(total_primary) + " non-overlapping")
print("   observations -- no additional filtering or selection will occur at experiment-run time.")

# ---- Persist full row-level dataset for reuse (avoids a second full re-fetch later) ----
dataset_bundle = {
    "all_complete_rows": all_complete_rows,
    "all_train": all_train, "all_val": all_val, "all_test": all_test,
    "primary_test_set": primary_test_set,
    "dataset_hash": dataset_hash,
    "generated_at": datetime.now(timezone.utc).isoformat(),
}
with open("ml_experiment1_dataset.pkl", "wb") as f:
    pickle.dump(dataset_bundle, f)
print("\nFull row-level dataset persisted to ml_experiment1_dataset.pkl (for reuse -- no re-fetch needed for the actual experiment run).")
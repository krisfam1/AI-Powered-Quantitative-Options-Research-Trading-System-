from dotenv import load_dotenv
load_dotenv()

"""
Complete-pipeline audit + real data run for ML Experiment 1's
data-preparation layer. Treated strictly as a DATA-INTEGRITY AUDIT,
not the experiment itself. No preregistration happens here.
"""

import hashlib
import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import backtest_engine as be
from data_prep_experiment1 import (
    find_phase6_candidate_signals, compute_feature_row, build_observation_matrix,
    chronological_split_with_purging, greedy_nonoverlapping_selection,
    fill_iv_percentile_column, LOCKED_FEATURES, TICKERS, FIXED_START, FIXED_END, TARGET_HORIZON
)
from iv_percentile_batch import build_ticker_iv_series

audit = {"per_ticker": {}, "overall": {}, "stop_conditions_triggered": []}


def compute_target(bars, index, horizon=TARGET_HORIZON):
    if index + horizon >= len(bars):
        return None  # insufficient future bars -- explicit None, never fabricated
    entry = float(bars[index].close)
    exitp = float(bars[index + horizon].close)
    return (exitp - entry) / entry


print("=" * 100)
print("COMPLETE-PIPELINE DATA-INTEGRITY AUDIT -- ML Experiment 1")
print("=" * 100)

all_bars_by_ticker = {}
spy_bars = be.get_historical_bars("SPY", FIXED_START, FIXED_END)
print("SPY bars retrieved: " + str(len(spy_bars)))

all_complete_rows = []
all_train, all_val, all_test = [], [], []
purge_totals = {"train": 0, "val": 0}

for ticker in TICKERS:
    print("\nProcessing " + ticker + "...")
    bars = be.get_historical_bars(ticker, FIXED_START, FIXED_END)
    all_bars_by_ticker[ticker] = bars

    signal_indices = find_phase6_candidate_signals(ticker, bars, spy_bars)
    print("  Phase 6 candidates: " + str(len(signal_indices)))

    raw_rows = []
    for idx in signal_indices:
        target = compute_target(bars, idx)
        row = compute_feature_row(ticker, bars, spy_bars, idx, target)
        raw_rows.append(row)

    removed_by_target = len([r for r in raw_rows if r["target"] is None])

    # Build this ticker's IV series and fill in iv_percentile
    trading_days = sorted(set(b.timestamp.date() for b in bars))
    price_lookup = {}
    for b in bars:
        price_lookup[b.timestamp.date()] = float(b.close)
    ticker_iv_series = build_ticker_iv_series(ticker, trading_days, price_lookup)
    raw_rows = fill_iv_percentile_column(raw_rows, ticker_iv_series)

    # Per-feature missingness
    missing_by_feature = {f: 0 for f in LOCKED_FEATURES}
    for row in raw_rows:
        for f in LOCKED_FEATURES:
            if row.get(f) is None:
                missing_by_feature[f] += 1

    complete_rows, excluded = build_observation_matrix(raw_rows)
    print("  Complete rows (all 10 features + target): " + str(len(complete_rows)) + " / " + str(len(raw_rows)))

    # Cross-ticker contamination check
    contamination = len([r for r in complete_rows if r["ticker"] != ticker])

    # Duplicate check
    seen_timestamps = set()
    duplicates = 0
    for r in complete_rows:
        key = (r["ticker"], r["signal_timestamp"])
        if key in seen_timestamps:
            duplicates += 1
        seen_timestamps.add(key)

    # Timestamp ordering check
    indices_seq = [r["signal_index"] for r in complete_rows]
    ordering_violations = sum(1 for i in range(1, len(indices_seq)) if indices_seq[i] < indices_seq[i-1])

    # DTE distribution
    dte_values = [r["dte_at_index"] for r in complete_rows if r.get("dte_at_index") is not None]
    invalid_dte = len([d for d in dte_values if d <= 0])

    train, val, test, purge_stats = chronological_split_with_purging(complete_rows)
    purge_totals["train"] += purge_stats["purged_train"]
    purge_totals["val"] += purge_stats["purged_val"]

    all_complete_rows.extend(complete_rows)
    all_train.extend(train)
    all_val.extend(val)
    all_test.extend(test)

    iv_coverage = len([r for r in complete_rows if r.get("iv_snapshot_date") is not None])

    audit["per_ticker"][ticker] = {
        "raw_bars": len(bars),
        "phase6_candidates": len(signal_indices),
        "missing_by_feature": missing_by_feature,
        "complete_rows": len(complete_rows),
        "removed_by_target": removed_by_target,
        "purged_train": purge_stats["purged_train"],
        "purged_val": purge_stats["purged_val"],
        "train_n": len(train), "val_n": len(val), "test_n": len(test),
        "iv_coverage": iv_coverage,
        "iv_history_depth": len(ticker_iv_series),
        "dte_distribution": {"min": min(dte_values) if dte_values else None, "max": max(dte_values) if dte_values else None, "invalid_negative_or_zero": invalid_dte},
        "duplicate_rows": duplicates,
        "timestamp_ordering_violations": ordering_violations,
        "cross_ticker_contamination": contamination,
    }

# ---- Primary non-overlapping test selection (across all tickers, pooled) ----
test_by_ticker = defaultdict(list)
for r in all_test:
    test_by_ticker[r["ticker"]].append(r)
primary_test_set = greedy_nonoverlapping_selection(dict(test_by_ticker))

# ---- Dataset hash/versioning ----
dataset_fingerprint_input = json.dumps(
    [{"ticker": r["ticker"], "signal_index": r["signal_index"], "target": r["target"]} for r in sorted(all_complete_rows, key=lambda r: (r["ticker"], r["signal_index"]))],
    sort_keys=True, default=str
)
dataset_hash = hashlib.sha256(dataset_fingerprint_input.encode()).hexdigest()

audit["overall"] = {
    "total_complete_rows": len(all_complete_rows),
    "total_train": len(all_train), "total_val": len(all_val), "total_test": len(all_test),
    "primary_nonoverlapping_test_count": len(primary_test_set),
    "total_purged_train": purge_totals["train"], "total_purged_val": purge_totals["val"],
    "dataset_hash": dataset_hash,
    "generated_at": datetime.now(timezone.utc).isoformat(),
}

print("\n" + "=" * 100)
print("AUDIT REPORT")
print("=" * 100)
for ticker, stats in audit["per_ticker"].items():
    print("\n--- " + ticker + " ---")
    for k, v in stats.items():
        print("  " + k + ": " + str(v))

print("\n--- OVERALL ---")
for k, v in audit["overall"].items():
    print("  " + k + ": " + str(v))

# ---- STOP CONDITIONS ----
print("\n" + "=" * 100)
print("STOP CONDITION CHECKS")
print("=" * 100)

MIN_PARTITION_SIZE = 5
stop = False

if audit["overall"]["total_train"] < MIN_PARTITION_SIZE or audit["overall"]["total_val"] < MIN_PARTITION_SIZE or audit["overall"]["total_test"] < MIN_PARTITION_SIZE:
    print("STOP: insufficient observations in a required partition.")
    stop = True

for ticker, stats in audit["per_ticker"].items():
    if stats["dte_distribution"]["invalid_negative_or_zero"] > 0:
        print("STOP: invalid/negative DTE values found for " + ticker)
        stop = True
    if stats["duplicate_rows"] > 0:
        print("STOP: duplicate rows found for " + ticker)
        stop = True
    if stats["timestamp_ordering_violations"] > 0:
        print("STOP: timestamp ordering violation found for " + ticker)
        stop = True
    if stats["cross_ticker_contamination"] > 0:
        print("STOP: cross-ticker contamination found for " + ticker)
        stop = True

if audit["overall"]["primary_nonoverlapping_test_count"] < MIN_PARTITION_SIZE:
    print("STOP: primary non-overlapping test set too small for a meaningful significance test.")
    stop = True

if not stop:
    print("\nNO STOP CONDITIONS TRIGGERED. Pipeline passed the data-integrity audit.")
    print("Per your instructions: this remains an AUDIT result, not a preregistered experiment.")
    print("Next step: inspect this dataset and finalize preregistration -- NOT run automatically here.")
else:
    print("\nSTOP CONDITIONS TRIGGERED -- do NOT preregister or run the experiment.")
    print("Document the finding and report back before any further action.")

with open("ml_experiment1_audit_report.json", "w") as f:
    json.dump(audit, f, indent=2, default=str)
print("\nFull audit report saved to ml_experiment1_audit_report.json")
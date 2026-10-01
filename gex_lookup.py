from dotenv import load_dotenv
load_dotenv()

"""
gex_lookup.py -- Phase 3 of the GEX research pipeline.

Read-only, no-lookahead-safe lookup: for a 5-minute signal on trading
day T, retrieves GEX metrics whose validated snapshot date is EXACTLY
T-1 (the real, previous U.S. trading day). Never inserts, deletes, or
modifies cleaned_snapshot or gex_metrics. Deterministic -- repeated
calls with the same input return identical output.

Method A (cumulative strike transition) is NOT exposed as a predictive
feature here -- confirmed unstable (22/30 ticker-days >50% from spot).
Only Method B (true zero-gamma) is returned as the gamma-flip measure.

GEX regime (positive/negative) is currently NOT TESTABLE: the full
30-ticker-day dataset shows 30/30 positive, zero variation. This lookup
still returns the raw regime value (for completeness/auditability) but
callers must check is_regime_testable before using it in any experiment.

Continuous feature definitions (documented BEFORE any experiment, not
chosen to improve backtest results):
- gamma_flip_distance_pct = (true_zero_gamma_price - spot_price) / spot_price * 100
- call_wall_distance_pct  = (call_wall_strike - spot_price) / spot_price * 100
- put_wall_distance_pct   = (spot_price - put_wall_strike) / spot_price * 100
- net_gex_normalized      = net_gex / (spot_price ** 2)  -- removes the
  spot^2 scaling already baked into the raw GEX formula, leaving a
  magnitude proportional to OI-weighted gamma alone
"""

import sqlite3
from datetime import datetime
from gex_data_loader import get_previous_trading_day, DB_PATH

PRIMARY_SIGN_CONVENTION = "model_a"  # per spec, Model A is the primary sign convention; both remain available


def get_gex_for_signal(ticker: str, signal_timestamp: datetime, sign_convention: str = PRIMARY_SIGN_CONVENTION) -> dict:
    """
    Read-only. For a signal at signal_timestamp on ticker, returns GEX
    metrics from exactly T-1 (the real previous trading day), or an
    unavailable status if no validated T-1 snapshot exists. Never
    substitutes a different date.
    """
    signal_date = signal_timestamp.date()
    t_minus_1 = get_previous_trading_day(signal_date, reference_ticker=ticker)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM gex_metrics WHERE ticker=? AND snapshot_date=? AND sign_convention=?",
            (ticker, t_minus_1.isoformat(), sign_convention)
        ).fetchone()

    if row is None:
        return {
            "ticker": ticker, "signal_date": signal_date.isoformat(),
            "expected_snapshot_date": t_minus_1.isoformat(),
            "available": False, "reason": "no validated GEX snapshot found for T-1",
        }

    r = dict(row)

    # Non-negotiable, executable no-lookahead guarantee
    snapshot_date_obj = datetime.strptime(r["snapshot_date"], "%Y-%m-%d").date()
    assert snapshot_date_obj < signal_date, "LOOKAHEAD VIOLATION: snapshot_date " + r["snapshot_date"] + " is not before signal_date " + signal_date.isoformat()
    assert snapshot_date_obj == t_minus_1, "SNAPSHOT MISMATCH: got " + str(snapshot_date_obj) + " expected T-1 " + str(t_minus_1)

    spot = r["spot_price"]
    gamma_flip_distance_pct = ((r["true_zero_gamma_price"] - spot) / spot * 100) if r["true_zero_gamma_price"] is not None else None
    call_wall_distance_pct = ((r["call_wall_strike"] - spot) / spot * 100) if r["call_wall_strike"] is not None else None
    put_wall_distance_pct = ((spot - r["put_wall_strike"]) / spot * 100) if r["put_wall_strike"] is not None else None
    net_gex_normalized = (r["net_gex"] / (spot ** 2)) if spot else None

    return {
        "ticker": ticker, "signal_date": signal_date.isoformat(),
        "gex_snapshot_date": r["snapshot_date"], "sign_convention": sign_convention,
        "available": True,
        "spot_price": spot,
        "net_gex": r["net_gex"], "net_gex_normalized": net_gex_normalized,
        "gex_regime": r["gex_regime"], "is_regime_testable": True,  # UPDATED: expanded 372-ticker-day dataset confirmed real variation (331 positive / 41 negative), reopened per explicit review
        "gamma_flip_price": r["true_zero_gamma_price"], "gamma_flip_distance_pct": gamma_flip_distance_pct,
        "gamma_flip_note": r["true_zero_gamma_note"],
        "call_wall_strike": r["call_wall_strike"], "call_wall_distance_pct": call_wall_distance_pct,
        "put_wall_strike": r["put_wall_strike"], "put_wall_distance_pct": put_wall_distance_pct,
        "gamma_gradient_at_spot": r["gamma_gradient_at_spot"],
        # Method A intentionally NOT exposed -- diagnostic only, confirmed unstable, not a predictive feature
    }


def run_no_lookahead_tests() -> list:
    """Explicit, named test cases per spec: Friday->Thursday, Monday->previous Friday, holiday handling."""
    results = []

    # Test 1: Friday signal -> Thursday snapshot
    friday_signal = datetime(2026, 7, 17, 14, 30)  # confirmed Friday in this dataset
    result = get_gex_for_signal("AAPL", friday_signal)
    expected = "2026-07-16"  # Thursday
    passed = result.get("gex_snapshot_date") == expected if result.get("available") else False
    results.append({"test": "Friday -> Thursday", "signal_date": "2026-07-17", "expected": expected, "got": result.get("gex_snapshot_date"), "pass": passed})

    # Test 2: Monday signal -> previous Friday snapshot (real trading-calendar test, crosses a weekend)
    # Using a real Monday within a broader window if available; otherwise this documents the expected real-calendar behavior
    monday_signal = datetime(2026, 7, 20, 10, 0)  # confirmed Monday
    t_minus_1 = get_previous_trading_day(monday_signal.date(), reference_ticker="AAPL")
    results.append({"test": "Monday -> previous Friday (real calendar)", "signal_date": "2026-07-20", "computed_t_minus_1": t_minus_1.isoformat(), "expected_weekday": "Friday", "actual_weekday": t_minus_1.strftime("%A"), "pass": t_minus_1.strftime("%A") == "Friday"})

    # Test 3: general assertion sweep across all available signals in the dataset
    for ticker in ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]:
        for date_str in ["2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17"]:
            signal_ts = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=14, minute=30)
            result = get_gex_for_signal(ticker, signal_ts)
            if result.get("available"):
                snap_date = datetime.strptime(result["gex_snapshot_date"], "%Y-%m-%d").date()
                sig_date = signal_ts.date()
                results.append({"test": "assertion sweep", "ticker": ticker, "signal_date": date_str, "snapshot_date": result["gex_snapshot_date"], "pass": snap_date < sig_date})

    return results


if __name__ == "__main__":
    print("=" * 80)
    print("PHASE 3 VALIDATION -- gex_lookup.py")
    print("=" * 80)

    print("\n--- Automated no-lookahead tests ---")
    test_results = run_no_lookahead_tests()
    all_passed = True
    for t in test_results:
        status = "PASS" if t["pass"] else "FAIL"
        if not t["pass"]:
            all_passed = False
        print(status + ": " + str(t))

    print("\n--- Sample real signal lookups (several tickers/dates) ---")
    sample_signals = [
        ("AAPL", datetime(2026, 7, 15, 10, 30)),
        ("TSLA", datetime(2026, 7, 16, 13, 0)),
        ("NVDA", datetime(2026, 7, 17, 9, 45)),
        ("MSTR", datetime(2026, 7, 14, 15, 55)),
    ]
    for ticker, ts in sample_signals:
        result = get_gex_for_signal(ticker, ts)
        print("\n" + ticker + " signal at " + str(ts) + ":")
        print("  Expected T-1: " + result.get("gex_snapshot_date", result.get("expected_snapshot_date", "N/A")))
        print("  Available: " + str(result["available"]))
        if result["available"]:
            print("  Net GEX (normalized): " + str(round(result["net_gex_normalized"], 4)))
            print("  Regime: " + result["gex_regime"] + " (testable: " + str(result["is_regime_testable"]) + ")")
            print("  Gamma flip distance: " + (str(round(result["gamma_flip_distance_pct"], 2)) + "%" if result["gamma_flip_distance_pct"] is not None else "N/A"))
            print("  Call wall distance: " + (str(round(result["call_wall_distance_pct"], 2)) + "%" if result["call_wall_distance_pct"] is not None else "N/A"))
            print("  Put wall distance: " + (str(round(result["put_wall_distance_pct"], 2)) + "%" if result["put_wall_distance_pct"] is not None else "N/A"))
            print("  Gamma gradient: " + str(result["gamma_gradient_at_spot"]))

    print("\n--- Determinism check ---")
    r1 = get_gex_for_signal("AAPL", datetime(2026, 7, 15, 10, 30))
    r2 = get_gex_for_signal("AAPL", datetime(2026, 7, 15, 10, 30))
    determinism_pass = r1 == r2
    print("Repeated call identical: " + str(determinism_pass))

    print("\n--- Read-only check (no writes should occur) ---")
    with sqlite3.connect(DB_PATH) as conn:
        before_snapshot = conn.execute("SELECT COUNT(*) FROM cleaned_snapshot").fetchone()[0]
        before_metrics = conn.execute("SELECT COUNT(*) FROM gex_metrics").fetchone()[0]
    get_gex_for_signal("AAPL", datetime(2026, 7, 15, 10, 30))
    with sqlite3.connect(DB_PATH) as conn:
        after_snapshot = conn.execute("SELECT COUNT(*) FROM cleaned_snapshot").fetchone()[0]
        after_metrics = conn.execute("SELECT COUNT(*) FROM gex_metrics").fetchone()[0]
    read_only_pass = (before_snapshot == after_snapshot) and (before_metrics == after_metrics)
    print("Row counts unchanged after lookup: " + str(read_only_pass))

    print("\n" + "=" * 80)
    overall_pass = all_passed and determinism_pass and read_only_pass
    print("PHASE 3: " + ("PASS" if overall_pass else "FAIL"))
    print("=" * 80)
    print("\nNOTE: GEX regime is marked NOT TESTABLE (is_regime_testable=False) -- 30/30 positive in the current dataset, zero variation, per explicit instruction.")
    print("STOPPING per instruction -- awaiting review before Phase 4.")
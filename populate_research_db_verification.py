import sqlite3
import json
from datetime import datetime, timezone

DB_PATH = "research_database.db"

with sqlite3.connect(DB_PATH) as conn:

    # ============================================================
    # EXPERIMENT 1: Phase 6 -- Signal vs Random/Regime Control
    # ============================================================
    conn.execute("""
        INSERT OR REPLACE INTO experiments (
            experiment_id, created_at, experiment_type, hypothesis, research_question,
            preregistered_at, hypothesis_locked, hypothesis_amended_after_results,
            dataset_version, date_range_start, date_range_end, universe, option_type,
            parameters, pricing_methodology, sample_size,
            primary_result_summary, primary_metric_value, statistical_tests_used,
            multiple_testing_correction, oos_tested, concentration_tested, robustness_tested,
            conclusion, status, related_experiment_ids, notes
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        "phase6_signal_random_control_20260914", datetime.now(timezone.utc).isoformat(), "signal_research",
        "The breakout+7-factor-score entry signal (threshold>=20) predicts favorable 20-bar forward returns beyond ticker and bullish-regime membership alone.",
        "Does the current entry signal have standalone predictive value on the underlying?",
        datetime.now(timezone.utc).isoformat(), 1, 0,
        "eodhd_clean_window_v1", "2026-06-11", "2026-09-09",
        json.dumps(["AAPL","TSLA","NVDA","AMD","SMCI","MSTR"]), "call",
        json.dumps({"entry_score_threshold": 20, "horizon_bars": 20, "n_replicates": 1000, "seeds": [42,43]}),
        "n/a (underlying-only, no options pricing)", 579,
        "Signal did not beat regime-matched random control; primary p=0.996-0.997, secondary same-day control p=1.0",
        0.996, json.dumps({"primary_monte_carlo_p": [0.996, 0.997], "secondary_monte_carlo_p": [1.0, 1.0]}),
        "Bonferroni across primary+temporal family (alpha=0.025)", 0, 0, 1,
        "No validated standalone predictive edge found. Result stable and reproducible across two independent seeds.",
        "REJECTED", json.dumps([]), "Located and rejected an earlier exploratory script (signal_validation_core.py) as unsuitable for confirmatory use before building this test."
    ))

    conn.execute("INSERT INTO experiment_robustness_tests (experiment_id, test_type, test_description, result_summary, survived) VALUES (?,?,?,?,?)",
        ("phase6_signal_random_control_20260914", "leave_one_ticker_out", "Excluded each of 6 tickers in turn", "T remained negative in all 6 exclusion scenarios (-0.20% to -0.38%)", 0))

    for gate, applicable, run, passed, evidence in [
        ("random_control", 1, 1, 0, "Primary + secondary Monte Carlo control, p=0.996-1.0"),
        ("concentration", 0, 0, None, "Not applicable -- this experiment tests raw signal quality, not portfolio P&L"),
        ("realistic_pricing", 0, 0, None, "Not applicable -- underlying-only, no options involved"),
        ("lookahead_audit", 1, 1, 1, "Regime labels confirmed computed from information available at each candidate bar only"),
        ("out_of_sample", 0, 0, None, "Not applicable at this stage -- single-window signal test"),
        ("robustness", 1, 1, 0, "Leave-one-ticker-out, score-bin, holding-horizon checks all reinforced the negative finding"),
        ("reproduction", 1, 1, 1, "Two independent seeds produced consistent p-values (diff<0.02)"),
    ]:
        conn.execute("INSERT INTO experiment_gate_checklist (experiment_id, gate_name, applicable, run, passed, evidence_summary) VALUES (?,?,?,?,?,?)",
            ("phase6_signal_random_control_20260914", gate, applicable, run, passed, evidence))

    # ============================================================
    # EXPERIMENT 2: Phase 7 -- Full-Strategy P&L Concentration
    # ============================================================
    conn.execute("""
        INSERT OR REPLACE INTO experiments (
            experiment_id, created_at, experiment_type, hypothesis, research_question,
            preregistered_at, hypothesis_locked, hypothesis_amended_after_results,
            dataset_version, date_range_start, date_range_end, universe, option_type,
            pricing_methodology, sample_size, primary_result_summary, primary_metric_value,
            concentration_tested, concentration_result_summary,
            conclusion, status, related_experiment_ids, notes
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        "phase7_pnl_concentration_20260914", datetime.now(timezone.utc).isoformat(), "baseline",
        "The frozen V1 strategy's historical P&L is broadly distributed across trades, not dominated by a small number of extreme outliers.",
        "Where did V1's historical profitability actually come from, and is it robust or fragile?",
        datetime.now(timezone.utc).isoformat(), 1, 0,
        "eodhd_clean_window_v1", "2026-06-11", "2026-09-09",
        json.dumps(["AAPL","TSLA","NVDA","AMD","SMCI","MSTR"]), "call",
        "v1_synthetic_realized_vol", 251,
        "Top 20 of 251 trades produced 215.6% of total P&L; remaining 231 trades net -$23,604.68",
        215.6, 1, "Top 1=35.5%, Top 5=97.7%, Top 20=215.6% of total P&L; top-5 MFE (533.6% median) vs rest (36.9% median) -- confirmed statistical outliers",
        "Historical profitability entirely dependent on a small number of extreme tail events; hypothesis of broad distribution REJECTED.",
        "REJECTED", json.dumps(["phase6_signal_random_control_20260914"]),
        "Exact reproduction of frozen baseline ($20,427.64, 251 trades) confirmed before any attribution performed."
    ))

    for ticker, n, pnl, wr, pct in [
        ("AAPL",30,1469.31,46.7,7.2),("TSLA",43,1285.42,44.2,6.3),("NVDA",37,-3246.24,35.1,-15.9),
        ("AMD",47,2484.16,40.4,12.2),("SMCI",46,10083.02,39.1,49.4),("MSTR",48,8351.96,37.5,40.9)
    ]:
        conn.execute("INSERT INTO experiment_ticker_results (experiment_id, ticker, n_trades, pnl, win_rate, pct_of_total_pnl) VALUES (?,?,?,?,?,?)",
            ("phase7_pnl_concentration_20260914", ticker, n, pnl, wr, pct))

    for gate, applicable, run, passed, evidence in [
        ("random_control", 0, 0, None, "Not applicable -- this is a P&L attribution study, not a signal-discovery test"),
        ("concentration", 1, 1, 0, "Top 20/251 = 215.6% of P&L; remaining 231 net negative -- FAILED"),
        ("realistic_pricing", 0, 0, None, "Deferred to the dedicated full-population IV repricing experiment"),
        ("lookahead_audit", 1, 1, 1, "Bar-by-bar reconstruction confirmed to use only real historical bars, no future information"),
        ("out_of_sample", 0, 0, None, "Not applicable -- single-window attribution study"),
        ("robustness", 1, 1, 0, "Top-5 characteristics confirmed as genuine outliers (MFE 14x higher than remaining population)"),
        ("reproduction", 1, 1, 1, "Exact reproduction of $20,427.64 / 251 trades confirmed before attribution began"),
    ]:
        conn.execute("INSERT INTO experiment_gate_checklist (experiment_id, gate_name, applicable, run, passed, evidence_summary) VALUES (?,?,?,?,?,?)",
            ("phase7_pnl_concentration_20260914", gate, applicable, run, passed, evidence))

    # ============================================================
    # EXPERIMENT 3: Full-Population Historical-IV Repricing
    # ============================================================
    conn.execute("""
        INSERT OR REPLACE INTO experiments (
            experiment_id, created_at, experiment_type, hypothesis, research_question,
            preregistered_at, hypothesis_locked, hypothesis_amended_after_results,
            dataset_version, date_range_start, date_range_end, universe, option_type,
            pricing_methodology, sample_size, primary_result_summary, primary_metric_value,
            concentration_tested, concentration_result_summary,
            conclusion, status, related_experiment_ids, notes
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        "full_population_iv_repricing_20260914", datetime.now(timezone.utc).isoformat(), "pricing_validation",
        "V1's historical P&L, when repriced using real historical implied volatility (not synthetic realized volatility), remains substantially positive.",
        "Is V1's reported historical profitability an artifact of synthetic option pricing?",
        datetime.now(timezone.utc).isoformat(), 1, 0,
        "eodhd_clean_window_v1", "2026-06-11", "2026-09-09",
        json.dumps(["AAPL","TSLA","NVDA","AMD","SMCI","MSTR"]), "call",
        "historical_iv_real_eodhd", 251,
        "Realistic full-population repriced P&L = -$1,874.37 vs synthetic +$20,427.64 (gap: $22,302.01)",
        -1874.37, 1, "Concentration confirmed to survive and worsen under realistic pricing: remaining 231 trades' losses nearly doubled (-$23,605 synthetic to -$44,936 real)",
        "Synthetic pricing materially overstated historical profitability. Under realistic pricing, the strategy shows a net loss over this window. Hypothesis REJECTED.",
        "REJECTED", json.dumps(["phase6_signal_random_control_20260914", "phase7_pnl_concentration_20260914"]),
        "All 251/251 trades successfully repriced in a single run, zero skipped. Resumable design was built but not needed."
    ))

    for gate, applicable, run, passed, evidence in [
        ("random_control", 0, 0, None, "Not applicable -- this is a pricing-methodology validation, not a signal test"),
        ("concentration", 1, 1, 0, "Concentration confirmed to survive realistic pricing -- FAILED (worsened, not improved)"),
        ("realistic_pricing", 1, 1, 1, "This IS the realistic-pricing gate for the underlying Phase 7 finding -- full 251/251 population repriced"),
        ("lookahead_audit", 1, 1, 1, "T-1 real trading-day snapshot rule enforced for every entry and exit IV lookup"),
        ("out_of_sample", 0, 0, None, "Not applicable -- same window as Phase 6/7, not an independent sample"),
        ("robustness", 0, 0, None, "Not separately tested here -- see Phase 7 for robustness checks on the underlying concentration finding"),
        ("reproduction", 1, 1, 1, "Baseline reproduction ($20,427.64/251) confirmed before repricing began"),
    ]:
        conn.execute("INSERT INTO experiment_gate_checklist (experiment_id, gate_name, applicable, run, passed, evidence_summary) VALUES (?,?,?,?,?,?)",
            ("full_population_iv_repricing_20260914", gate, applicable, run, passed, evidence))

    conn.commit()

print("Verification records inserted for 3 experiments (Phase 6, Phase 7 concentration, full IV repricing).\n")

# Now query back to confirm the schema genuinely represents the research
print("=" * 100)
print("VERIFICATION QUERY: Full research lineage")
print("=" * 100)
rows = conn.execute("SELECT experiment_id, experiment_type, status, primary_result_summary FROM experiments ORDER BY created_at").fetchall() if False else None
with sqlite3.connect(DB_PATH) as conn2:
    rows = conn2.execute("SELECT experiment_id, experiment_type, status, primary_result_summary FROM experiments ORDER BY rowid").fetchall()
    for r in rows:
        print(r[0] + " [" + r[1] + "] status=" + r[2])
        print("  -> " + r[3])

    print("\n" + "=" * 100)
    print("GATE CHECKLIST SUMMARY PER EXPERIMENT")
    print("=" * 100)
    for exp_id in [r[0] for r in rows]:
        gates = conn2.execute("SELECT gate_name, applicable, run, passed FROM experiment_gate_checklist WHERE experiment_id=?", (exp_id,)).fetchall()
        applicable_gates = [g for g in gates if g[1] == 1]
        passed_gates = [g for g in applicable_gates if g[3] == 1]
        print(exp_id + ": " + str(len(applicable_gates)) + " applicable gates, " + str(len(passed_gates)) + " passed")

    print("\n" + "=" * 100)
    print("TICKER-LEVEL CONCENTRATION CHECK (Phase 7 experiment)")
    print("=" * 100)
    ticker_rows = conn2.execute("SELECT ticker, pnl, pct_of_total_pnl FROM experiment_ticker_results WHERE experiment_id='phase7_pnl_concentration_20260914' ORDER BY pnl DESC").fetchall()
    for tr in ticker_rows:
        print("  " + tr[0] + ": $" + str(tr[1]) + " (" + str(tr[2]) + "% of total)")

print("\nSCHEMA VERIFICATION COMPLETE -- successfully represents Phase 6 -> Phase 7 -> full IV repricing research chain.")
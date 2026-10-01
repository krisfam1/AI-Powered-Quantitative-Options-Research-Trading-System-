import sqlite3

DB_PATH = "research_database.db"

with sqlite3.connect(DB_PATH) as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            experiment_id TEXT PRIMARY KEY,
            created_at TEXT,
            experiment_type TEXT,  -- controlled vocabulary (documented, not enforced): baseline, signal_research, feature_test, model_test, exit_test, pricing_validation, robustness, oos_validation
            hypothesis TEXT,
            research_question TEXT,
            preregistered_at TEXT,
            hypothesis_locked INTEGER DEFAULT 0,  -- boolean
            hypothesis_amended_after_results INTEGER DEFAULT 0,  -- boolean, IRREVERSIBLE once set to 1 (enforced by trigger below)
            dataset_version TEXT,
            date_range_start TEXT,
            date_range_end TEXT,
            universe TEXT,  -- JSON list
            option_type TEXT,  -- call, put, or both
            features_used TEXT,  -- JSON list
            parameters TEXT,  -- JSON
            model_version TEXT,
            pricing_methodology TEXT,
            execution_assumptions TEXT,
            train_period_start TEXT,
            train_period_end TEXT,
            validation_period_start TEXT,
            validation_period_end TEXT,
            test_period_start TEXT,
            test_period_end TEXT,
            sample_size INTEGER,
            primary_result_summary TEXT,
            primary_metric_value REAL,
            statistical_tests_used TEXT,  -- JSON
            multiple_testing_correction TEXT,
            oos_tested INTEGER DEFAULT 0,
            oos_result_summary TEXT,
            concentration_tested INTEGER DEFAULT 0,
            concentration_result_summary TEXT,
            robustness_tested INTEGER DEFAULT 0,
            conclusion TEXT,
            status TEXT,  -- ACCEPTED / REJECTED / INCONCLUSIVE / PROMISING_NEEDS_FOLLOWUP -- set by external Experiment Framework logic, NOT computed by the database itself
            data_dependencies TEXT,
            data_cost TEXT,
            related_experiment_ids TEXT,  -- JSON list
            notes TEXT
        )
    """)

    # Enforce irreversibility of hypothesis_amended_after_results at the database level
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_amendment_flag_reset
        BEFORE UPDATE OF hypothesis_amended_after_results ON experiments
        WHEN OLD.hypothesis_amended_after_results = 1 AND NEW.hypothesis_amended_after_results = 0
        BEGIN
            SELECT RAISE(ABORT, 'hypothesis_amended_after_results is a permanent audit flag and cannot be reset to FALSE once set to TRUE');
        END;
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS experiment_ticker_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id TEXT,
            ticker TEXT,
            n_trades INTEGER,
            pnl REAL,
            win_rate REAL,
            pct_of_total_pnl REAL,
            FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS experiment_robustness_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id TEXT,
            test_type TEXT,
            test_description TEXT,
            result_summary TEXT,
            survived INTEGER,  -- boolean
            FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS experiment_gate_checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id TEXT,
            gate_name TEXT,  -- random_control, concentration, realistic_pricing, lookahead_audit, out_of_sample, robustness, reproduction
            applicable INTEGER,  -- boolean: is this gate even relevant to this experiment_type?
            run INTEGER DEFAULT 0,  -- boolean: was it actually executed?
            passed INTEGER,  -- boolean, NULL if not yet run
            evidence_summary TEXT,
            FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
        )
    """)

    conn.commit()

print("Schema created successfully: 4 tables + 1 trigger.")

# Verify trigger works as intended
print("\nVerifying irreversibility trigger...")
with sqlite3.connect(DB_PATH) as conn:
    conn.execute("INSERT INTO experiments (experiment_id, hypothesis_amended_after_results) VALUES ('trigger_test', 1)")
    conn.commit()
    try:
        conn.execute("UPDATE experiments SET hypothesis_amended_after_results = 0 WHERE experiment_id = 'trigger_test'")
        conn.commit()
        print("  FAIL: reset was allowed (trigger not working)")
    except sqlite3.IntegrityError as e:
        print("  PASS: reset correctly blocked -- " + str(e))
    conn.execute("DELETE FROM experiments WHERE experiment_id = 'trigger_test'")
    conn.commit()

print("\nSchema creation and trigger verification complete.")
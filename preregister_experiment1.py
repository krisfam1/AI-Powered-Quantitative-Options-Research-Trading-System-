from dotenv import load_dotenv
load_dotenv()

"""
Constructs and preregisters ExperimentConfig for ML Experiment 1.
Per explicit instruction: does NOT execute the experiment in this
same step. Prints the entire frozen config and config_hash for
inspection BEFORE preregistering, and again AFTER, to confirm the
persisted record matches exactly.
"""

from experiment_config import ExperimentConfig
from experiment import preregister_experiment
import db_interface
import json

NOTES = (
    "DATA-INTEGRITY AUDIT FINDINGS (documented, NOT used to modify hypothesis/methodology): "
    "(1) TSLA contributes only 1 of 24 primary non-overlapping test observations (train=0, val=0, test=1) "
    "due to a structural feature-availability limitation, not a methodology change. "
    "(2) AAPL contributes the largest share of the primary test set at 7/24 = 29.2%. "
    "Full primary-test distribution: AAPL=7, NVDA=5, SMCI=5, AMD=3, MSTR=3, TSLA=1. "
    "(3) iv_percentile has structural missingness because the available IV history begins with "
    "the experiment window itself rather than providing a full prior lookback -- candidates in "
    "roughly the first 20-30 trading days of the window cannot have sufficient history. This is a "
    "DATA-WINDOW limitation, not random missingness; the complete-case dataset is not necessarily "
    "representative of the original Phase 6 candidate population. "
    "(4) dte_at_index equals exactly 14 for every single observation, due to the documented "
    "synthetic ATM-proxy contract construction (expiry = signal_date + 14 calendar days). This "
    "feature therefore has ZERO variation in this experiment and cannot contribute incremental "
    "explanatory information. "
    "(5) Dataset hash: caae50de859f3b830a419c1f17c92f6aa77317ac4d72d541f8cad0e79c334c81 -- confirmed "
    "identical across two fully independent pipeline runs. "
    "(6) The observation population, six-ticker universe, feature set, date range, and methodology "
    "were NOT changed after inspecting the data. All findings above were discovered via the "
    "data-integrity audit and are recorded here for transparency, not incorporated into the "
    "hypothesis or any pre-result design decision."
)

config = ExperimentConfig(
    experiment_id="ml_experiment1_feature_factory_vs_baseline_20260917",
    experiment_type="signal_research",
    hypothesis=(
        "A model using the full locked Feature Factory feature set produces lower out-of-sample "
        "prediction error for 20-bar forward returns than a minimal baseline model using only "
        "past_return_n, on the same clean data window and ticker universe validated throughout "
        "this project."
    ),
    research_question=(
        "Does the locked Feature Factory feature set contain predictive information about future "
        "underlying returns beyond a minimal single-feature baseline within the Phase 6 candidate "
        "population?"
    ),
    dataset_version="clean_window_v1_phase6_candidates",
    date_range=("2026-06-11", "2026-09-09"),
    universe=["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"],
    option_type="call",
    features_used=[
        ("past_return_n", "1.0"), ("breakout_strength", "1.0"), ("atr_normalized", "1.0"),
        ("dte_at_index", "1.0"), ("delta_at_index", "1.0"), ("iv_vs_realized_vol", "1.0"),
        ("iv_percentile", "1.0"), ("spy_trend_state", "1.0"), ("relative_strength_vs_spy", "1.0"),
        ("vwap_distance", "1.0"),
    ],
    parameters={
        "baseline_feature": "past_return_n",
        "target_horizon_bars": 20,
        "train_frac": 0.6, "val_frac": 0.2, "test_frac": 0.2,
        "purge_horizon_bars": 20,
        "model_class": "Ridge",
        "ridge_alpha_grid": [0.01, 0.1, 1.0, 10.0, 100.0],
        "effect_size_threshold_relative_mse_reduction": 0.10,
        "primary_test": "paired_wilcoxon_one_sided_greater",
        "primary_test_population": "greedy_nonoverlapping_chronological_within_ticker",
        "dataset_hash": "caae50de859f3b830a419c1f17c92f6aa77317ac4d72d541f8cad0e79c334c81",
    },
    model_version=None,
    pricing_methodology="n/a_underlying_prediction_only",
    execution_assumptions="ATM-proxy contract construction (strike=round(price/5)*5, expiry=signal_date+14d); realized_vol via existing validated calculate_historical_volatility; historical IV via validated T-1 data-layer helper.",
    train_period=None, validation_period=None, test_period=None,
    random_seeds=[42],
    code_version="ml_exp1_v1",
    testing_family_declaration="INDEPENDENT_SINGLE",
    applicability_lock=[
        ("data_integrity", True), ("lookahead_audit", True), ("timestamp_safety", True),
        ("sample_size_adequacy", True), ("statistical_testing", True), ("reproduction", True),
        ("primary_test_significant", True), ("effect_size_meets_threshold", True),
        ("multiple_testing_survived", True), ("robustness_survived", True),
        ("oos_survived", False),
        ("primary_performance_test_significant", False), ("concentration_check", False),
        ("pricing_accuracy_meets_threshold", False), ("pricing_coverage_meets_threshold", False),
    ],
    oos_validation_claimed=False,
    declared_robustness_checks=[
        "leave_one_ticker_out", "alternate_horizon:10bar", "alternate_horizon:5bar",
    ],
)

print("=" * 100)
print("CONSTRUCTED CONFIG -- FULL INSPECTION BEFORE PREREGISTRATION")
print("=" * 100)
print("experiment_id: " + config.experiment_id)
print("experiment_type: " + config.experiment_type)
print("hypothesis: " + config.hypothesis)
print("research_question: " + config.research_question)
print("universe: " + str(config.universe))
print("date_range: " + str(config.date_range))
print("features_used: " + str(config.features_used))
print("baseline_feature (in parameters): " + str(dict(config.parameters).get("baseline_feature")))
print("testing_family_declaration: " + config.testing_family_declaration)
print("oos_validation_claimed: " + str(config.oos_validation_claimed))
print("applicability_lock: " + str(config.applicability_lock))
print("declared_robustness_checks: " + str(config.declared_robustness_checks))
print("\nCONFIG HASH: " + config.config_hash)
print("\n" + "=" * 100)

confirm = input("Type EXACTLY 'PREREGISTER' to proceed, anything else to abort: ")
if confirm != "PREREGISTER":
    print("Aborted -- no preregistration occurred.")
    exit()

experiment = preregister_experiment(config)
print("\nPreregistered successfully.")
print("state: " + experiment.state)
print("preregistered_at: " + experiment.preregistered_at)

# Write the documented limitations to the notes column (data-audit findings,
# NOT part of the locked ExperimentConfig -- written post-preregistration,
# never influences the hypothesis or methodology).
import sqlite3
with sqlite3.connect(db_interface.DB_PATH) as conn:
    conn.execute("UPDATE experiments SET notes=? WHERE experiment_id=?", (NOTES, config.experiment_id))
    conn.commit()
print("Data-audit findings written to notes field (documentation only, not methodology).")

print("\n" + "=" * 100)
print("VERIFICATION -- RE-READING PERSISTED RECORD FROM DATABASE")
print("=" * 100)
persisted = db_interface.get_experiment_record(config.experiment_id)
print("Persisted config_hash: " + persisted["config_hash"])
print("Matches constructed config_hash: " + str(persisted["config_hash"] == config.config_hash))
print("Persisted state: " + persisted["state"])
print("Persisted hypothesis matches: " + str(persisted["hypothesis"] == config.hypothesis))

print("\n" + "=" * 100)
print("PREREGISTRATION COMPLETE. EXPERIMENT NOT YET EXECUTED.")
print("Per instruction: run_experiment.run_experiment() must be called SEPARATELY, not here.")
print("=" * 100)
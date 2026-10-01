from dotenv import load_dotenv
load_dotenv()

"""
Executes ML Experiment 1 through the full framework:
run_experiment.run_experiment() -> gates -> verdict -> persisted result.
Uses the persisted, hash-verified dataset -- no new data fetching.
"""

import run_experiment
from ml_experiment1_final_executor import run_ml_experiment_1_final

EXPERIMENT_ID = "ml_experiment1_feature_factory_vs_baseline_20260917"

print("Executing " + EXPERIMENT_ID + " through the full framework...\n")

verdict = run_experiment.run_experiment(EXPERIMENT_ID, run_ml_experiment_1_final, run_reason="implemented and included the 3 declared robustness checks (previously missing, causing an incomplete verdict)")

print("=" * 100)
print("FINAL VERDICT")
print("=" * 100)
print("Status: " + verdict.status)
print("Reasoning: " + verdict.reasoning)
if verdict.promising_meaning:
    print("\nPROMISING MEANING (scope of this result): " + verdict.promising_meaning)

print("\n" + "=" * 100)
print("REMINDER")
print("=" * 100)
print("This verdict does NOT modify V1. PROMISING (if reached) means only:")
print("'worth a separate strategy-level validation experiment' -- nothing more.")
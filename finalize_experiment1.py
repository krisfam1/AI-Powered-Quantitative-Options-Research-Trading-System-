from dotenv import load_dotenv
load_dotenv()

"""
Verifies the already-persisted Experiment 1 verdict/gates, and appends
a formal, permanent closing summary to the notes field -- documenting
the 5-bar finding correctly as exploratory evidence from a robustness
check, NOT a confirmed edge or independent primary result.
"""

import sqlite3
import db_interface

EXPERIMENT_ID = "ml_experiment1_feature_factory_vs_baseline_20260917"

print("=" * 100)
print("VERIFICATION: ALREADY-PERSISTED VERDICT AND GATE STATE")
print("=" * 100)

with sqlite3.connect(db_interface.DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    verdict_rows = conn.execute(
        "SELECT * FROM experiment_verdicts WHERE experiment_id=? ORDER BY id DESC LIMIT 1", (EXPERIMENT_ID,)
    ).fetchall()
    gate_rows = conn.execute(
        "SELECT gate_name, passed, evidence_summary FROM experiment_gate_checklist WHERE experiment_id=? ORDER BY id", (EXPERIMENT_ID,)
    ).fetchall()

if not verdict_rows:
    print("ERROR: no verdict found. Cannot finalize.")
    exit()

v = verdict_rows[0]
print("Persisted verdict status: " + v["status"])
print("Persisted reasoning: " + v["reasoning"])
print("Linked execution_id: " + str(v["execution_id"]))
print("gate_checklist_max_id (evidentiary snapshot): " + str(v["gate_checklist_max_id"]))

print("\nFull gate state at time of verdict:")
for g in gate_rows:
    print("  " + g["gate_name"] + ": passed=" + str(g["passed"]))

FINAL_SUMMARY = (
    "=== EXPERIMENT 1 -- FORMALLY CLOSED ===\n"
    "Type: signal_research | Primary horizon: 20 bars | Verdict: REJECTED\n"
    "Primary result: p=0.2635, relative MSE reduction=-2.09% (threshold was +10%).\n"
    "robustness_survived: SURVIVED (all 3 declared checks completed).\n"
    "  - leave_one_ticker_out: no contradiction across all 6 exclusions.\n"
    "  - alternate_horizon:10bar: p=0.208, relative MSE reduction=-0.10% (no meaningful evidence).\n"
    "  - alternate_horizon:5bar: p=0.0091, relative MSE reduction=+4.25%.\n"
    "\n"
    "IMPORTANT FRAMING FOR THE 5-BAR RESULT: This is exploratory evidence discovered WITHIN a "
    "preregistered ROBUSTNESS CHECK, not a separately preregistered primary hypothesis, and not "
    "independent confirmation of an edge. The statistically significant p-value (0.0091) is real, "
    "but the observed effect size (+4.25%) fell below this experiment's own preregistered 10% "
    "economic-significance threshold. The correct, narrow statement of evidence is: 'the full "
    "feature set produced statistically detectable improvement over the past_return_n baseline at "
    "the 5-bar horizon, but the observed improvement was below the preregistered effect-size "
    "threshold.' This is NOT evidence of a usable trading edge and must not be treated as such. "
    "Any further investigation of the 5-bar horizon requires an independently preregistered "
    "experiment (Experiment 2) with its own hypothesis, effect threshold, and full gate battery -- "
    "never a retroactive promotion of this robustness-check finding.\n"
    "\n"
    "Dataset hash: caae50de859f3b830a419c1f17c92f6aa77317ac4d72d541f8cad0e79c334c81 (confirmed "
    "identical across two independent pipeline runs).\n"
    "V1 was not modified by this experiment or its verdict."
)

with sqlite3.connect(db_interface.DB_PATH) as conn:
    current_notes = conn.execute("SELECT notes FROM experiments WHERE experiment_id=?", (EXPERIMENT_ID,)).fetchone()[0]
    new_notes = (current_notes or "") + "\n\n" + FINAL_SUMMARY
    conn.execute("UPDATE experiments SET notes=?, status=? WHERE experiment_id=?", (new_notes, v["status"], EXPERIMENT_ID))
    conn.commit()

print("\n" + "=" * 100)
print("EXPERIMENT 1 FORMALLY CLOSED. Summary appended to notes field. Status field synced to REJECTED.")
print("=" * 100)
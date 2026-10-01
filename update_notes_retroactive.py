import sqlite3

DB_PATH = "research_database.db"

RETROACTIVE_TAG = "RETROACTIVE BACKFILL: this record was entered after the experiment was already run and results were known -- it does NOT constitute genuine preregistration, despite preregistered_at being populated. Entered solely to verify the database schema could represent real, completed research. "

with sqlite3.connect(DB_PATH) as conn:
    for exp_id in ["phase6_signal_random_control_20260914", "phase7_pnl_concentration_20260914", "full_population_iv_repricing_20260914"]:
        current_notes = conn.execute("SELECT notes FROM experiments WHERE experiment_id=?", (exp_id,)).fetchone()[0]
        new_notes = RETROACTIVE_TAG + (current_notes or "")
        conn.execute("UPDATE experiments SET notes=? WHERE experiment_id=?", (new_notes, exp_id))
    conn.commit()

print("Notes updated for all 3 retroactive records.\n")

with sqlite3.connect(DB_PATH) as conn:
    rows = conn.execute("SELECT experiment_id, notes FROM experiments").fetchall()
    for r in rows:
        print(r[0] + ":")
        print("  " + r[1])
        print()

print("Track 2 Phase A (Research Database) -- COMPLETE.")
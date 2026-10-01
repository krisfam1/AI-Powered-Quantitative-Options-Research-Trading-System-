content = open('execute_ml_experiment1.py', encoding='utf-8').read()
old = 'verdict = run_experiment.run_experiment(EXPERIMENT_ID, run_ml_experiment_1_final, run_reason="fixed categorical encoding bug in spy_trend_state (first attempt crashed before producing any result)")'
new = 'verdict = run_experiment.run_experiment(EXPERIMENT_ID, run_ml_experiment_1_final, run_reason="implemented and included the 3 declared robustness checks (previously missing, causing an incomplete verdict)")'
if old not in content:
    print("Pattern not found -- checking for original unmodified line instead...")
    old2 = 'verdict = run_experiment.run_experiment(EXPERIMENT_ID, run_ml_experiment_1_final)'
    if old2 in content:
        content = content.replace(old2, new, 1)
        open('execute_ml_experiment1.py', 'w', encoding='utf-8').write(content)
        print("Patched (from original line)")
    else:
        print("Neither pattern found -- no changes made.")
else:
    content = content.replace(old, new, 1)
    open('execute_ml_experiment1.py', 'w', encoding='utf-8').write(content)
    print("Patched successfully")
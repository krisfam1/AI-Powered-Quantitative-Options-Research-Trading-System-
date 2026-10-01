content = open('ml_experiment1_final_executor.py', encoding='utf-8').read()

old = '''import pickle
import numpy as np
from scipy import stats as scipy_stats
from ml_experiment1_executor import LOCKED_FEATURES, BASELINE_FEATURE, _fit_ridge_with_validation'''

new = '''import pickle
import numpy as np
from scipy import stats as scipy_stats
from ml_experiment1_executor import LOCKED_FEATURES, BASELINE_FEATURE, _fit_ridge_with_validation
from ml_experiment1_robustness_checks import run_all_robustness_checks'''

if old not in content:
    print("PATCH A not found -- aborting.")
else:
    content = content.replace(old, new, 1)

    old2 = '''    return {
        "gate_results": gate_results,
        "primary_p_value": p_value,'''
    new2 = '''    print("\\nRunning declared robustness checks...")
    robustness_results = run_all_robustness_checks()

    return {
        "gate_results": gate_results,
        "robustness_results": robustness_results,
        "primary_p_value": p_value,'''
    if old2 not in content:
        print("PATCH B not found -- aborting.")
    else:
        content = content.replace(old2, new2, 1)
        with open('ml_experiment1_final_executor.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Integrated robustness checks successfully.")
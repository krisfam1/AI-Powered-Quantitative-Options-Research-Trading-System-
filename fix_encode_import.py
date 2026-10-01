content = open('diagnostic_5bar_vs_20bar.py', encoding='utf-8').read()
old = 'from ml_experiment1_final_executor import _encode_value'
new = 'from ml_experiment1_robustness_checks import _encode_value'
if old not in content:
    print("Pattern not found")
else:
    content = content.replace(old, new, 1)
    open('diagnostic_5bar_vs_20bar.py', 'w', encoding='utf-8').write(content)
    print("Patched successfully")
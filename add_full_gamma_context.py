content = open('options_trade_log.py', encoding='utf-8').read()

old = "                gamma_modifier REAL\n"
new = "                gamma_modifier REAL,\n                gamma_context TEXT\n"

if old not in content:
    print("Could not find target -- no changes made.")
else:
    new_content = content.replace(old, new, 1)
    with open('options_trade_log.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Added gamma_context column to schema.")
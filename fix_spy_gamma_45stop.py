content = open('spy_gamma_daytrader.py', encoding='utf-8').read()

old = "STOP_LOSS_PCT = 0.40\n"
new = "STOP_LOSS_PCT = 0.45\n"

if old not in content:
    print("Could not find target -- no changes made.")
else:
    new_content = content.replace(old, new, 1)
    with open('spy_gamma_daytrader.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Updated stop-loss to 45%.")

lines = open('options_shadow_loop.py', encoding='utf-8').readlines()

old = 'OPTIONS_TICKERS = ["AAPL", "TSLA", "NVDA", "AMD"]\n'
target_index = None
for i, line in enumerate(lines):
    if line == old:
        target_index = i
        break

if target_index is None:
    print("Could not find target line -- no changes made.")
else:
    lines[target_index] = 'from main import LIVE_TICKERS\nOPTIONS_TICKERS = LIVE_TICKERS\n'
    with open('options_shadow_loop.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("Fixed OPTIONS_TICKERS to pull dynamically from main.LIVE_TICKERS.")
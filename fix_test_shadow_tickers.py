content = open('test_options_shadow.py', encoding='utf-8').read()

old = 'from live_options_trader import check_signal_and_trade_options\n\nfor ticker in ["AAPL", "TSLA", "NVDA", "AMD"]:'
new = 'from live_options_trader import check_signal_and_trade_options\nfrom main import LIVE_TICKERS\n\nfor ticker in LIVE_TICKERS:'

if old not in content:
    print("Could not find target -- no changes made.")
else:
    new_content = content.replace(old, new, 1)
    with open('test_options_shadow.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Fixed test_options_shadow.py to use dynamic LIVE_TICKERS.")
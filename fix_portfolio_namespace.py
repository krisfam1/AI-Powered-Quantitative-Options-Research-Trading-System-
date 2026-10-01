content = open('portfolio_backtest.py', encoding='utf-8').read()

old = 'calculate_historical_volatility(bars, index)'
new = 'calculate_historical_volatility(bars, index, cache_namespace="portfolio")'

count = content.count(old)
if count == 0:
    print("Could not find any occurrences of the target call pattern -- no changes made.")
else:
    content = content.replace(old, new)
    with open('portfolio_backtest.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Updated " + str(count) + " call site(s) in portfolio_backtest.py to use cache_namespace='portfolio'.")
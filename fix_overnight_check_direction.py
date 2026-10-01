content = open('overnight_hold_check.py', encoding='utf-8').read()

old_func_sig = 'def check_overnight_hold_safety(ticker: str) -> dict:\n'
new_func_sig = 'def check_overnight_hold_safety(ticker: str, option_type: str = "call") -> dict:\n'

if old_func_sig not in content:
    print("Could not find function signature -- no changes made.")
else:
    content = content.replace(old_func_sig, new_func_sig, 1)
    print("Added option_type parameter.")

old_news_block = '''    try:
        news_start = now - timedelta(hours=24)
        news_items = be.get_news_for_ticker(ticker, news_start, now)
        if not be.check_news_sentiment(news_items, now, lookback_hours=24):
            safe = False
            reasons.append("recent news sentiment is negative")
    except Exception as exc:
        reasons.append("news check unavailable: " + str(exc))'''

new_news_block = '''    try:
        news_start = now - timedelta(hours=24)
        news_items = be.get_news_for_ticker(ticker, news_start, now)
        news_positive_or_neutral = be.check_news_sentiment(news_items, now, lookback_hours=24)

        # Negative news is a real risk for a CALL (bullish bet), but is
        # actually FAVORABLE for a PUT (bearish bet) -- direction matters.
        if option_type == "call" and not news_positive_or_neutral:
            safe = False
            reasons.append("recent news sentiment is negative (risk for a call)")
        elif option_type == "put" and not news_positive_or_neutral:
            reasons.append("recent news sentiment is negative (favorable for this put, not flagged as risk)")
    except Exception as exc:
        reasons.append("news check unavailable: " + str(exc))'''

if old_news_block not in content:
    print("Could not find news block -- no changes made to that part.")
else:
    content = content.replace(old_news_block, new_news_block, 1)
    print("Made news check direction-aware.")

with open('overnight_hold_check.py', 'w', encoding='utf-8') as f:
    f.write(content)
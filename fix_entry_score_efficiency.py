content = open('entry_scorer.py', encoding='utf-8').read()

old_news_func = '''def score_news_sentiment(ticker: str, bars: list, index: int) -> float:
    """0-5 points -- binary for now (non-negative news), reusing existing check."""
    try:
        timestamp = bars[index].timestamp
        news_items = be.get_news_for_ticker(ticker, timestamp - timedelta(hours=24), timestamp)
        if be.check_news_sentiment(news_items, timestamp, lookback_hours=24):
            return 5.0
        return 0.0
    except Exception:
        return 2.5'''

new_news_func = '''_news_cache = {}  # keyed by (ticker, date) -- avoids redundant API calls within the same day


def score_news_sentiment(ticker: str, bars: list, index: int) -> float:
    """0-5 points -- binary for now (non-negative news), cached per ticker per day."""
    try:
        timestamp = bars[index].timestamp
        cache_key = (ticker, timestamp.date())

        if cache_key not in _news_cache:
            news_items = be.get_news_for_ticker(ticker, timestamp - timedelta(hours=24), timestamp)
            _news_cache[cache_key] = news_items
        else:
            news_items = _news_cache[cache_key]

        if be.check_news_sentiment(news_items, timestamp, lookback_hours=24):
            return 5.0
        return 0.0
    except Exception:
        return 2.5'''

if old_news_func not in content:
    print("Could not find news function -- no changes made.")
else:
    content = content.replace(old_news_func, new_news_func, 1)
    print("Added per-ticker-per-day news caching (eliminates redundant API calls).")

    old_calc = '''def calculate_entry_score(ticker: str, bars: list, index: int, direction: str, spy_regime: str = "neutral") -> dict:
    """Combine all factors into a total 0-100 score with a breakdown."""
    scores = {
        "relative_volume": score_relative_volume(bars, index),
        "breakout_magnitude": score_breakout_magnitude(bars, index, direction),
        "trend_strength": score_trend_strength(bars, index, direction),
        "momentum": score_momentum(bars, index, direction),
        "volatility_regime": score_volatility_regime(bars, index),
        "news_sentiment": score_news_sentiment(ticker, bars, index),
        "market_regime_alignment": score_market_regime_alignment(direction, spy_regime),
    }
    total = sum(scores.values())
    return {"total_score": round(total, 1), "breakdown": scores}'''

    new_calc = '''def calculate_entry_score(ticker: str, bars: list, index: int, direction: str, spy_regime: str = "neutral") -> dict:
    """Combine all factors into a total 0-100 score with a breakdown."""
    rv_score = score_relative_volume(bars, index)
    breakout_score = score_breakout_magnitude(bars, index, direction)

    if rv_score + breakout_score < 5:
        return {
            "total_score": round(rv_score + breakout_score, 1),
            "breakdown": {
                "relative_volume": rv_score, "breakout_magnitude": breakout_score,
                "trend_strength": 0.0, "momentum": 0.0, "volatility_regime": 0.0,
                "news_sentiment": 0.0, "market_regime_alignment": 0.0,
            },
        }

    scores = {
        "relative_volume": rv_score,
        "breakout_magnitude": breakout_score,
        "trend_strength": score_trend_strength(bars, index, direction),
        "momentum": score_momentum(bars, index, direction),
        "volatility_regime": score_volatility_regime(bars, index),
        "news_sentiment": score_news_sentiment(ticker, bars, index),
        "market_regime_alignment": score_market_regime_alignment(direction, spy_regime),
    }
    total = sum(scores.values())
    return {"total_score": round(total, 1), "breakdown": scores}'''

    if old_calc not in content:
        print("Could not find calculate_entry_score -- no changes made to that part.")
    else:
        content = content.replace(old_calc, new_calc, 1)
        print("Added lightweight short-circuit for clearly non-viable bars.")

    with open('entry_scorer.py', 'w', encoding='utf-8') as f:
        f.write(content)
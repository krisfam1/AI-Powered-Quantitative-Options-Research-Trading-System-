content = open('options_backtest_engine.py', encoding='utf-8').read()

old = '''def _vol_cache_key(bars: list):
    """Content-based cache key -- avoids the real risk of Python's id()
    being reused after garbage collection, which could silently return
    a completely wrong, stale cached series for a different bars list."""
    if not bars:
        return None
    return (bars[0].timestamp, bars[-1].timestamp, len(bars))'''

new = '''def _vol_cache_key(bars: list, cache_namespace: str = "default"):
    """Content-based cache key -- avoids the real risk of Python's id()
    being reused after garbage collection, which could silently return
    a completely wrong, stale cached series for a different bars list.

    HONEST FIX: now includes cache_namespace, so different engines
    (e.g. the original engine vs. the portfolio engine) never share a
    cache entry even when computing on identical bars data. This closes
    a real cross-engine isolation gap discovered during the 11-vs-30
    forensic investigation -- confirmed NOT the cause of that specific
    discrepancy (which was a date-window artifact), but a real,
    separate isolation flaw worth fixing before trusting any future
    cross-engine comparison."""
    if not bars:
        return None
    return (cache_namespace, bars[0].timestamp, bars[-1].timestamp, len(bars))'''

if old not in content:
    print("Could not find target (_vol_cache_key) -- no changes made.")
else:
    content = content.replace(old, new, 1)

    old2 = '''def calculate_historical_volatility(bars: list, current_index: int, lookback: int = 60) -> float:
    """
    Estimate volatility using the validated hybrid methodology (see
    _precompute_hybrid_volatility_series docstring for full detail and
    validation results). SYNTHETIC ESTIMATE, not real market IV -- see
    Advanced_Options_System_Roadmap.md.

    Signature unchanged from the prior implementation so every existing
    call site continues to work without modification. The `lookback`
    parameter is accepted for backward compatibility but is not used by
    the new methodology, which uses a fixed 20-trading-day daily-bar
    window internally instead.
    """
    key = _vol_cache_key(bars)
    if key not in _volatility_series_cache:
        _volatility_series_cache[key] = _precompute_hybrid_volatility_series(bars)

    series = _volatility_series_cache[key]
    if current_index < len(series):
        return series[current_index]
    return 0.30'''

    new2 = '''def calculate_historical_volatility(bars: list, current_index: int, lookback: int = 60, cache_namespace: str = "default") -> float:
    """
    Estimate volatility using the validated hybrid methodology (see
    _precompute_hybrid_volatility_series docstring for full detail and
    validation results). SYNTHETIC ESTIMATE, not real market IV -- see
    Advanced_Options_System_Roadmap.md.

    Signature backward-compatible: existing call sites (which don't
    pass cache_namespace) continue to use "default" unchanged. The
    `lookback` parameter is accepted for backward compatibility but is
    not used by the new methodology, which uses a fixed 20-trading-day
    daily-bar window internally instead.

    cache_namespace: pass a distinct value (e.g. "portfolio") from a
    different engine to guarantee true cache isolation, even when both
    engines compute on identical bars data.
    """
    key = _vol_cache_key(bars, cache_namespace)
    if key not in _volatility_series_cache:
        _volatility_series_cache[key] = _precompute_hybrid_volatility_series(bars)

    series = _volatility_series_cache[key]
    if current_index < len(series):
        return series[current_index]
    return 0.30'''

    if old2 not in content:
        print("Could not find target (calculate_historical_volatility) -- no changes made to that function.")
    else:
        content = content.replace(old2, new2, 1)
        with open('options_backtest_engine.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Cache-isolation fix applied: calculate_historical_volatility now supports cache_namespace.")
content = open('data_prep_experiment1.py', encoding='utf-8').read()

old = '''    if iv_result and realized_vol:
        row["iv_vs_realized_vol"] = iv_vs_realized_vol(bars, index, iv_result["iv"])
        row["iv_snapshot_date"] = iv_result["snapshot_date"]
    else:
        row["iv_vs_realized_vol"] = None
        row["iv_snapshot_date"] = None

    # iv_percentile requires a historical IV series -- built from the T-1 IV
    # at each of the prior ~30 real trading days for this ticker/strike (a
    # bounded, real lookback; not an unlimited or speculative query).
    row["iv_percentile"] = None  # computed in a separate batched pass (see build_iv_percentile_series)'''

new = '''    if iv_result and realized_vol:
        row["iv_vs_realized_vol"] = iv_vs_realized_vol(bars, index, iv_result["iv"])
        row["iv_snapshot_date"] = iv_result["snapshot_date"]
        row["raw_current_iv"] = iv_result["iv"]
    else:
        row["iv_vs_realized_vol"] = None
        row["iv_snapshot_date"] = None
        row["raw_current_iv"] = None

    # iv_percentile is filled in by a SEPARATE batch pass (fill_iv_percentile_column,
    # below) AFTER all rows for a ticker exist.
    row["iv_percentile"] = None'''

if old not in content:
    print("Pattern not found -- no changes made.")
else:
    content = content.replace(old, new, 1)

    integration_fn = '''

def fill_iv_percentile_column(rows_for_ticker, ticker_iv_series):
    """
    INTEGRATION step: fills in row["iv_percentile"] for every row of a
    single ticker, using that ticker's cached IV series and each row's
    own raw_current_iv. Mutates rows_for_ticker in place; returns it.
    """
    from iv_percentile_batch import compute_iv_percentile_for_observation
    for row in rows_for_ticker:
        if row.get("raw_current_iv") is None:
            continue
        signal_date = row["signal_timestamp"][:10]
        from datetime import date as _date
        obs_date = _date.fromisoformat(signal_date)
        row["iv_percentile"] = compute_iv_percentile_for_observation(obs_date, row["raw_current_iv"], ticker_iv_series)
    return rows_for_ticker
'''
    content = content + integration_fn

    open('data_prep_experiment1.py', 'w', encoding='utf-8').write(content)
    print("Patched successfully")
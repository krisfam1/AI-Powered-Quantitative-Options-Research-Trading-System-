content = open('combined_iv_spread_correction.py', encoding='utf-8').read()

old = '''def fetch_exact_contract_quote(ticker, quote_date, strike, exp_date):
    """Fetches REAL bid/ask for the EXACT strike+expiry V1 actually used, on a specific quote_date."""
    params = {
        "filter[underlying_symbol]": ticker, "filter[tradetime_from]": quote_date.isoformat(), "filter[tradetime_to]": quote_date.isoformat(),
        "filter[exp_date_from]": exp_date.isoformat(), "filter[exp_date_to]": exp_date.isoformat(),
        "api_token": EODHD_API_TOKEN, "page[limit]": 1000,
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=60)
        resp.raise_for_status()
        records = [r["attributes"] for r in resp.json().get("data", []) if r["attributes"].get("type") == "call"]
    except Exception:
        return None
    exact = [r for r in records if r.get("strike") == strike]
    if not exact:
        return None
    return exact[0]'''

new = '''def fetch_exact_contract_quote(ticker, quote_date, strike, exp_date):
    """
    Fetches REAL bid/ask for the same expiry V1 actually used, snapping
    to the NEAREST real, exchange-listed strike -- V1's synthetic
    backtest computes strike via continuous delta-solving (e.g. 277.34),
    which essentially never matches a real, discretely-spaced listed
    strike exactly. This mirrors the already-validated nearest-strike
    approach used successfully elsewhere tonight (251/251, 580/580).
    """
    params = {
        "filter[underlying_symbol]": ticker, "filter[tradetime_from]": quote_date.isoformat(), "filter[tradetime_to]": quote_date.isoformat(),
        "filter[exp_date_from]": exp_date.isoformat(), "filter[exp_date_to]": exp_date.isoformat(),
        "api_token": EODHD_API_TOKEN, "page[limit]": 1000,
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=60)
        resp.raise_for_status()
        records = [r["attributes"] for r in resp.json().get("data", []) if r["attributes"].get("type") == "call"]
    except Exception:
        return None
    if not records:
        return None
    nearest = min(records, key=lambda r: abs(r.get("strike", 1e9) - strike))
    return nearest'''

if old not in content:
    print("Pattern not found -- no changes made.")
else:
    content = content.replace(old, new, 1)
    open('combined_iv_spread_correction.py', 'w', encoding='utf-8').write(content)
    print("Patched successfully -- now snaps to nearest real listed strike.")
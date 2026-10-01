content = open('portfolio_backtest.py', encoding='utf-8').read()

# --- PATCH 3: add the day-level-cached checkpoint helper, right after the imports ---
old3 = '''from v2_iv_pricing_model import get_v2_entry_iv'''

new3 = '''from v2_iv_pricing_model import get_v2_entry_iv, get_v2_checkpoint_iv


def _get_v2_checkpoint_vol(meta, ticker, timestamp):
    """
    Day-level-cached checkpoint IV lookup for pricing_mode='v2_corrected'.
    Fetches fresh IV only once per calendar day per position; reuses the
    cached value for all bars within that day. If a genuine gap occurs
    (exact-contract IV unavailable at this checkpoint), carries forward
    the last known v2 IV as an EXPLICITLY LOGGED, visible measure --
    never a silent fallback to V1 volatility, never fabricated.
    """
    current_date = timestamp.date()
    if meta.get("v2_last_checkpoint_date") == current_date:
        return meta["v2_last_iv"]

    result = get_v2_checkpoint_iv(ticker, meta["v2_contract"], meta["v2_exp_date_str"], current_date)
    if result is not None:
        meta["v2_last_checkpoint_date"] = current_date
        meta["v2_last_iv"] = result["iv"]
        return result["iv"]
    else:
        meta["v2_checkpoint_gaps"] = meta.get("v2_checkpoint_gaps", 0) + 1
        return meta["v2_last_iv"]'''

if old3 not in content:
    print("PATCH 3 pattern not found -- aborting, no changes made.")
    exit()
content = content.replace(old3, new3, 1)

# --- PATCH 4: exit-check valuation (first checkpoint location) ---
old4 = '''            vol = calculate_historical_volatility(bars, index, cache_namespace="portfolio")
            current_option_value = black_scholes_price(current_price, meta["strike"], max(days_left, 0), vol, option_type=meta["option_type"])'''

new4 = '''            vol = calculate_historical_volatility(bars, index, cache_namespace="portfolio")
            if pricing_mode == "v2_corrected" and "v2_contract" in meta:
                vol = _get_v2_checkpoint_vol(meta, ticker, timestamp)
            current_option_value = black_scholes_price(current_price, meta["strike"], max(days_left, 0), vol, option_type=meta["option_type"])'''

if old4 not in content:
    print("PATCH 4 pattern not found -- aborting, no changes made (patch 3 was already applied, file may be partially modified -- review before retrying).")
    exit()
content = content.replace(old4, new4, 1)

# --- PATCH 5: mark-to-market valuation (second checkpoint location) ---
old5 = '''                vol = calculate_historical_volatility(bars, index, cache_namespace="portfolio")
                val = black_scholes_price(current_price, meta["strike"], max(days_left, 0), vol, option_type=meta["option_type"])'''

new5 = '''                vol = calculate_historical_volatility(bars, index, cache_namespace="portfolio")
                if pricing_mode == "v2_corrected" and "v2_contract" in meta:
                    vol = _get_v2_checkpoint_vol(meta, ticker, timestamp)
                val = black_scholes_price(current_price, meta["strike"], max(days_left, 0), vol, option_type=meta["option_type"])'''

if old5 not in content:
    print("PATCH 5 pattern not found -- aborting, no changes made (patches 3-4 were already applied, file may be partially modified -- review before retrying).")
    exit()
content = content.replace(old5, new5, 1)

with open('portfolio_backtest.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("PATCH 3, 4, and 5 applied successfully.")
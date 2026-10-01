content = open('spy_gamma_execution.py', encoding='utf-8').read()

old_import = "import options_trade_log\nfrom zoneinfo import ZoneInfo\nfrom trade_reviewer import review_and_store_trade\n"
new_import = old_import + "import json\n"

if old_import not in content:
    print("Could not find import line -- no changes made.")
else:
    content = content.replace(old_import, new_import, 1)
    print("Added json import.")

    old = '''        options_trade_log.log_entry({
            "trade_id": trade_id,
            "ticker": ticker,
            "contract_symbol": best.symbol,
            "option_type": option_type,
            "entry_date": datetime.now(timezone.utc).date().isoformat(),
            "entry_premium": real_entry_premium,
            "contracts": tranche_contracts,
            "stop_loss_pct": _sl,
            "take_profit_pct": _tp,
            "expiry_date": best.expiration_date.isoformat(),
        })'''

    new = '''        _gamma_context = {
            "regime": signal.get("regime"),
            "wall_price": signal.get("wall_price"),
            "current_price_at_entry": current_price,
            "confluence_bonuses": signal.get("confluence_bonuses", []),
            "tranche": tranche_name,
        }
        options_trade_log.log_entry({
            "trade_id": trade_id,
            "ticker": ticker,
            "contract_symbol": best.symbol,
            "option_type": option_type,
            "entry_date": datetime.now(timezone.utc).date().isoformat(),
            "entry_premium": real_entry_premium,
            "contracts": tranche_contracts,
            "stop_loss_pct": _sl,
            "take_profit_pct": _tp,
            "expiry_date": best.expiration_date.isoformat(),
            "gamma_context": json.dumps(_gamma_context),
        })'''

    if old not in content:
        print("Could not find target -- no changes made to that part.")
    else:
        content = content.replace(old, new, 1)
        print("Added rich gamma context capture for each SPY gamma trade.")

    with open('spy_gamma_execution.py', 'w', encoding='utf-8') as f:
        f.write(content)
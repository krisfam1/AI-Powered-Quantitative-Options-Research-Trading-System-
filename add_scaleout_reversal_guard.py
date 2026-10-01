content = open('spy_gamma_execution.py', encoding='utf-8').read()

# 1. Update constants: 45% stop, tranche structure
old_constants_marker = "from options_data import get_options_chain, filter_near_the_money, pick_best_contract\n"
new_constants_marker = old_constants_marker
content = content.replace(old_constants_marker, new_constants_marker, 1)

# 2. Replace the whole entry function to build 3 tranches instead of one position
old_entry_func_tail = '''    if spy_gamma_daytrader.SPY_GAMMA_SHADOW_MODE:
        note = "SHADOW MODE -- would buy " + str(contracts) + "x " + best.symbol + " @ ~$" + str(round(premium, 2)) + " | " + signal["note"]
        return {"signal_fired": True, "executed": False, "note": note}

    order_request = OptMarketOrderRequest(
        symbol=best.symbol, qty=contracts, side=OptOrderSide.BUY, time_in_force=OptTimeInForce.DAY,
    )
    order = _trading_client.submit_order(order_request)

    real_entry_premium = premium
    for _ in range(10):
        time.sleep(1)
        try:
            refreshed = _trading_client.get_order_by_id(order.id)
            if refreshed.filled_avg_price:
                real_entry_premium = float(refreshed.filled_avg_price)
                break
        except Exception:
            continue

    trade_id = "spy-gamma-" + str(order.id)
    options_trade_log.log_entry({
        "trade_id": trade_id,
        "ticker": ticker,
        "contract_symbol": best.symbol,
        "option_type": option_type,
        "entry_date": datetime.now(timezone.utc).date().isoformat(),
        "entry_premium": real_entry_premium,
        "contracts": contracts,
        "stop_loss_pct": STOP_LOSS_PCT,
        "take_profit_pct": TAKE_PROFIT_PCT,
        "expiry_date": best.expiration_date.isoformat(),
    })

    return {"signal_fired": True, "executed": True, "trade_id": trade_id, "note": "LIVE order placed: " + str(contracts) + "x " + best.symbol + " @ $" + str(real_entry_premium)}'''

new_entry_func_tail = '''    if spy_gamma_daytrader.SPY_GAMMA_SHADOW_MODE:
        _tranches_preview = _build_tranches(contracts)
        note = "SHADOW MODE -- would buy " + str(contracts) + "x " + best.symbol + " @ ~$" + str(round(premium, 2)) + " split into tranches " + str(_tranches_preview) + " | " + signal["note"]
        return {"signal_fired": True, "executed": False, "note": note}

    order_request = OptMarketOrderRequest(
        symbol=best.symbol, qty=contracts, side=OptOrderSide.BUY, time_in_force=OptTimeInForce.DAY,
    )
    order = _trading_client.submit_order(order_request)

    real_entry_premium = premium
    for _ in range(10):
        time.sleep(1)
        try:
            refreshed = _trading_client.get_order_by_id(order.id)
            if refreshed.filled_avg_price:
                real_entry_premium = float(refreshed.filled_avg_price)
                break
        except Exception:
            continue

    # Split into scale-out tranches: A (40% target), B (75% target),
    # RUNNER (reversal_guard, looser 50% threshold, no fixed cap).
    # Each tranche is logged as its own trade for independent tracking.
    tranche_plan = _build_tranches(contracts)
    trade_ids = []
    for tranche_name, tranche_contracts in tranche_plan.items():
        if tranche_contracts <= 0:
            continue
        trade_id = "spy-gamma-" + tranche_name + "-" + str(order.id)
        if tranche_name == "A":
            _tp, _sl = 0.40, STOP_LOSS_PCT
        elif tranche_name == "B":
            _tp, _sl = 0.75, STOP_LOSS_PCT
        else:  # RUNNER
            _tp, _sl = 999.0, STOP_LOSS_PCT  # no fixed cap -- reversal_guard handles the exit
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
        })
        trade_ids.append(trade_id)

    return {"signal_fired": True, "executed": True, "trade_ids": trade_ids, "note": "LIVE order placed: " + str(contracts) + "x " + best.symbol + " @ $" + str(real_entry_premium) + " split into tranches " + str(tranche_plan)}


def _build_tranches(total_contracts: int) -> dict:
    """
    Split total contracts into 3 scale-out tranches: A (~25%, 40% target),
    B (~25%, 75% target), RUNNER (~50%, reversal_guard, no fixed cap).
    Falls back to a single RUNNER-only position if too few contracts to
    meaningfully split (fewer than 4).
    """
    if total_contracts < 4:
        return {"A": 0, "B": 0, "RUNNER": total_contracts}

    a = max(int(total_contracts * 0.25), 1)
    b = max(int(total_contracts * 0.25), 1)
    runner = total_contracts - a - b
    return {"A": a, "B": b, "RUNNER": runner}'''

if old_entry_func_tail not in content:
    print("Could not find entry function tail -- no changes made.")
else:
    content = content.replace(old_entry_func_tail, new_entry_func_tail, 1)
    print("Added scale-out tranche logic to entry.")

with open('spy_gamma_execution.py', 'w', encoding='utf-8') as f:
    f.write(content)
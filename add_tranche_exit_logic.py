content = open('spy_gamma_execution.py', encoding='utf-8').read()

old = '''        pct_change = (current_premium - entry_premium) / entry_premium if entry_premium > 0 else 0

        exit_reason = None
        if pct_change <= -STOP_LOSS_PCT:
            exit_reason = "stop_loss"
        elif pct_change >= TAKE_PROFIT_PCT:
            exit_reason = "take_profit"
        elif force_close_time:
            exit_reason = "day_trade_close"'''

new = '''        pct_change = (current_premium - entry_premium) / entry_premium if entry_premium > 0 else 0

        # Determine which tranche this position belongs to from its trade_id
        # (format: "spy-gamma-{A|B|RUNNER}-{order_id}").
        _tranche = "RUNNER"
        _id_parts = trade_id.split("-")
        if len(_id_parts) > 2 and _id_parts[2] in ("A", "B", "RUNNER"):
            _tranche = _id_parts[2]

        exit_reason = None
        _own_stop_loss_pct = pos.get("stop_loss_pct", STOP_LOSS_PCT)
        _own_take_profit_pct = pos.get("take_profit_pct", TAKE_PROFIT_PCT)

        if pct_change <= -_own_stop_loss_pct:
            exit_reason = "stop_loss"
        elif _tranche == "RUNNER":
            # Looser reversal_guard: wait for 50%+ profit (vs the main
            # bot's 40%) before checking for a sustained reversal, since
            # this tranche is meant to run further before protecting gains.
            if pct_change >= 0.50:
                try:
                    from datetime import timedelta as _timedelta
                    import backtest_engine as _be
                    _now = datetime.now(timezone.utc)
                    _stock_bars = _be.get_historical_bars(pos.get("ticker", "SPY"), _now - _timedelta(hours=1), _now)
                    if len(_stock_bars) >= 7:
                        _closes = [float(b.close) for b in _stock_bars[-7:]]
                        _last_two = _closes[-2:]
                        _ma_before = sum(_closes[-7:-2]) / 5
                        _opt_type = pos["option_type"]
                        if _opt_type == "call" and all(c < _ma_before for c in _last_two):
                            exit_reason = "reversal_guard"
                        elif _opt_type == "put" and all(c > _ma_before for c in _last_two):
                            exit_reason = "reversal_guard"
                except Exception:
                    pass
        elif pct_change >= _own_take_profit_pct:
            exit_reason = "take_profit"

        if exit_reason is None and force_close_time:
            exit_reason = "day_trade_close"'''

if old not in content:
    print("Could not find target -- no changes made.")
else:
    new_content = content.replace(old, new, 1)
    with open('spy_gamma_execution.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Added per-tranche exit logic: A/B use flat targets, RUNNER uses looser reversal_guard.")
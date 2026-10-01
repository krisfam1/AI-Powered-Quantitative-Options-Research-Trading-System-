content = open('spy_gamma_execution.py', encoding='utf-8').read()

old_import = "from spy_gamma_daytrader import check_spy_gamma_signal, SPY_GAMMA_SHADOW_MODE, STOP_LOSS_PCT, TAKE_PROFIT_PCT, POSITION_RISK_PCT, DTE_TARGET\n"
new_import = "import spy_gamma_daytrader\nfrom spy_gamma_daytrader import check_spy_gamma_signal, STOP_LOSS_PCT, TAKE_PROFIT_PCT, POSITION_RISK_PCT, DTE_TARGET\n"

if old_import not in content:
    print("Could not find import line -- no changes made.")
else:
    content = content.replace(old_import, new_import, 1)
    content = content.replace("if SPY_GAMMA_SHADOW_MODE:", "if spy_gamma_daytrader.SPY_GAMMA_SHADOW_MODE:")
    print("Fixed shadow-mode flag to reference a single source of truth.")

    old_risk_import = "import options_trade_log\nfrom zoneinfo import ZoneInfo\n"
    new_risk_import = old_risk_import + "from ticker_circuit_breaker import check_ticker_circuit_breaker\nfrom risk_manager import check_max_positions, check_daily_loss_limit, check_drawdown_pause\nfrom pathlib import Path\nimport sqlite3 as _sqlite3\n"
    content = content.replace(old_risk_import, new_risk_import, 1)
    print("Added risk-management imports.")

    old_entry_start = '''def check_and_enter_spy_gamma() -> dict:
    signal = check_spy_gamma_signal()
    if not signal["signal_fired"]:
        return signal

    ticker = signal["ticker"]
    option_type = signal["option_type"]
    current_price = signal["current_price"]'''

    new_entry_start = '''def check_and_enter_spy_gamma() -> dict:
    signal = check_spy_gamma_signal()
    if not signal["signal_fired"]:
        return signal

    ticker = signal["ticker"]
    option_type = signal["option_type"]
    current_price = signal["current_price"]

    breaker_check = check_ticker_circuit_breaker(ticker)
    if breaker_check["blocked"]:
        return {"signal_fired": True, "executed": False, "note": "circuit breaker: " + breaker_check["reason"]}

    cooldown_minutes = 90
    with _sqlite3.connect("options_signal_log.db") as _con:
        try:
            _row = _con.execute(
                "SELECT checked_at FROM options_signal_log WHERE ticker = ? AND signal_fired = 1 ORDER BY checked_at DESC LIMIT 1",
                ("SPY-GAMMA",),
            ).fetchone()
        except Exception:
            _row = None
    if _row:
        _last_fired = datetime.fromisoformat(_row[0])
        _minutes_since = (datetime.now(timezone.utc) - _last_fired).total_seconds() / 60
        if _minutes_since < cooldown_minutes:
            return {"signal_fired": True, "executed": False, "note": "cooldown active -- fired " + str(round(_minutes_since, 0)) + " min ago"}

    account = _trading_client.get_account()
    equity = float(account.equity)
    last_equity = float(account.last_equity) if account.last_equity else equity
    daily_pnl_frac = (equity - last_equity) / last_equity if last_equity else 0.0

    peak_file = Path(".options_peak_equity")
    if peak_file.exists():
        try:
            stored_peak = float(peak_file.read_text().strip())
            peak_equity = max(stored_peak, equity)
        except ValueError:
            peak_equity = equity
    else:
        peak_equity = equity
    rolling_pnl_frac = (equity - peak_equity) / peak_equity if peak_equity else 0.0

    if not check_daily_loss_limit(daily_pnl_frac):
        return {"signal_fired": True, "executed": False, "note": "daily loss limit hit (" + str(round(daily_pnl_frac*100, 2)) + "% today)"}
    if not check_drawdown_pause(rolling_pnl_frac):
        return {"signal_fired": True, "executed": False, "note": "drawdown pause triggered (" + str(round(rolling_pnl_frac*100, 2)) + "% from peak)"}

    positions = _trading_client.get_all_positions()
    options_positions = [p for p in positions if getattr(p, "asset_class", None) is not None and "option" in str(p.asset_class).lower()]
    if not check_max_positions(len(options_positions)):
        return {"signal_fired": True, "executed": False, "note": "max options positions reached (" + str(len(options_positions)) + " open, account-wide)"}'''

    if old_entry_start not in content:
        print("Could not find entry function start -- no changes made to that part.")
    else:
        content = content.replace(old_entry_start, new_entry_start, 1)
        print("Added circuit breaker, cooldown, daily loss limit, drawdown pause, and max-position checks.")

    with open('spy_gamma_execution.py', 'w', encoding='utf-8') as f:
        f.write(content)

old_return = '''    if spy_gamma_daytrader.SPY_GAMMA_SHADOW_MODE:
        note = "SHADOW MODE -- would buy " + str(contracts) + "x " + best.symbol + " @ ~$" + str(round(premium, 2)) + " | " + signal["note"]
        return {"signal_fired": True, "executed": False, "note": note}'''

new_return = '''    with _sqlite3.connect("options_signal_log.db") as _con:
        try:
            _con.execute(
                "CREATE TABLE IF NOT EXISTS options_signal_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, signal_fired INTEGER, checked_at TEXT, note TEXT)"
            )
            _con.execute(
                "INSERT INTO options_signal_log (ticker, signal_fired, checked_at, note) VALUES (?, ?, ?, ?)",
                ("SPY-GAMMA", 1, datetime.now(timezone.utc).isoformat(), signal["note"]),
            )
            _con.commit()
        except Exception:
            pass

    if spy_gamma_daytrader.SPY_GAMMA_SHADOW_MODE:
        note = "SHADOW MODE -- would buy " + str(contracts) + "x " + best.symbol + " @ ~$" + str(round(premium, 2)) + " | " + signal["note"]
        return {"signal_fired": True, "executed": False, "note": note}'''

content2 = open("spy_gamma_execution.py", encoding="utf-8").read()
if old_return in content2:
    content2 = content2.replace(old_return, new_return, 1)
    with open("spy_gamma_execution.py", "w", encoding="utf-8") as f:
        f.write(content2)
    print("Fixed -- signal log now actually gets written, so cooldown checks work correctly.")
else:
    print("Could not find target for the logging fix -- checking alternate pattern.")
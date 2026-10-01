content = open('live_options_trader.py', encoding='utf-8').read()

old_import = "from options_confluence_modifier import calculate_size_modifier\n"
new_import = "from options_confluence_modifier import calculate_size_modifier\nfrom gamma_regime import calculate_net_gamma_regime\nfrom gamma_landscape import build_gamma_landscape, find_gamma_walls\nimport json\n"

if old_import not in content:
    print("Could not find import line -- no changes made.")
else:
    content = content.replace(old_import, new_import, 1)
    print("Added imports.")

    old = '''            _safe_gamma_modifier = gamma_check.get("modifier") if "gamma_check" in locals() else None
            options_trade_log.log_entry({'''

    new = '''            _safe_gamma_modifier = gamma_check.get("modifier") if "gamma_check" in locals() else None

            _gamma_context = {}
            try:
                _regime_result = calculate_net_gamma_regime(ticker, current_price)
                _gamma_context["regime"] = _regime_result["regime"]
                _gamma_context["net_gamma_exposure"] = _regime_result["net_gamma_exposure"]
            except Exception:
                _gamma_context["regime"] = "unavailable"

            try:
                _landscape = build_gamma_landscape(ticker, current_price)
                _walls = find_gamma_walls(_landscape, top_n=1)
                if _walls:
                    _nearest_wall = _walls[0]["strike"]
                    _gamma_context["nearest_wall"] = _nearest_wall
                    _gamma_context["wall_distance_pct"] = round(abs(_nearest_wall - current_price) / current_price * 100, 2)
            except Exception:
                pass

            _gamma_context["estimated_volatility"] = round(vol, 4) if "vol" in locals() else None
            _gamma_context_json = json.dumps(_gamma_context)

            options_trade_log.log_entry({'''

    if old not in content:
        print("Could not find target -- no changes made to that part.")
    else:
        content = content.replace(old, new, 1)
        print("Added full gamma context capture.")

        old_field = '                "gamma_modifier": _safe_gamma_modifier,\n'
        new_field = '                "gamma_modifier": _safe_gamma_modifier,\n                "gamma_context": _gamma_context_json,\n'
        content = content.replace(old_field, new_field, 1)
        print("Added gamma_context to the logged fields.")

    with open('live_options_trader.py', 'w', encoding='utf-8') as f:
        f.write(content)
content = open('v2_iv_pricing_model.py', encoding='utf-8').read()

old = '''    resp = requests.get(BASE_URL, params=params, timeout=60)
    resp.raise_for_status()
    records = resp.json().get("data", [])
    for r in records:
        a = r.get("attributes", {})
        if a.get("contract") != contract_symbol:
            continue
        parts = r.get("id", "").split("-", 1)
        if len(parts) != 2:
            continue
        try:
            id_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
        except ValueError:
            continue
        if id_date != obs_date:
            continue
        if a.get("volatility") is None:
            return None
        return {"iv": a["volatility"], "snapshot_date": date_str}
    return None'''

new = '''    import time
    resp = None
    for attempt in range(3):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=60)
            resp.raise_for_status()
            break
        except requests.exceptions.RequestException:
            if attempt == 2:
                raise
            time.sleep(2)

    records = resp.json().get("data", [])
    for r in records:
        a = r.get("attributes", {})
        if a.get("contract") != contract_symbol:
            continue
        parts = r.get("id", "").split("-", 1)
        if len(parts) != 2:
            continue
        try:
            id_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
        except ValueError:
            continue
        if id_date != obs_date:
            continue
        if a.get("volatility") is None:
            return None
        return {"iv": a["volatility"], "snapshot_date": date_str}
    return None'''

if old not in content:
    print("Pattern not found -- no changes made.")
else:
    content = content.replace(old, new, 1)
    with open('v2_iv_pricing_model.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Retry logic added to get_v2_checkpoint_iv.")
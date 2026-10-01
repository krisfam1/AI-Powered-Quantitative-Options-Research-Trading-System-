content = open('reversal_detector.py', encoding='utf-8').read()

old = '''    closes = [float(b.close) for b in bars[-6:]]
    short_ma = sum(closes[:-1]) / 5  # average of the 5 bars before the current one
    current_price = closes[-1]

    if option_type == "call":
        # A call wants the stock going UP -- reversal = price crossing BELOW the short MA
        if current_price < short_ma:
            return {
                "reversal_detected": True,
                "reason": ticker + " price ($" + str(round(current_price, 2)) + ") crossed below its 5-bar average ($" + str(round(short_ma, 2)) + ") while position is +" + str(round(profit_pct * 100, 1)) + "% -- possible reversal",
            }
    else:  # put
        # A put wants the stock going DOWN -- reversal = price crossing ABOVE the short MA
        if current_price > short_ma:
            return {
                "reversal_detected": True,
                "reason": ticker + " price ($" + str(round(current_price, 2)) + ") crossed above its 5-bar average ($" + str(round(short_ma, 2)) + ") while position is +" + str(round(profit_pct * 100, 1)) + "% -- possible reversal",
            }

    return {"reversal_detected": False, "reason": "no reversal signal detected"}'''

new = '''    closes = [float(b.close) for b in bars]

    # Require SUSTAINED confirmation (last 2 bars both against the position),
    # not a single-bar blip -- reduces false positives from normal noise
    # that could otherwise cut a genuine big winner short prematurely.
    last_two = closes[-2:]
    ma_before_last_two = sum(closes[-7:-2]) / 5

    if option_type == "call":
        if all(c < ma_before_last_two for c in last_two):
            return {
                "reversal_detected": True,
                "reason": ticker + " price held below its 5-bar average ($" + str(round(ma_before_last_two, 2)) + ") for 2 consecutive bars while position is +" + str(round(profit_pct * 100, 1)) + "% -- sustained reversal signal",
            }
    else:
        if all(c > ma_before_last_two for c in last_two):
            return {
                "reversal_detected": True,
                "reason": ticker + " price held above its 5-bar average ($" + str(round(ma_before_last_two, 2)) + ") for 2 consecutive bars while position is +" + str(round(profit_pct * 100, 1)) + "% -- sustained reversal signal",
            }

    return {"reversal_detected": False, "reason": "no sustained reversal signal detected"}'''

if old not in content:
    print("Could not find target -- no changes made.")
else:
    new_content = content.replace(old, new, 1)
    with open('reversal_detector.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Refined to require 2-bar sustained confirmation, reducing false positives.")

old_bars_check = "    if len(bars) < 6:\n        return {\"reversal_detected\": False, \"reason\": \"not enough recent bars to evaluate\"}\n"
new_bars_check = "    if len(bars) < 7:\n        return {\"reversal_detected\": False, \"reason\": \"not enough recent bars to evaluate\"}\n"

content2 = open("reversal_detector.py", encoding="utf-8").read()
if old_bars_check in content2:
    content2 = content2.replace(old_bars_check, new_bars_check, 1)
    with open("reversal_detector.py", "w", encoding="utf-8") as f:
        f.write(content2)
    print("Also fixed minimum bars check to require 7.")
else:
    print("Could not find bars-check target.")
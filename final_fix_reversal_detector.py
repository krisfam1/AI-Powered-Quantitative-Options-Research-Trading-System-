lines = open('reversal_detector.py', encoding='utf-8').readlines()

expected_first = "    closes = [float(b.close) for b in bars[-6:]]\n"
expected_last = "    return {\"reversal_detected\": False, \"reason\": \"no reversal signal detected\"}\n"

if lines[37] != expected_first or lines[54] != expected_last:
    print("Line positions don't match expected -- aborting to avoid corrupting the file.")
    print("Line 38: " + repr(lines[37]))
    print("Line 55: " + repr(lines[54]))
else:
    new_block = [
        "    closes = [float(b.close) for b in bars]\n",
        "\n",
        "    last_two = closes[-2:]\n",
        "    ma_before_last_two = sum(closes[-7:-2]) / 5\n",
        "\n",
        "    if option_type == \"call\":\n",
        "        if all(c < ma_before_last_two for c in last_two):\n",
        "            return {\n",
        "                \"reversal_detected\": True,\n",
        "                \"reason\": ticker + \" price held below its 5-bar average ($\" + str(round(ma_before_last_two, 2)) + \") for 2 consecutive bars while position is +\" + str(round(profit_pct * 100, 1)) + \"% -- sustained reversal signal\",\n",
        "            }\n",
        "    else:\n",
        "        if all(c > ma_before_last_two for c in last_two):\n",
        "            return {\n",
        "                \"reversal_detected\": True,\n",
        "                \"reason\": ticker + \" price held above its 5-bar average ($\" + str(round(ma_before_last_two, 2)) + \") for 2 consecutive bars while position is +\" + str(round(profit_pct * 100, 1)) + \"% -- sustained reversal signal\",\n",
        "            }\n",
        "\n",
        "    return {\"reversal_detected\": False, \"reason\": \"no sustained reversal signal detected\"}\n",
    ]
    new_lines = lines[:37] + new_block + lines[55:]
    with open('reversal_detector.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("Successfully replaced with sustained 2-bar confirmation logic.")
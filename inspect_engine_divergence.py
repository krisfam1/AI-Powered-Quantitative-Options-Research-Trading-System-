# Scans the two engine source files for keywords related to:
#   1. exit_mode / reversal_guard / take_profit handling
#   2. volatility calculation (which approach A/B/C is wired in)
#
# Prints each matching line with a few lines of context so we can see
# HOW each engine handles these, not just THAT the keyword exists.
#
# Run this from the same folder as options_backtest_engine.py and
# portfolio_backtest.py.

import re

FILES = ["options_backtest_engine.py", "portfolio_backtest.py"]

EXIT_KEYWORDS = [
    "exit_mode",
    "reversal_guard",
    "take_profit",
]

VOL_KEYWORDS = [
    "def.*vol",          # function defs with "vol" in the name
    "volatility",
    "approach_a",
    "approach_b",
    "approach_c",
    "hybrid_volatility",
]

SIZING_KEYWORDS = [
    "contracts",
    "risk_pct",
    "risk_amount",
    "account_equity",
    "position_size",
]

EXIT_PRICING_KEYWORDS = [
    "_estimated_spread_cost_pct",
    "_exit_value_after_spread",
    "close_position",
    "current_option_value",
]

ENTRY_SCORE_KEYWORDS = [
    "calculate_entry_score",
    "spy_regime",
    "entry_score_threshold",
]

CANDLE_GATE_KEYWORDS = [
    "_gate_passed",
    "_close_position",
    "bar_range",
    "_bar_high",
    "_bar_low",
    "0.70",
    "0.30",
]

BREAKOUT_KEYWORDS = [
    "check_breakout",
    "check_breakdown",
    "require_close_strength",
]

CONTEXT_LINES = 3


def scan_file(path, keywords, label):
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"  [!] {path} not found in this folder -- skipping")
        return

    pattern = re.compile("|".join(keywords), re.IGNORECASE)
    hits = [i for i, line in enumerate(lines) if pattern.search(line)]

    print(f"\n--- {path} :: {label} ({len(hits)} matching lines) ---")
    if not hits:
        print("  (no matches)")
        return

    shown = set()
    for i in hits:
        if i in shown:
            continue
        start = max(0, i - CONTEXT_LINES)
        end = min(len(lines), i + CONTEXT_LINES + 1)
        print(f"\n  [lines {start+1}-{end}]")
        for j in range(start, end):
            marker = ">>" if j == i else "  "
            print(f"    {marker} {j+1}: {lines[j].rstrip()}")
        for j in range(start, end):
            shown.add(j)


for path in FILES:
    print("=" * 70)
    print(f"SCANNING: {path}")
    print("=" * 70)
    scan_file(path, EXIT_KEYWORDS, "EXIT MODE / EXIT LOGIC")
    scan_file(path, VOL_KEYWORDS, "VOLATILITY CALCULATION")
    scan_file(path, SIZING_KEYWORDS, "POSITION SIZING (contracts calculation)")
    scan_file(path, EXIT_PRICING_KEYWORDS, "EXIT PRICING (spread cost on exit)")
    scan_file(path, ENTRY_SCORE_KEYWORDS, "ENTRY SCORING (calculate_entry_score args)")
    scan_file(path, CANDLE_GATE_KEYWORDS, "CANDLE POSITION GATE (bar close vs range filter)")
    scan_file(path, BREAKOUT_KEYWORDS, "BREAKOUT/BREAKDOWN GATE (be.check_breakout etc.)")
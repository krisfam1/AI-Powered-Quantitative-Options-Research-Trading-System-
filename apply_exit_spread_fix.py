import shutil

TARGET = "portfolio_backtest.py"
BACKUP = "portfolio_backtest.py.bak2"

OLD_BLOCK = (
    "            if exit_reason:\n"
    "                account.close_position(position_id, timestamp, current_option_value, exit_reason)\n"
)

NEW_BLOCK = (
    "            if exit_reason:\n"
    "                # Mirrors the original, validated engine's exit-side spread\n"
    "                # cost (options_backtest_engine.py, _exit_value_after_spread).\n"
    "                # Without this, exits were priced at the raw model value with\n"
    "                # no trading friction, while entries already charged spread\n"
    "                # cost -- an asymmetric-friction bug that inflated P&L.\n"
    "                _exit_value_after_spread = current_option_value * (1 - _estimated_spread_cost_pct(current_option_value) / 2)\n"
    "                account.close_position(position_id, timestamp, _exit_value_after_spread, exit_reason)\n"
)

with open(TARGET, "r", encoding="utf-8") as f:
    content = f.read()

if OLD_BLOCK not in content:
    print("Could not find the expected block to replace.")
    print("This likely means the file has already been patched, or the")
    print("surrounding code doesn't match exactly (whitespace differences).")
    print("No changes were made. Open portfolio_backtest.py around line 155")
    print("and check manually.")
else:
    shutil.copy(TARGET, BACKUP)
    new_content = content.replace(OLD_BLOCK, NEW_BLOCK)
    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Patched successfully.")
    print("Backup saved as: " + BACKUP)
    print("Added exit-side spread cost, matching the original engine's pricing.")
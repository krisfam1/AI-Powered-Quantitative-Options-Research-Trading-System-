import shutil

TARGET = "portfolio_backtest.py"
BACKUP = "portfolio_backtest.py.bak"

OLD_BLOCK = (
    "            if exit_reason is None and pct_change >= 0.75:\n"
    "                # HONEST FIX: the original, validated reversal_guard mode\n"
    "                # falls back to a flat 75% take-profit if the specific\n"
    "                # 2-bar reversal pattern hasn't triggered -- this was\n"
    "                # missing from the initial build, a real omission.\n"
    "                exit_reason = \"take_profit\"\n"
)

NEW_BLOCK = (
    "            # NOTE: no 75% take-profit fallback here. In the original,\n"
    "            # validated engine (options_backtest_engine.py), reversal_guard\n"
    "            # exit is a single elif branch -- if pct_change >= 0.40 and the\n"
    "            # specific 2-bar reversal pattern hasn't fired, the position\n"
    "            # simply stays open. There is no take_profit fallback in that\n"
    "            # mode. The fallback that used to be here was a behavioral\n"
    "            # divergence from the validated original, not a bug fix.\n"
)

with open(TARGET, "r", encoding="utf-8") as f:
    content = f.read()

if OLD_BLOCK not in content:
    print("Could not find the expected block to replace.")
    print("This likely means the file has already been patched, or the")
    print("surrounding code doesn't match exactly (whitespace differences).")
    print("No changes were made. Open portfolio_backtest.py around line 145")
    print("and check manually.")
else:
    shutil.copy(TARGET, BACKUP)
    new_content = content.replace(OLD_BLOCK, NEW_BLOCK)
    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Patched successfully.")
    print("Backup saved as: " + BACKUP)
    print("Removed the take_profit fallback from reversal_guard exit logic.")
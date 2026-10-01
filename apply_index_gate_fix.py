import shutil

TARGET = "portfolio_backtest.py"
BACKUP = "portfolio_backtest.py.bak3"

OLD_LINE = "        if ticker_positions[ticker] is None and index >= 60:\n"
NEW_BLOCK = (
    "        # NOTE: removed the unconditional 'index >= 60' gate that used to\n"
    "        # sit here. The original, validated engine has no blanket index\n"
    "        # floor on entries -- index >= 60 only appears there scoped to the\n"
    "        # OPTIONAL require_elevated_volatility feature (default False, never\n"
    "        # enabled in any comparison run). This gate was silently blocking\n"
    "        # every entry attempt in roughly the first 60 bars of any backtest,\n"
    "        # which caused a real missed trade vs. the original engine.\n"
    "        if ticker_positions[ticker] is None:\n"
)

with open(TARGET, "r", encoding="utf-8") as f:
    content = f.read()

if OLD_LINE not in content:
    print("Could not find the expected line to replace.")
    print("This likely means the file has already been patched, or the")
    print("line doesn't match exactly (whitespace differences).")
    print("No changes were made. Open portfolio_backtest.py around line 167")
    print("and check manually.")
else:
    shutil.copy(TARGET, BACKUP)
    new_content = content.replace(OLD_LINE, NEW_BLOCK)
    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Patched successfully.")
    print("Backup saved as: " + BACKUP)
    print("Removed the artificial index >= 60 entry gate.")
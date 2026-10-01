import re

PATH = "backtest_engine.py"

try:
    with open(PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
except FileNotFoundError:
    print(f"[!] {PATH} not found in this folder.")
    print("    If the module lives elsewhere, tell me the actual filename/path")
    print("    (check the top of options_backtest_engine.py or portfolio_backtest.py")
    print("    for the import line, e.g. 'import backtest_engine as be' or")
    print("    'from some_module import backtest_engine as be').")
    raise SystemExit(0)

start_idx = None
for i, line in enumerate(lines):
    if re.match(r"^def\s+get_historical_bars\b", line):
        start_idx = i
        break

if start_idx is None:
    print(f"[!] Could not find 'def get_historical_bars' in {PATH}")
    print("    Listing all top-level function/class definitions instead:")
    for i, line in enumerate(lines):
        if re.match(r"^(def |class )", line):
            print(f"  line {i+1}: {line.rstrip()}")
    raise SystemExit(0)

end_idx = len(lines)
for i in range(start_idx + 1, len(lines)):
    if re.match(r"^(def |class )", lines[i]):
        end_idx = i
        break

print("=" * 70)
print(f"{PATH} :: get_historical_bars -- lines {start_idx+1} to {end_idx}")
print("=" * 70)
for i in range(start_idx, end_idx):
    print(f"{i+1:4}: {lines[i].rstrip()}")

# Also show any module-level cache dicts near the top of the file that
# get_historical_bars might be reading/writing.
print("\n" + "=" * 70)
print("MODULE-LEVEL CACHE-LIKE VARIABLES (possible culprits for stale/partial data)")
print("=" * 70)
cache_pattern = re.compile(r"^_?\w*cache\w*\s*=", re.IGNORECASE)
found_any = False
for i, line in enumerate(lines[:120]):  # module-level vars are usually near the top
    if cache_pattern.match(line.strip()):
        print(f"  line {i+1}: {line.rstrip()}")
        found_any = True
if not found_any:
    print("  (none found in the first 120 lines)")
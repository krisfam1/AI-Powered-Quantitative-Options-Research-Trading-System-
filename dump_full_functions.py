import re

FILES = [
    ("options_backtest_engine.py", r"^def\s+run_options_backtest\b"),
    ("portfolio_backtest.py", r"^def\s+run_portfolio_backtest\b"),
]

for path, pattern in FILES:
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"[!] {path} not found -- skipping")
        continue

    start_idx = None
    for i, line in enumerate(lines):
        if re.match(pattern, line):
            start_idx = i
            break

    if start_idx is None:
        print(f"[!] Could not find function matching {pattern} in {path}")
        continue

    # Find the end: next top-level (column-0) def/class after this one
    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        if re.match(r"^(def |class )", lines[i]):
            end_idx = i
            break

    print("=" * 70)
    print(f"{path} -- FULL FUNCTION, lines {start_idx+1} to {end_idx} ({end_idx - start_idx} lines)")
    print("=" * 70)
    for i in range(start_idx, end_idx):
        print(f"{i+1:4}: {lines[i].rstrip()}")
    print()
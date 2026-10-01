import re

FILES = [
    ("options_backtest_engine.py", r"^def\s+run_options_backtest\b"),
    ("portfolio_backtest.py", r"^def\s+run_portfolio_backtest\b"),
]

MAX_LINES_TO_SHOW = 70  # setup code before the main loop typically fits in this

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

    end_idx = min(len(lines), start_idx + MAX_LINES_TO_SHOW)
    print("=" * 70)
    print(f"{path} -- function setup, lines {start_idx+1} to {end_idx}")
    print("=" * 70)
    for i in range(start_idx, end_idx):
        print(f"{i+1:4}: {lines[i].rstrip()}")
    print()
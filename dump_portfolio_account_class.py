import re

with open("portfolio_backtest.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find the PortfolioAccount class and print it in full, plus a bit of
# context after it ends (next top-level def/class at column 0).
start_idx = None
for i, line in enumerate(lines):
    if re.match(r"^class\s+PortfolioAccount\b", line):
        start_idx = i
        break

if start_idx is None:
    print("Could not find 'class PortfolioAccount' in portfolio_backtest.py")
    print("Searching for any class definitions instead:")
    for i, line in enumerate(lines):
        if line.startswith("class "):
            print(f"  line {i+1}: {line.rstrip()}")
else:
    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        if re.match(r"^(class |def )", lines[i]):
            end_idx = i
            break
    print(f"PortfolioAccount class -- lines {start_idx+1} to {end_idx}")
    print("=" * 70)
    for i in range(start_idx, end_idx):
        print(f"{i+1:4}: {lines[i].rstrip()}")

# Also print where run_portfolio_backtest calls open_position / close_position
# / can_afford, so we can see exactly what's passed in each call site.
print("\n" + "=" * 70)
print("ALL CALL SITES referencing account.<method> in this file")
print("=" * 70)
for i, line in enumerate(lines):
    if re.search(r"account\.(can_afford|open_position|close_position|mark_to_market|cash)\b", line):
        print(f"  line {i+1}: {line.rstrip()}")
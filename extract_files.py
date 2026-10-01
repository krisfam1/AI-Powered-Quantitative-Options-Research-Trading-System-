"""
Extracts specific files out of all_code_dump.txt (produced by the
`for /r %f in (*.py) do (echo. & echo ===== %f ===== & type "%f")` dump
command), based on the "===== <full path> =====" markers it inserts
between files. Writes each requested file back out individually so it
can be uploaded on its own instead of the full 1.65MB dump.

Usage: run this from the same folder as all_code_dump.txt:
    python extract_files.py
"""

TARGET_FILENAMES = [
    "investigate_date_discrepancy.py",
    "check_lookahead_bias.py",
    "check_contract_identity.py",
    "fix_real_expiration_bug.py",
]

with open("all_code_dump.txt", "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

current_target = None
buffer = []
extracted = {}

for line in lines:
    stripped = line.rstrip("\n")
    if stripped.startswith("===== ") and stripped.endswith(" ====="):
        # flush previous buffer if it was one of our targets
        if current_target is not None:
            extracted[current_target] = "".join(buffer)
        path = stripped[len("===== "):-len(" =====")]
        basename = path.split("\\")[-1].split("/")[-1]
        current_target = basename if basename in TARGET_FILENAMES else None
        buffer = []
        continue
    if current_target is not None:
        buffer.append(line)

if current_target is not None:
    extracted[current_target] = "".join(buffer)

for name in TARGET_FILENAMES:
    if name in extracted:
        out_name = "extracted_" + name
        with open(out_name, "w", encoding="utf-8") as out:
            out.write(extracted[name])
        print(f"Extracted: {name} -> {out_name} ({len(extracted[name])} chars)")
    else:
        print(f"NOT FOUND in dump: {name}")
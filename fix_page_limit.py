content = open('eodhd_audit_term_structure.py', encoding='utf-8').read()
old = '"page[limit]": 2000,'
new = '"page[limit]": 1000,'
count = content.count(old)
if count == 0:
    print("Pattern not found")
else:
    content = content.replace(old, new)
    open('eodhd_audit_term_structure.py', 'w', encoding='utf-8').write(content)
    print("Patched " + str(count) + " occurrence(s)")
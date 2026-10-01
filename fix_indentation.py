import re

content = open('experiment_config.py', encoding='utf-8').read()
lines = content.split('\n')

for i, line in enumerate(lines):
    if line.strip() == 'try:' and line != '        try:':
        print('Fixing line ' + str(i+1) + ': ' + repr(line))
        lines[i] = '        try:'  # 8 spaces, matching the surrounding block's indentation

open('experiment_config.py', 'w', encoding='utf-8').write('\n'.join(lines))
print('Done.')
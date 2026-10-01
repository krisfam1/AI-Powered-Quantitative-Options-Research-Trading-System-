content = open('experiment_config.py', encoding='utf-8').read()

leftover = '''        else:
            object.__setattr__(self, "parameters", _deep_freeze(tuple(self.parameters)))
'''

if leftover in content:
    content = content.replace(leftover, '', 1)
    print('Removed leftover fragment')
else:
    print('Leftover fragment not found -- may already be clean, or has different whitespace')

open('experiment_config.py', 'w', encoding='utf-8').write(content)
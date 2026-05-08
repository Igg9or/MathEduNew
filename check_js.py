import re

with open('static/js/student_duel.js', 'r', encoding='utf-8') as f:
    code = f.read()

code2 = re.sub(r'//.*', '', code)
code2 = re.sub(r'"[^"]*"', '""', code2)
code2 = re.sub(r"'[^']*'", "''", code2)
code2 = re.sub(r'/[^/]+/', '/ /', code2)

print('braces:', code2.count('{') - code2.count('}'))
print('parens:', code2.count('(') - code2.count(')'))
print('brackets:', code2.count('[') - code2.count(']'))

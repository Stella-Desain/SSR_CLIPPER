import re

with open(r'source sementara\GEMINI_INSTRUCTIONS_ssr_clipper_efficiency_fix.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 5a extraction
match_5a = re.search(r'Ganti dengan \(kode lama \+ fungsi baru setelahnya.*?\):\n```python\n(.*?)```', content, re.DOTALL)
if not match_5a:
    print('Failed 5a extraction')
    exit(1)
new_code_5a = match_5a.group(1).rstrip()

with open('clipper_core.py', 'r', encoding='utf-8') as f:
    core = f.read()

target_5a_pattern = re.compile(r'        if not Path\(output_path\)\.exists\(\):\n            raise Exception\("Failed to apply credit watermark"\)\n*(\s*)$')
if not target_5a_pattern.search(core):
    print('Failed 5a target find')
    exit(1)
core = target_5a_pattern.sub(new_code_5a + '\n\n', core)

# 5b extraction
match_target_5b = re.search(r'Cari blok ini PERSIS.*?\n```python\n(.*?)```\n\n\*\*Ganti dengan:\*\*', content, re.DOTALL)
target_5b = match_target_5b.group(1).rstrip()

match_new_5b = re.search(r'\*\*Ganti dengan:\*\*\n```python\n(.*?)```', content, re.DOTALL)
new_5b = match_new_5b.group(1).rstrip()

if target_5b in core:
    core = core.replace(target_5b, new_5b)
    print('Task 5b replaced!')
else:
    print('Failed to find 5b target in core')
    exit(1)

with open('clipper_core.py', 'w', encoding='utf-8') as f:
    f.write(core)
print('Task 5 complete!')

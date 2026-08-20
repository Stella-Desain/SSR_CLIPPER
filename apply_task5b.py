import re

with open(r'source sementara\GEMINI_INSTRUCTIONS_ssr_clipper_efficiency_fix.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 5b extraction
match_new_5b = re.search(r'\*\*Ganti dengan:\*\*\n```python\n(.*?)```', content, re.DOTALL)
if not match_new_5b:
    print('Failed to extract new 5b')
    exit(1)
new_5b = match_new_5b.group(1).rstrip()

with open('clipper_core.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Line numbers 3021 to 3089 are 0-indexed 3020 to 3088
# Delete 3020 to 3089 and insert new_5b
start_idx = 3021 - 1
end_idx = 3089

del lines[start_idx:end_idx]

# Split new_5b into lines with newlines so it inserts cleanly
new_lines = [line + '\n' for line in new_5b.split('\n')]
lines[start_idx:start_idx] = new_lines

with open('clipper_core.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Task 5b lines replaced!")

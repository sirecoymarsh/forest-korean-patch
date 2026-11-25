# -*- coding: utf-8 -*-
"""model.cpp 의 scenes 표 → 대본 번호: 장 번호(0=I)."""
import re, json
s = open(r'P:\AI\forest-qol\s-hiart\native\model.cpp', encoding='utf-8').read()
i = s.find('scenes=')
j = s.find('};', i)
body = s[i:j]
out = {}
for m in re.finditer(r'\{(\d+),(\d+),L"([^"]*)"', body):
    t = m.group(3).encode().decode('unicode_escape')
    out[int(m.group(1))] = (int(m.group(2)), t)
if __name__ == '__main__':
    for k, v in sorted(out.items()):
        print(k, v[0], v[1])
    json.dump({k: v for k, v in out.items()}, open(r'Y:\AI\forest-4k\scenes.json', 'w', encoding='utf-8'), ensure_ascii=False)

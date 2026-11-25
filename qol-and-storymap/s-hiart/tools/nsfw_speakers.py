# -*- coding: utf-8 -*-
"""성적 장면 후보 CG 가 뜬 뒤 대사 40줄의 화자 꼬리표(【이름】)만 센다. 문장은 담지 않는다."""
import sys, json, re, collections
sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import gscwalk
SCR = r'Y:\AI\forest-qol-test-hiart\game\scr'
CG = [int(x) for x in sys.argv[1].split(',')]
out = []
for sid, _ in gscwalk.all_scripts():
    if not (2100 <= sid < 4000): continue
    rows, strs = gscwalk.read_gsc('%s\\%04d.gsc' % (SCR, sid), 'cp949')
    for k, (pc, op, a) in enumerate(rows):
        v = a[2] if (op == 0x1800 and len(a) == 3 and a[1] in (501, 503)) else None
        if v not in CG: continue
        sp = collections.Counter()
        n = 0
        for pc2, op2, a2 in rows[k + 1:k + 800]:
            if op2 == 0x51:
                for slot in (a2[1], a2[5]):
                    if slot < len(strs):
                        for m in re.findall('【([^】]{1,12})】', strs[slot]): sp[m] += 1
                n += 1
                if n >= 40: break
        out.append('grpe/%04d script %d pc %d speakers %s' % (v, sid, pc, dict(sp.most_common(6))))
open(r'Y:\AI\forest-4k\nsfw_speakers.txt', 'w', encoding='utf-8').write('\n'.join(out))
print(len(out))

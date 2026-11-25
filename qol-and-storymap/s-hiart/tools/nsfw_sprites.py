# -*- coding: utf-8 -*-
"""성적 장면 후보 CG 가 뜨기 전 300명령 안에 띄운 얼굴 창(층 35~37)·스탠딩(층 26~32) 번호 — 인물 가리기용(그림은 열지 않음)."""
import sys, json, collections
sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import gscwalk
SCR = r'Y:\AI\forest-qol-test-hiart\game\scr'
CG = [int(x) for x in sys.argv[1].split(',')]
out = []
for sid, _ in gscwalk.all_scripts():
    if not (2100 <= sid < 4000): continue
    rows, strs = gscwalk.read_gsc('%s\\%04d.gsc' % (SCR, sid), 'cp949')
    for k, (pc, op, a) in enumerate(rows):
        v = a[2] if (op == 0x1800 and len(a) == 3 and a[1] in (501, 503)) else (a[0] if op == 0x14 else None)
        if v not in CG: continue
        f = collections.Counter(); b = collections.Counter()
        for pc2, op2, a2 in rows[max(0, k - 400):k + 200]:
            if op2 == 0x1e and a2[1] < 65536:
                if 35 <= a2[0] <= 37: f[a2[1] // 100] += 1
                if 26 <= a2[0] <= 32: b[a2[1] // 10] += 1
        out.append('grpe/%04d script %d: face groups %s | standing groups %s' % (v, sid, dict(f.most_common(5)), dict(b.most_common(6))))
open(r'Y:\AI\forest-4k\nsfw_sprites.txt', 'w', encoding='utf-8').write('\n'.join(sorted(set(out))))
print(len(out))

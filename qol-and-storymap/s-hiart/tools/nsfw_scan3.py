# -*- coding: utf-8 -*-
"""얼굴 창·스탠딩·컷인·배경(층 0x1e 로 띄우는 그림)도 뜬 자리 뒤 대사 20줄의 강한 낱말·이름 수. 문장은 담지 않는다."""
import sys, json, collections
sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import gscwalk
SCR = r'Y:\AI\forest-qol-test-hiart\game\scr'
KW = ['알몸', '나체', '벗겨', '벗기', '젖가슴', '젖꼭지', '유두', '음부', '음핵', '애액', '삽입', '정액', '섹스', '성기', '핥', '페니스', '애무', '절정', '허리를 움직']
NAMES = ['앨리스', '노조미', '아메노모리', '마유즈미', '나가츠키', '아케루']
sc = {int(k): v for k, v in json.load(open(r'Y:\AI\forest-4k\scenes.json', encoding='utf-8')).items()}
fc = json.load(open(r'Y:\AI\forest-4k\first_chapter.json'))
folder = {int(k): v for k, v in fc['folder'].items()}
agg = collections.defaultdict(lambda: [0, collections.Counter(), set()])
for sid, _ in gscwalk.all_scripts():
    if sid not in sc: continue
    rows, strs = gscwalk.read_gsc('%s\\%04d.gsc' % (SCR, sid), 'cp949')
    for k, (pc, op, a) in enumerate(rows):
        if op != 0x1e or a[1] >= 65536: continue
        f = folder.get(a[0])
        if f not in ('grpo_bu', 'grpo_f', 'grpo_ci', 'grpo_bg'): continue
        texts = []
        for pc2, op2, a2 in rows[k + 1:k + 400]:
            if op2 == 0x51 and a2[5] < len(strs):
                texts.append(strs[a2[5]])
                if len(texts) >= 20: break
        t = ' '.join(texts)
        s = sum(t.count(w) for w in KW)
        key = '%s/%04d' % (f, a[1])
        g = agg[key]; g[0] = max(g[0], s); g[2].add(sc[sid][0] + 1)
        for nm in NAMES: g[1][nm] += t.count(nm)
with open(r'Y:\AI\forest-4k\nsfw_scan3.txt', 'w', encoding='utf-8') as fo:
    for key, (s, nm, chs) in sorted(agg.items(), key=lambda kv: -kv[1][0]):
        if s >= 3: fo.write('%s max_strong %d chapters %s names %s\n' % (key, s, sorted(chs), dict(nm.most_common(3))))
print('ok')

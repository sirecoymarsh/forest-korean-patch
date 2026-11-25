# -*- coding: utf-8 -*-
"""CG 가 뜬 자리마다(이야기 대본만) 뒤 대사 30줄의 강한 낱말 수·이름 수. 문장은 담지 않는다."""
import sys, json, collections
sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import gscwalk
SCR = r'Y:\AI\forest-qol-test-hiart\game\scr'
KW = ['알몸', '나체', '벗겨', '벗기', '젖가슴', '젖꼭지', '유두', '음부', '음핵', '애액', '삽입', '정액', '섹스', '성기', '핥', '페니스', '애무', '절정', '허리를 움직', '가슴을 주무', '안에 싸']
NAMES = ['앨리스', '노조미', '아메노모리', '마유즈미', '나가츠키', '아케루', '피터', '웬디', '하루시']
sc = {int(k): v for k, v in json.load(open(r'Y:\AI\forest-4k\scenes.json', encoding='utf-8')).items()}
inv = json.load(open(r'Y:\AI\forest-4k\inventory_raw.json', encoding='utf-8'))
grpe = {int(e['name'][:4]) for e in inv if e['arc'] == 'grpe.xfl'}
rows_out = []
for sid, _ in gscwalk.all_scripts():
    if sid not in sc: continue
    rows, strs = gscwalk.read_gsc('%s\\%04d.gsc' % (SCR, sid), 'cp949')
    for k, (pc, op, a) in enumerate(rows):
        v = None
        if op == 0x1800 and len(a) == 3 and a[1] in (501, 503) and a[2] in grpe: v = a[2]
        if op == 0x14 and a[0] in grpe: v = a[0]
        if v is None or v >= 1000: continue
        texts = []
        for pc2, op2, a2 in rows[k + 1:k + 600]:
            if op2 == 0x51 and a2[5] < len(strs):
                texts.append(strs[a2[5]])
                if len(texts) >= 30: break
        t = ' '.join(texts)
        hits = {w: t.count(w) for w in KW if t.count(w)}
        names = {w: t.count(w) for w in NAMES if t.count(w)}
        rows_out.append({'cg': 'grpe/%04d' % v, 'script': sid, 'chapter': sc[sid][0] + 1, 'pc': pc, 'strong': sum(hits.values()), 'hits': hits, 'names': names})
json.dump(rows_out, open(r'Y:\AI\forest-4k\nsfw_scan2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
agg = collections.defaultdict(lambda: [0, collections.Counter(), set()])
for r in rows_out:
    a = agg[r['cg']]; a[0] = max(a[0], r['strong']); a[1].update(r['names']); a[2].add((r['script'], r['chapter']))
with open(r'Y:\AI\forest-4k\nsfw_scan2.txt', 'w', encoding='utf-8') as f:
    for cg, (s, nm, wh) in sorted(agg.items()):
        f.write('%s max_strong %d names %s scripts %s\n' % (cg, s, dict(nm.most_common(4)), sorted(wh)))
print('ok', len(rows_out))

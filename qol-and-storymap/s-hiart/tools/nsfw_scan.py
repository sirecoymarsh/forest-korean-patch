# -*- coding: utf-8 -*-
"""CG 를 눈으로 열지 않고 대본 문맥으로 성적 장면 후보를 가린다.
CG 번호를 정하는 곳(변수 501/503 := 번호, 또는 0x14) 뒤 대사 40줄의 낱말 점수 + 나오는 이름.
출력: Y:\\AI\\forest-4k\\nsfw_scan.json (문장은 담지 않는다: 낱말 수·이름만)."""
import sys, json, re, collections
sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import gscwalk
SCR = r'Y:\AI\forest-qol-test-hiart\game\scr'
KW = ['알몸', '나체', '맨살', '벌거', '벗겨', '벗기', '벗은', '젖가슴', '젖꼭지', '유두', '가슴을', '허벅지', '사타구니', '음부', '음핵', '애액', '삽입', '사정', '정액',
      '신음', '교성', '허리를 움직', '처녀', '섹스', '성기', '핥', '빨아', '안에다', '쾌감', '절정', '흥분', '애무', '페니스', '자지', '보지', '젖어',
      '하앗', '아앗', '흐읏', '앙앙', '꿈틀']
NAMES = ['앨리스', '노조미', '아메노모리', '마유즈미', '나가츠키', '아케루', '하루시', '우사기', '그리폰', '웬디', '피터']
inv = json.load(open(r'Y:\AI\forest-4k\inventory_raw.json', encoding='utf-8'))
grpe = {int(e['name'][:4]) for e in inv if e['arc'] == 'grpe.xfl'}
res = collections.defaultdict(lambda: {'hits': collections.Counter(), 'names': collections.Counter(), 'where': []})
for sid, _ in gscwalk.all_scripts():
    p = '%s\\%04d.gsc' % (SCR, sid)
    try:
        rows, strs = gscwalk.read_gsc(p, 'cp949')
    except Exception:
        continue
    for k, (pc, op, a) in enumerate(rows):
        v = None
        if op == 0x1800 and len(a) == 3 and a[1] in (501, 503) and a[2] in grpe: v = a[2]
        if op == 0x14 and a[0] in grpe: v = a[0]
        if v is None: continue
        texts = []
        for pc2, op2, a2 in rows[k + 1:k + 400]:
            if op2 == 0x51 and a2[5] < len(strs):
                texts.append(strs[a2[5]])
                if len(texts) >= 40: break
            if op2 == 0x1800 and len(a2) == 3 and a2[1] == 501 and a2[2] != v: break   # 다음 CG
        t = ' '.join(texts)
        r = res[v]
        r['where'].append((sid, pc))
        for w in KW: r['hits'][w] += t.count(w)
        for nm in NAMES: r['names'][nm] += t.count(nm)
out = {}
for v, r in sorted(res.items()):
    score = sum(r['hits'].values())
    out['grpe/%04d' % v] = {'score': score, 'hits': {k: c for k, c in r['hits'].items() if c}, 'names': {k: c for k, c in r['names'].items() if c}, 'where': r['where'][:4]}
json.dump(out, open(r'Y:\AI\forest-4k\nsfw_scan.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
top = sorted(out.items(), key=lambda kv: -kv[1]['score'])
for k, v in top[:30]:
    print(k, v['score'], v['hits'], v['names'], v['where'][:2])

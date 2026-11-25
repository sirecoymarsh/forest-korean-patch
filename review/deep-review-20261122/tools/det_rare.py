# -*- coding: utf-8 -*-
"""검출기 A2: 한국어 쪽 드문 한자어 — 원문 한자 음과 상관없이, 번역에 들어간 2~3음절 낱말 중
(1) 모든 음절이 한자음으로 쓰이는 음절이고 (2) 한국어 구어 말뭉치 빈도(그 글자로 시작하는 어절 합)가 2 이하이며
(3) 같은 칸 원문 가타카나의 음차가 아닌 것. 흑점(黒丸)·대해양(大海原)처럼 「음 옮김」이 아니라 「드문 한자어로 옮긴」 것을 잡는다.
→ data\rare_ko.json · data\screen_rare.tsv"""
import os, sys, re, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from kores import kofreq, _H
from det_kata import KATA, k2h, lev, PART
SINO = set(x for v in _H.values() for x in v)
rows = [r for r in load_corpus() if r['kind'] in ('MSG', 'SUB', 'CHQ', 'CHO') and r['chap'] and not r['hold']]
ad = set(json.load(open(os.path.join(DATA, 'adult.json'), encoding='utf-8'))['ids'])
cnt = collections.defaultdict(list)
for r in rows:
    kat = [k2h(k) for k in KATA.findall(plain(r['ja']))]
    for tok in re.findall(r'[가-힣]+', plain(r['ko'])):
        st = PART.sub('', tok)
        for s in {st}:
            if not (2 <= len(s) <= 3): continue
            if not all(c in SINO for c in s): continue
            if any(lev(t, s) <= 0.4 for t in kat if t): continue
            cnt[s].append(r['id'])
cand = []
for s, ids in cnt.items():
    ids = sorted(set(ids), key=idkey)
    if kofreq(s) <= 1 and len(ids) <= 6:
        cand.append((s, ids))
# 같은 칸에서 긴 것이 잡히면 그 앞머리 짧은 것은 뺀다
long = {(i, s) for s, ids in cand if len(s) == 3 for i in ids}
cand = [(s, ids) for s, ids in cand if not (len(s) == 2 and all(any((i, l) in long for l in [s + c for c in '']) for i in ids))]
rws = {r['id']: r for r in rows}
with open(os.path.join(DATA, 'screen_rare.tsv'), 'w', encoding='utf-8') as fo:
    fo.write('no\t낱말\t칸수\t예칸\t한국어 예문\t일본어 예문\n')
    for n, (s, ids) in enumerate(sorted(cand), 1):
        i = next((x for x in ids if x not in ad), None)
        if not i: fo.write('%d\t%s\t%d\t%s*\t(성적 구간)\t\n' % (n, s, len(ids), ids[0])); continue
        k = flat(rws[i]['ko']); p = k.find(s)
        fo.write('%d\t%s\t%d\t%s\t%s\t%s\n' % (n, s, len(ids), i, k[max(0, p - 16): p + len(s) + 16], flat(rws[i]['ja'])[:60]))
json.dump(cand, open(os.path.join(DATA, 'rare_ko.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('rare sino candidates', len(cand), 'cells', sum(len(i) for _, i in cand))
sys.stdout.reconfigure(encoding='utf-8')
# 옛 판(앞 검수 실례가 남은 판)에도 같은 규칙: 재현율 확인
old = collections.defaultdict(list)
for r in rows:
    for tok in re.findall(r'[가-힣]+', plain(r['old'])):
        st = PART.sub('', tok)
        if 2 <= len(st) <= 3 and all(c in SINO for c in st) and kofreq(st) <= 1: old[st].append(r['id'])
for s in ['흑점', '대해양', '청공', '호천하', '외견적', '격통', '극통', '폭산', '편차치', '배전', '모잇']:
    print(s, '지금판', s in cnt, '옛판', old.get(s, [])[:3], '빈도', kofreq(s))

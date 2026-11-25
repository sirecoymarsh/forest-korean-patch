# -*- coding: utf-8 -*-
"""층화 무작위 표본 400칸 — 제미나이가 손대지 않은 칸(runtime\\scr == scr_backup_20261121)에서.

층 = 장(I~IX) × 줄 종류(narr 지문 / quote 지문 속 「」대사 / voiced 화자 대사 / sub 음성 자막 / choice 선택지)
     × 화자(voiced 만: 상위 7 코드, 나머지 etc)
배분: 비례 배분(최대 나머지법), 크기 10 이상인 층은 최소 2칸, 1~9 층은 최소 1칸 — 그 뒤 비례분에서 덜어 400에 맞춤.
빼는 칸: 정책 보류(대본 통째·칸)와 그 앞뒤 15칸, 성적 구간(adult.json), 빈 칸, 원문 없는 MSG.
씨앗 20261122 — 다시 돌려도 같은 표본.
→ data\\population.json(층별 크기) · data\\sample.jsonl(표본 + 문맥)
"""
import os, sys, json, random, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

N_SAMPLE = 400
import re
# 표본 칸 하나하나에 거는 넓은 거르개(창이 아니라 칸 단위): 걸리면 표본에서 뺀다(읽지 않고)
BROAD = re.compile(r'乳|舐|挿|膣|精|勃|性器|股|喘|犯|陰|絶頂|処女|秘|裸|濡|下着|パンツ|ショーツ|揉|太もも|太腿|イく|イッ|イっ|気持ちい|気持ちよ|あぁん|あんっ|セックス|エッチ|えっち|尻|唾液|腰|感じ')
BROAD_KO = re.compile(r'젖|핥|삽입|정액|사정하|발기|성기|사타구니|애액|신음|범하|범해|음경|절정|처녀|알몸|젖어|속옷|팬티|허벅지|가버|기분 좋|야한|엉덩이|섹스|허리')
SEED = 20261122
TOPSPK = ['006', '007', '001', '005', '004', '002', '003']


def line_type(r):
    if r['kind'] == 'SUB': return 'sub'
    if r['kind'] in ('CHQ', 'CHO'): return 'choice'
    if r['spk'] != '999': return 'voiced'
    return 'quote' if '「' in r['ja'] else 'narr'


def stratum(r):
    lt = line_type(r)
    g = (r['spk'] if r['spk'] in TOPSPK else 'etc') if lt == 'voiced' else '-'
    return '%s|%s|%s' % (r['chap'], lt, g)


def excluded_ids(rows):
    ad = set(json.load(open(os.path.join(DATA, 'adult.json'), encoding='utf-8'))['ids'])
    ex = set(ad)
    byf = collections.defaultdict(list)
    for r in rows: byf[r['file']].append(r)
    for f, rs in byf.items():
        rs.sort(key=lambda r: r['seq'])
        for i, r in enumerate(rs):
            if r['hold']:
                for j in range(max(0, i - 15), min(len(rs), i + 16)):
                    ex.add(rs[j]['id'])
    return ex


def context(rows_by_file, r, before=3, after=2):
    rs = rows_by_file[r['file']]
    i = r['_i']
    ctx = []
    for j in range(max(0, i - before), min(len(rs), i + after + 1)):
        if j == i: continue
        q = rs[j]
        ctx.append({'rel': j - i, 'id': q['id'], 'kind': q['kind'], 'spk': q['spk'],
                    'ja': flat(q['ja']), 'ko': flat(q['ko'])})
    return ctx


def main():
    rows = load_corpus()
    ex = excluded_ids(rows)
    byf = collections.defaultdict(list)
    for r in rows:
        if r['kind'] in ('MSG', 'SUB', 'CHQ', 'CHO'): byf[r['file']].append(r)
    for f in byf:
        byf[f].sort(key=lambda r: r['seq'])
        for i, r in enumerate(byf[f]): r['_i'] = i
    pop = []
    why = collections.Counter()
    for r in rows:
        if r['kind'] not in ('MSG', 'SUB', 'CHQ', 'CHO') or not r['chap']: continue
        if r['changed']: why['changed'] += 1; continue
        if r['hold']: why['hold'] += 1; continue
        if r['id'] in ex: why['adult_or_near_hold'] += 1; continue
        if not plain(r['ko']).strip(): why['empty'] += 1; continue
        if BROAD.search(r['ja'] or '') or BROAD_KO.search(r['ko']): why['broad_sexual_word'] += 1; continue
        if r['kind'] != 'SUB' and not plain(r['ja']).strip(): why['no_ja'] += 1; continue
        pop.append(r)
    S = collections.defaultdict(list)
    for r in pop: S[stratum(r)].append(r)
    N = len(pop)
    alloc = {}
    for h, rs in S.items():
        alloc[h] = 2 if len(rs) >= 10 else 1
    rest = N_SAMPLE - sum(alloc.values())
    share = {h: len(rs) / N * N_SAMPLE for h, rs in S.items()}
    extra = {h: max(0.0, share[h] - alloc[h]) for h in S}
    tot_extra = sum(extra.values())
    raw = {h: extra[h] / tot_extra * rest for h in S}
    add = {h: int(raw[h]) for h in S}
    left = rest - sum(add.values())
    for h in sorted(S, key=lambda h: raw[h] - add[h], reverse=True)[:left]: add[h] += 1
    for h in S: alloc[h] = min(len(S[h]), alloc[h] + add[h])
    rnd = random.Random(SEED)
    sample = []
    for h in sorted(S):
        pick = rnd.sample(S[h], alloc[h])
        for r in pick:
            s = {k: r[k] for k in ('id', 'file', 'slot', 'chap', 'kind', 'spk', 'voice', 'ja', 'ko', 'en') if k in r}
            s['stratum'] = h
            s['lt'] = line_type(r)
            s['context'] = context(byf, r)
            sample.append(s)
    sample.sort(key=lambda s: idkey(s['id']))
    json.dump({'N': N, 'excluded': dict(why), 'strata': {h: {'N': len(S[h]), 'n': alloc[h]} for h in sorted(S)}},
              open(os.path.join(DATA, 'population.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    dump_jsonl(sample, os.path.join(DATA, 'sample.jsonl'))
    print('population', N, 'excluded', dict(why), 'strata', len(S), 'sample', len(sample))
    print('by lt', collections.Counter(s['lt'] for s in sample))
    print('by chap', collections.Counter(s['chap'] for s in sample))


if __name__ == '__main__':
    main()

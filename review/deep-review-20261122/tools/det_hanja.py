# -*- coding: utf-8 -*-
"""검출기 A: 한자음 잔재 — 원문 한자어를 한국 한자음 그대로 옮겼는데, 그 말이 한국어에서 거의 안 쓰이는 곳.

규칙
 1. 일본어 원문 MSG 에서 한자 연속(々 포함) 2~4자 부분열 w 를 모두 뽑는다.
 2. w 의 한국 한자음 r(Unihan kHangul, 이체자, 첫소리 두음법칙 변형)이 같은 칸 한국어에 그대로 있으면 「옮겨 옴」.
    (긴 w 가 맞으면 그 안쪽 짧은 w 는 세지 않는다.)
 3. r 의 한국어 빈도(OpenSubtitles 2018 한국어 63만 어절, r 로 시작하는 어절 빈도 합)가 F_MAX 이하면 후보.
 4. 사용자 허용 목록(작품 용어·정착 한자어)은 뺀다 — allow 표 참조.
→ out\\det_hanja.tsv (w, r, 빈도, 칸 수, 칸들) · data\\carry_pairs.json(모든 옮겨 옴 쌍: 검출기 C 가 씀)
"""
import os, sys, re, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
from kores import hangul_readings, kofreq, is_kanji, per_million

F_MAX = 2
ALLOW = set()   # 사람이 확인해 정상으로 본 것(아래 triage 뒤 채움)
ap = os.path.join(DATA, 'hanja_allow.txt')
if os.path.exists(ap):
    ALLOW = {l.split('\t')[0].strip() for l in open(ap, encoding='utf-8') if l.strip() and not l.startswith('#')}


def kanji_runs(t):
    out, cur, st = [], '', 0
    for i, c in enumerate(t):
        if is_kanji(c):
            if not cur: st = i
            cur += c
        else:
            if len(cur) >= 2: out.append(cur)
            cur = ''
    if len(cur) >= 2: out.append(cur)
    return out


def carry(ja, ko):
    """같은 칸에서 한자음 그대로 옮겨 온 (w, r) 쌍."""
    kop = re.sub(r'[^가-힣]', ' ', plain(ko))
    found = []
    for run in kanji_runs(plain(ja)):
        n = len(run)
        covered = [False] * n
        for L in range(min(4, n), 1, -1):
            for s in range(0, n - L + 1):
                if all(covered[s:s + L]): continue
                w = run[s:s + L]
                for r in hangul_readings(w):
                    if r in kop:
                        found.append((w, r))
                        for q in range(s, s + L): covered[q] = True
                        break
    return found


def main():
    rows = [r for r in load_corpus() if r['kind'] in ('MSG', 'CHQ', 'CHO') and r['ja'] and not r['hold']]
    ad = set(json.load(open(os.path.join(DATA, 'adult.json'), encoding='utf-8'))['ids'])
    pairs = collections.defaultdict(list)
    for r in rows:
        for w, rd in carry(r['ja'], r['ko']):
            pairs[(w, rd)].append(r['id'])
    allp = [{'w': w, 'r': rd, 'freq': kofreq(rd), 'n': len(ids), 'ids': ids} for (w, rd), ids in pairs.items()]
    allp.sort(key=lambda x: (x['freq'], -x['n']))
    json.dump(allp, open(os.path.join(DATA, 'carry_pairs.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    cand = [p for p in allp if p['freq'] <= F_MAX and p['r'] not in ALLOW]
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'det_hanja.tsv'), 'w', encoding='utf-8') as fo:
        fo.write('w\tr\tfreq\tn\tids(성적 구간은 *)\n')
        for p in cand:
            fo.write('%s\t%s\t%d\t%d\t%s\n' % (p['w'], p['r'], p['freq'], p['n'],
                                               ' '.join(i + ('*' if i in ad else '') for i in p['ids'])))
    print('carry pairs', len(allp), 'cells', sum(p['n'] for p in allp))
    print('candidates freq<=%d' % F_MAX, len(cand), 'cells', sum(p['n'] for p in cand))


if __name__ == '__main__':
    main()

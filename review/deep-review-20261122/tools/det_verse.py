# -*- coding: utf-8 -*-
"""검출기 F: 말장난·운문 전 목록과 제약 재기.

찾기(원문 기준)
 V1 단서어: 洒落·シャレ·ダジャレ·韻·リメリック·語呂·回文·しりとり·替え歌·早口言葉·なぞなぞ·言葉遊び·詩·歌詞·唄 등이 든 칸과 그 앞뒤 2칸
 V2 각운: 3줄 이상 칸에서 줄끝 가나 2모라가 같은 줄이 2개 이상(흔한 끝말 です·ます·した·った·ている 등은 셈 안 함)
 V3 음수율: 3줄 이상이고 모든 줄이 7·5·12 모라(±1) — 7·5조
 V4 메아리: 한 칸 안에서 같은 구(4모라 이상)가 2번 이상 / 같은 대본 안에서 같은 줄이 3번 이상(후렴)
제약 재기(번역)
 - 각운: 원문에서 운이 맞는 줄 묶음마다 번역 줄끝 1음절이 같은지(같은 묶음 안 일치 비율)
 - 음수율: 원문 줄별 모라 수 대 번역 줄별 음절 수의 비(줄마다 비율의 흩어짐 = 변동계수)
 - 메아리: 원문에서 되풀이되는 구가 번역에서도 같은 글로 되풀이되는지
→ out\\det_verse.tsv (모든 항목·제약·잰 값·어긋남 표시) · data\\verse.json
"""
import os, sys, re, json, collections, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
import pykakasi
KK = pykakasi.kakasi()

CUE = re.compile(r'洒落|シャレ|ダジャレ|駄洒落|韻を|韻が|押韻|リメリック|語呂|回文|しりとり|替え歌|早口言葉|なぞなぞ|言葉遊び|ことば遊び|地口|歌詞|戯れ歌|♪')
STOP = {'ます', 'した', 'った', 'ない', 'です', 'てる', 'いる', 'ある', 'だよ', 'のよ', 'わよ', 'かな', 'よね', 'てた', 'んだ', 'のだ',
        'ろう', 'しょ', 'ょう', 'けど', 'から', 'のに', 'した', 'れた', 'った', 'いた', 'だっ', 'ぞ', 'ね', 'よ', 'な'}


def hira(t):
    t = re.sub(r'[\s、。，．,.!！?？…‥・「」『』（）()〜～ー―─\-"\'“”　]', '', t)
    return ''.join(x['hira'] for x in KK.convert(t))


def mora(t):
    h = hira(t)
    return len(re.sub(r'[ゃゅょぁぃぅぇぉ]', '', h))


def ko_syl(t):
    return len(re.findall(r'[가-힣]', t))


def lines_ja(r): return [l for l in plain(r['ja']).replace('　', '').split(' ') if l.strip()] if False else [l.strip('　 ') for l in TOK.sub(lambda m: '\n' if m.group(1) == 'n' else '', r['ja']).split('\n') if l.strip('　 ')]
def lines_ko(r): return [l.strip() for l in TOK.sub(lambda m: '\n' if m.group(1) == 'n' else '', r['ko']).split('\n') if l.strip()]


def endk(l, n=2):
    h = hira(l)
    return h[-n:] if len(h) >= n else h


def main():
    rows = [r for r in load_corpus() if r['kind'] in ('MSG', 'CHQ', 'CHO') and r['chap'] and not r['hold'] and r['ja']]
    ad = set(json.load(open(os.path.join(DATA, 'adult.json'), encoding='utf-8'))['ids'])
    byf = collections.defaultdict(list)
    for r in rows: byf[r['file']].append(r)
    for f in byf: byf[f].sort(key=lambda r: r['seq'])
    items = {}

    def add(r, why):
        items.setdefault(r['id'], {'r': r, 'why': set()})['why'].add(why)
    for f, rs in byf.items():
        lc = collections.Counter()
        for r in rs:
            for l in lines_ja(r):
                if mora(l) >= 6: lc[hira(l)] += 1
        for i, r in enumerate(rs):
            ja = plain(r['ja'])
            L = lines_ja(r)
            if CUE.search(ja):
                for j in range(max(0, i - 2), min(len(rs), i + 3)): add(rs[j], 'V1 단서어' if j == i else 'V1 단서어 이웃')
            if len(L) >= 3:
                ends = [endk(l) for l in L]
                ec = collections.Counter(e for e in ends if e and e not in STOP and len(e) == 2)
                if any(v >= 2 for v in ec.values()): add(r, 'V2 각운')
                ms = [mora(l) for l in L]
                if all(any(abs(m - t) <= 1 for t in (5, 7, 12)) for m in ms) and len(set(ms)) <= 3: add(r, 'V3 7·5조')
            h = hira(ja)
            for L4 in range(8, 3, -1):
                found = False
                for s in range(0, len(h) - 2 * L4 + 1):
                    seg = h[s:s + L4]
                    if h.count(seg) >= 2 and not re.fullmatch(r'(.)\1+', seg):
                        add(r, 'V4 칸 안 메아리'); found = True; break
                if found: break
            if any(lc[hira(l)] >= 3 for l in L if mora(l) >= 6): add(r, 'V4 후렴')
    out = []
    for cid, it in sorted(items.items(), key=lambda x: idkey(x[0])):
        r = it['r']
        LJ, LK = lines_ja(r), lines_ko(r)
        m = {'id': cid, 'chap': r['chap'], 'why': sorted(it['why']), 'adult': cid in ad, 'nj': len(LJ), 'nk': len(LK)}
        # 각운 보존
        if 'V2 각운' in it['why'] and len(LJ) == len(LK):
            ends = [endk(l) for l in LJ]
            grp = collections.defaultdict(list)
            for k, e in enumerate(ends):
                if e and e not in STOP: grp[e].append(k)
            kept = tot = 0
            for e, ks in grp.items():
                if len(ks) < 2: continue
                ke = [re.sub(r'[^가-힣]', '', LK[k])[-1:] for k in ks]
                tot += 1
                if len(set(ke)) == 1: kept += 1
            m['rhyme_groups'] = tot; m['rhyme_kept'] = kept
        # 음수율
        if len(LJ) == len(LK) and len(LJ) >= 2:
            rat = [ko_syl(k) / max(1, mora(j)) for j, k in zip(LJ, LK)]
            mu = statistics.mean(rat)
            m['syl_ratio_cv'] = round(statistics.pstdev(rat) / mu, 3) if mu else None
            m['ja_mora'] = [mora(j) for j in LJ]; m['ko_syl'] = [ko_syl(k) for k in LK]
        # 칸 안 메아리
        if 'V4 칸 안 메아리' in it['why']:
            kp = re.sub(r'[^가-힣]', '', plain(r['ko']))
            best = 0
            for L4 in range(6, 2, -1):
                for s in range(0, len(kp) - 2 * L4 + 1):
                    if kp.count(kp[s:s + L4]) >= 2: best = L4; break
                if best: break
            m['ko_echo_len'] = best
        flags = []
        if m.get('rhyme_groups') and m['rhyme_kept'] < m['rhyme_groups']: flags.append('각운 %d/%d 보존' % (m['rhyme_kept'], m['rhyme_groups']))
        if 'V3 7·5조' in it['why'] and m.get('syl_ratio_cv') is not None and m['syl_ratio_cv'] > 0.25: flags.append('음절 비 흩어짐 %.2f' % m['syl_ratio_cv'])
        if 'V4 칸 안 메아리' in it['why'] and m.get('ko_echo_len', 0) < 2: flags.append('메아리 사라짐')
        m['flags'] = flags
        m['ja'] = '' if m['adult'] else flat(r['ja']); m['ko'] = '' if m['adult'] else flat(r['ko'])
        out.append(m)
    json.dump(out, open(os.path.join(DATA, 'verse.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    with open(os.path.join(OUT, 'det_verse.tsv'), 'w', encoding='utf-8') as fo:
        fo.write('칸\t장\t찾은 까닭\t어긋남(숫자)\t원문 모라\t번역 음절\t일본어\t한국어\n')
        for m in out:
            fo.write('%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (m['id'], m['chap'], ','.join(m['why']), '; '.join(m['flags']),
                     m.get('ja_mora', ''), m.get('ko_syl', ''), m['ja'], m['ko']))
    c = collections.Counter(w for m in out for w in m['why'])
    print('items', len(out), dict(c), 'flagged', sum(1 for m in out if m['flags']))


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""검출기 D: 같은 원문의 번역 갈림.

D1 용어 대응표 — 원문 용어 t(가타카나 3자 이상·이름 한자·작품 용어 한자, 원문 3칸 이상)마다
   t 가 든 칸들의 한국어에서 가장 많이 함께 나오는 한글 조각 c*(2~8자)를 대응어로 잡는다.
   일관 비율 = c* 가 든 칸 / t 가 든 칸. c* 가 없는 칸 = 갈림 후보(그 칸에서 c* 대신 쓴 말을 함께 적음).
D2 같은 문장 — 토큰·공백·문장부호를 걷은 원문이 12자 이상이고 2번 이상 나오는데 한국어(같은 방식으로 걷음)가 다른 것.
예외(사용자 결정): 雨森(한자)=아메노모리 / アマモリ=아마모리 는 다른 용어로 따로 센다. ピンチ 핀치/위기 갈림은 사용자 결정(셈하지 않음).
→ out\\det_terms_table.tsv · out\\det_terms_split.tsv · out\\det_same_sentence.tsv
"""
import os, sys, re, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
from kores import is_kanji

NAMES = ['城之崎', '灰流', '九月', '黛', '刈谷', '真季', '雨森', '宮乃', '伽子', '新宿', '都知事', '中野', '牛込', '歌舞伎町',
         '世界樹', '黒丸', '借り暮らし', '借りぐらし', '改賊船', '三月ウサギ', '３月ウサギ', '帽子屋', '野ウサギ', '眠りネズミ',
         '影法師', '天使', '悪魔', '王様', '女王', '魔法使い', '魔女', '巨人', '小人', '海賊', '人魚', '妖精', '迷子', '番人',
         '朝びらき丸', '子豚', '豚', '梟', '熊', '大鴉', '白ウサギ', '黒ウサギ', '犬', '猫', '森', '庭園', '庭', '人間', 'ヒト',
         '贈り物', '招待状', '物語', '冒険', '役割', '宿題', '眠り姫', '鏡', '時計', '帽子', '紅茶', '旅人']
KATA = re.compile(r'[ァ-ヴ][ァ-ヴー・]{2,}')
SKIP_T = {'ピンチ'}   # 사용자 결정
# 의성·의태어·감탄(되풀이, ッ 로 끝남, 작은 모음 겹침)은 문맥마다 달리 옮기는 게 정상 → 뺀다
ONO = re.compile(r'^(.{2,})$|ッ$|[ァィゥェォャュョ]{2}|^(ハハ|フフ|ヘヘ|ホホ|アハ|ウフ|エヘ|イヒ)')


def norm_ko(s):
    return re.sub(r'[\s"「」『』“”‘’\'.,!?…·~～─―\-—()（）\[\]、。！？]', '', plain(s))


def norm_ja(s):
    return re.sub(r'[\s「」『』“”.,!?…・~～─―\-—()（）\[\]、。！？　]', '', plain(s))


def grams(ko):
    out = set()
    for tok in re.findall(r'[가-힣A-Za-zＡ-Ｚａ-ｚ0-9０-９]+(?:[ ·][가-힣]+)?', plain(ko)):
        t = tok.replace(' ', '')
        for L in range(2, min(9, len(t) + 1)):
            for s in range(0, len(t) - L + 1):
                out.add(t[s:s + L])
    return out


def main():
    rows = [r for r in load_corpus() if r['kind'] in ('MSG', 'CHQ', 'CHO') and r['ja'] and not r['hold'] and r['chap']]
    ad = set(json.load(open(os.path.join(DATA, 'adult.json'), encoding='utf-8'))['ids'])
    terms = collections.defaultdict(list)
    for r in rows:
        ja = plain(r['ja'])
        found = set(k.strip('・ー') for k in KATA.findall(ja))
        for n in NAMES:
            if n in ja: found.add(n)
        for t in found:
            if len(t) >= 2 and t not in SKIP_T and not ONO.search(t): terms[t].append(r)
    G = {r['id']: grams(r['ko']) for r in rows}
    df = collections.Counter()
    for g in G.values(): df.update(g)
    table, splits = [], []
    for t, rs in terms.items():
        if len(rs) < 3: continue
        cnt = collections.Counter()
        for r in rs: cnt.update(G[r['id']])
        n = len(rs)
        # 대응어: 지지도 높고(≥40%), t 없는 칸에선 드문(정밀도 ≥0.5) 조각 — 길이 긴 쪽 우선
        best = None
        for c, s in cnt.items():
            if s < max(2, 0.4 * n): continue
            if df[c] > max(20 * n, 60): continue       # 어디에나 나오는 조각(조사·흔한 말)은 대응어가 아니다
            prec = s / df[c]
            key = (s, prec, len(c))
            if best is None or key > best[0]: best = (key, c)
        if not best: continue
        c = best[1]
        # 같은 지지도면 더 긴 조각으로 넓힌다(조사 붙은 것은 빼려고 길이 6까지만)
        for c2, s2 in cnt.items():
            if c in c2 and s2 == cnt[c] and len(c) < len(c2) <= 6 and df[c2] == df[c]: c = c2
        from det_kata import k2h, lev
        kind = '음차' if (KATA.fullmatch(t) and lev(k2h(t), c) <= 0.5) or t in NAMES[:14] else '번역'
        miss = [r for r in rs if c not in G[r['id']]]
        alt = collections.Counter()
        for r in miss:
            cands = [(cnt2, g) for g in G[r['id']] for cnt2 in [cnt[g]] if g not in c and c not in g and len(g) >= 2]
        table.append({'t': t, 'c': c, 'n': n, 'ok': n - len(miss), 'ratio': round((n - len(miss)) / n, 3), 'kind': kind,
                      'miss': [r['id'] for r in miss]})
        for r in miss:
            splits.append((t, c, r['id'], '*' if r['id'] in ad else '', flat(r['ja']), flat(r['ko'])))
    table.sort(key=lambda x: (x['ratio'], -x['n']))
    with open(os.path.join(OUT, 'det_terms_table.tsv'), 'w', encoding='utf-8') as fo:
        fo.write('원문용어\t대응어\t칸수\t대응어든칸\t일관비율\t갈린칸\n')
        for x in table:
            fo.write('%s\t%s\t%d\t%d\t%.3f\t%s\n' % (x['t'], x['c'], x['n'], x['ok'], x['ratio'], ' '.join(x['miss'])))
    json.dump(table, open(os.path.join(DATA, 'terms_table.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    with open(os.path.join(OUT, 'det_terms_split.tsv'), 'w', encoding='utf-8') as fo:
        fo.write('원문용어\t대응어\t칸\t성적구간\t일본어\t한국어\n')
        for t, c, i, a, ja, ko in sorted(splits, key=lambda x: (x[0], idkey(x[2]))):
            if a: ja = ko = '(성적 구간 — 내용 생략)'
            fo.write('%s\t%s\t%s\t%s\t%s\t%s\n' % (t, c, i, a, ja, ko))
    for kd in ('음차', '번역'):
        tb = [x for x in table if x['kind'] == kd]
        tot = sum(x['n'] for x in tb); ok = sum(x['ok'] for x in tb)
        print(kd, 'terms', len(tb), 'cells', tot, 'consistent', ok, 'ratio %.4f' % (ok / tot), 'split', tot - ok)
    # D2 같은 문장
    same = collections.defaultdict(list)
    for r in rows:
        j = norm_ja(r['ja'])
        if len(j) >= 12: same[j].append(r)
    out = []
    for j, rs in same.items():
        if len(rs) < 2: continue
        v = collections.Counter(norm_ko(r['ko']) for r in rs)
        if len(v) > 1:
            out.append((j, rs, v))
    with open(os.path.join(OUT, 'det_same_sentence.tsv'), 'w', encoding='utf-8') as fo:
        fo.write('원문(걷음)\t번수\t변이수\t칸:한국어\n')
        for j, rs, v in sorted(out, key=lambda x: -len(x[1])):
            fo.write('%s\t%d\t%d\t%s\n' % (j, len(rs), len(v), ' ‖ '.join('%s%s: %s' % (r['id'], '*' if r['id'] in ad else '', flat(r['ko']) if r['id'] not in ad else '(생략)') for r in rs)))
    grp = sum(1 for j, rs in same.items() if len(rs) >= 2)
    print('same-sentence groups', grp, 'split groups', len(out), 'cells in split groups', sum(len(rs) for _, rs, _ in out))


if __name__ == '__main__':
    main()

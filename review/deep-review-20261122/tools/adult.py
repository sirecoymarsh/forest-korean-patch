# -*- coding: utf-8 -*-
"""성적 장면 구간 기계 표시(내용은 출력하지 않는다 — 번호와 개수만).

일본어 원문(MSG)·자막 한국어에서 성적 낱말을 세고, 앞뒤 8칸 창의 합이 3 이상이면 그 칸을 '성적 구간'으로 본다.
구간은 표본·서브에이전트 꾸러미에서 통째로 뺀다(미성년 여부를 가리려면 읽어야 하므로 성인 장면도 같이 뺀다 — 보수적).
→ data\\adult.json  {ids: [...], scenes: [[first,last,count], ...]}
"""
import os, sys, json, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

JA_W = ['乳首', '乳房', 'おっぱい', '舐め', '舐る', '挿入', '膣', '精液', '射精', '勃起', 'ペニス', '性器', '股間', '愛液',
        '喘', '犯さ', '犯す', '犯し', '陰茎', '腰を振', '突き上げ', '絶頂', '処女', '秘所', '秘裂', '割れ目', 'クリトリス',
        '陰核', 'フェラ', 'しゃぶ', '肉棒', 'ちんちん', 'ちんぽ', 'ち○', '白濁', '精子', '性交', '交わ', '裸', '濡れて',
        'あそこ', '下着', 'ショーツ', 'パンツ', '胸を', '揉', '太もも', '太腿', '奥まで', '中に出', 'イく', 'イッ', 'イっ',
        '感じちゃ', '気持ちい', '気持ちよ', 'あぁん', 'あんっ', 'ひぁ', 'んぁ', 'セックス', 'エッチ', 'えっち', 'まんこ', '尻', '唾液']
KO_W = ['젖꼭지', '가슴을', '핥', '삽입', '질 ', '정액', '사정', '발기', '페니스', '성기', '사타구니', '애액', '신음', '범해',
        '음경', '허리를 흔', '절정', '처녀', '비부', '클리토리스', '펠라', '빨아', '자지', '보지', '섹스', '알몸', '젖어',
        '속옷', '팬티', '주물', '허벅지', '안에 싸', '가버', '기분 좋', '야한', '엉덩이', '침이']


PUNCT = re.compile(r'[、。，,…・ー～〜っッ！!？?「」『』（）()\s　─―^a-z0-9]')


def score(r):
    t = r['ja'] if r['kind'] in ('MSG', 'CHQ', 'CHO') and r['ja'] else ''
    t2 = PUNCT.sub('', t)
    s = sum(t.count(w) + (t2.count(w) if w not in t else 0) for w in JA_W)
    if r['kind'] == 'SUB' or not t:
        k2 = re.sub(r'[\s,.…·~!?─]', '', r['ko'])
        s += sum(k2.count(w.replace(' ', '')) for w in KO_W)
    return s


def main():
    rows = load_corpus()
    byf = collections.defaultdict(list)
    for r in rows:
        if r['kind'] in ('MSG', 'SUB', 'CHQ', 'CHO'):
            byf[r['file']].append(r)
    flagged, scenes = set(), []
    W = 12
    for f, rs in byf.items():
        rs.sort(key=lambda r: r['seq'])
        sc = [score(r) for r in rs]
        mark = [False] * len(rs)
        for i in range(len(rs)):
            win = sum(sc[max(0, i - W):i + W + 1])
            if win >= 3 and sc[i] > 0:
                for j in range(max(0, i - W), min(len(rs), i + W + 1)):
                    mark[j] = True
        # 정책 보류 칸·성적 구간이 있는 대본은 그 둘레 30칸까지 넓힌다
        hot = [i for i in range(len(rs)) if mark[i] or rs[i]['hold'] == 'cell']
        for i in hot:
            for j in range(max(0, i - 30), min(len(rs), i + 31)):
                mark[j] = True
        i = 0
        while i < len(rs):
            if mark[i]:
                j = i
                while j + 1 < len(rs) and mark[j + 1]: j += 1
                ids = [rs[q]['id'] for q in range(i, j + 1)]
                flagged.update(ids)
                scenes.append([ids[0], ids[-1], len(ids)])
                i = j + 1
            else:
                i += 1
    json.dump({'ids': sorted(flagged, key=idkey), 'scenes': scenes}, open(os.path.join(DATA, 'adult.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    c = collections.Counter(i.split(':')[0] for i in flagged)
    print('flagged cells', len(flagged), 'scenes', len(scenes))
    print(dict(sorted(c.items())))
    hold = [r['id'] for r in rows if r['hold']]
    print('hold cells (file/cell)', len(hold), 'of which flagged', sum(1 for h in hold if h in flagged))
    hc = [r['id'] for r in rows if r['hold'] == 'cell']
    print('held single cells covered by flag:', sum(1 for h in hc if h in flagged), '/', len(hc))


if __name__ == '__main__':
    main()

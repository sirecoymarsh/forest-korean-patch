# -*- coding: utf-8 -*-
"""검출기 재현율 ① — 앞 검수(Claude·GPT)가 실제로 찾은 결함을 옛 판(scr_backup_20261121)에서 검출기가 다시 잡는가.
검출기 재현율 ② — 판정자용 심은 결함 중 검출기 부류(HANJA·FALSE_FRIEND·WASEI·TERM·REGISTER)를 검출기에 넣으면 잡는가.
→ out\\recall_detectors.md
"""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
from kores import kofreq
from det_hanja import carry, F_MAX
from det_kata import KATA, k2h, lev, ko_words

rows = {r['id']: r for r in load_corpus()}
W = {json.loads(l)['voice']: json.loads(l)['text'] for l in open(os.path.join(DATA, 'stt_whisper.jsonl'), encoding='utf-8')}
screen_c = {}
p = os.path.join(DATA, 'screen_carry_out.tsv')
if os.path.exists(p):
    src = {}
    for l in open(os.path.join(DATA, 'screen_carry.tsv'), encoding='utf-8').read().split('\n')[1:]:
        if l: q = l.split('\t'); src[q[0]] = (q[1], q[2])
    for l in open(p, encoding='utf-8').read().split('\n'):
        q = l.split('\t')
        if len(q) >= 2 and q[0] in src: screen_c[src[q[0]]] = q[1]
screen_k = {}
p = os.path.join(DATA, 'screen_kata_out.tsv')
if os.path.exists(p):
    src = {}
    for l in open(os.path.join(DATA, 'screen_kata.tsv'), encoding='utf-8').read().split('\n')[1:]:
        if l: q = l.split('\t'); src[q[0]] = (q[1], q[2])
    for l in open(p, encoding='utf-8').read().split('\n'):
        q = l.split('\t')
        if len(q) >= 2 and q[0] in src: screen_k[src[q[0]]] = q[1]


def det_a_c(ja, ko, word):
    """A(저빈도)·C(선별 FALSE/HANJA) 중 무엇이 그 낱말을 잡나"""
    out = []
    for w, r in carry(ja, ko):
        if word in r or r in word:
            f = kofreq(r)
            tag = []
            if f <= F_MAX: tag.append('A저빈도')
            s = screen_c.get((w, r))
            if s in ('HANJA', 'FALSE'): tag.append('C선별:' + s)
            out.append('%s→%s(빈도%d)%s' % (w, r, f, '[' + ','.join(tag) + ']' if tag else '[못 잡음]'))
    return out


def det_b(ja, ko, word):
    out = []
    ws = ko_words(ko)
    for kw in set(KATA.findall(plain(ja))):
        t = k2h(kw.strip('・'))
        if len(t) < 2 or not ws: continue
        best = min(ws, key=lambda w: lev(t, w))
        if lev(t, best) <= 0.45 and (word in best or best in word):
            f = kofreq(best)
            s = screen_k.get((kw.strip('・'), best))
            out.append('%s→%s(빈도%d)[%s]' % (kw, best, f, ('B선별:' + s) if s else ('B저빈도' if f <= 2 else '못 잡음')))
    return out


KNOWN = [  # (칸, 낱말, 부류) — 앞 검수 보고서(재검수_제미나이5차.md 등)에 적힌 실례, 옛 판 기준
    ('2600:543', '청공', 'HANJA'), ('2600:543', '대해양', 'HANJA'), ('2600:544', '호천하', 'HANJA'), ('2600:545', '외견적', 'HANJA'),
    ('2700:762', '흑점', 'FALSE'), ('2700:764', '흑점', 'FALSE'), ('2700:812', '흑점', 'FALSE'), ('2700:819', '흑점', 'FALSE'),
    ('2700:966', '흑점', 'FALSE'), ('2700:976', '흑점', 'FALSE'), ('2400:282', '원맨', 'WASEI'),
]


def main():
    L = ['# 검출기 재현율\n', '## ① 앞 검수가 찾은 실제 결함을 옛 판에서 다시 잡는가\n',
         '| 칸 | 낱말 | 부류 | 옛 판에 있나 | 검출 결과 |', '|---|---|---|---|---|']
    hit = tot = 0
    for cid, word, cls in KNOWN:
        r = rows[cid]
        ko = r['old']
        ja = r['ja'] if r['kind'] != 'SUB' else W.get(r['voice'], '')
        present = word in ko
        res = (det_b(ja, ko, word) if cls == 'WASEI' else det_a_c(ja, ko, word)) if present else []
        ok = any('[못 잡음]' not in x and '못 잡음' not in x for x in res)
        if present:
            tot += 1; hit += ok
        L.append('| %s | %s | %s | %s | %s |' % (cid, word, cls, '있음' if present else '없음', '; '.join(res) or '—'))
    L.append('\n**재현 %d / %d**\n' % (hit, tot))
    # ② 심은 결함
    PL = [json.loads(l) for l in open(os.path.join(DATA, 'planted.jsonl'), encoding='utf-8')]
    L += ['## ② 판정자용 심은 결함을 검출기에 넣으면\n', '| 칸 | 부류 | 심은 말 | 원문에 대응 낱말 | 검출 결과 |', '|---|---|---|---|---|']
    for p in PL:
        if p['type'] not in ('HANJA', 'FALSE_FRIEND', 'WASEI'): continue
        r = rows[p['id']]
        word = re.sub(r'[^가-힣]', '', p['span'])[:3]
        if p['type'] == 'WASEI':
            res = det_b(r['ja'], p['after'], word)
        else:
            res = det_a_c(r['ja'], p['after'], word)
        L.append('| %s | %s | %s | %s | %s |' % (p['id'], p['type'], p['span'], '있음' if res else '원문에 대응 한자어·가나 없음', '; '.join(res) or '못 잡음'))
    open(os.path.join(OUT, 'recall_detectors.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""지적 명세(findings_spec.py) → 칸마다 지금·고칠 안(토큰 포함 전체 문자열)과 화면 판정.

화면 판정(엔진 규칙): 이 엔진은 글자를 바이트 칸으로 놓는다 — CP949 2바이트 글자 = 2칸, 1바이트 = 1칸
(반각 로마자가 전각 폭에 반각 이동으로 겹쳐 찍히는 현상이 그 증거). 대사창은 57칸에서 접힌다
(3021.gsc 63칸 두 줄이 화면에서 56/57 에서 접힘 — forest-korean-patch 실측). 그래서:
 넘침 = 한 줄 > 57칸 · 대사(MSG) 줄 수 > 3 · 줄 수가 지금보다 늘어남 · ^g### 뒤 반각 숫자 · CP949 로 못 쓰는 글자
→ data\\findings.jsonl
"""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
from findings_spec import F, ADULT_ONLY

rows = {r['id']: r for r in load_corpus()}
W = {json.loads(l)['voice']: json.loads(l)['text'] for l in open(os.path.join(DATA, 'stt_whisper.jsonl'), encoding='utf-8')}
Q = {json.loads(l)['voice']: json.loads(l)['text'] for l in open(os.path.join(DATA, 'stt_qwen.jsonl'), encoding='utf-8')}


def cells(s):
    out = []
    for line in re.split(r'\^n', s):
        t = re.sub(r'\^(g\d{3}|m|c[a-z])', '', line)
        try:
            out.append(len(t.encode('cp949')))
        except UnicodeEncodeError:
            out.append(-1)
    return out


def screen(now, fix, kind):
    p = []
    cn, cf = cells(now), cells(fix)
    if any(c < 0 for c in cf): p.append('CP949 불가 글자')
    if max(cf) > 57: p.append('넘침 %d칸' % max(cf))
    nl = len([c for c in cf]); ol = len(cn)
    if kind == 'MSG' and nl > 3: p.append('줄 수 %d' % nl)
    if nl > ol: p.append('줄 늘어남 %d→%d' % (ol, nl))
    if re.search(r'\^g\d{3}\d', fix): p.append('^g 뒤 숫자')
    return ('통과' if not p else '어긋남: ' + ', '.join(p)), cf


def main():
    per = {}
    order = []
    problems = []
    for k, f in enumerate(F):
        for i in f['ids']:
            if i not in per:
                per[i] = {'fix': rows[i]['ko'], 'specs': []}; order.append(i)
            cur = per[i]['fix']
            old, new = f['old'], f['new']
            if old.startswith('@'):
                o = old[1:]
                if o not in cur: problems.append((i, old)); continue
                cur = cur.replace(o, new[1:] if new.startswith('@') else new, 1)
            else:
                n = cur.count(old)
                if n == 0: problems.append((i, old)); continue
                cur = cur.replace(old, new)
            per[i]['fix'] = cur
            per[i]['specs'].append(k)
    out = []
    for i in order:
        r = rows[i]
        if not per[i]['specs']: continue
        fs = [F[k] for k in per[i]['specs']]
        verdict, cf = screen(r['ko'], per[i]['fix'], r['kind'])
        src = flat(r['ja']) if r['kind'] != 'SUB' else '[음성 %04d] Whisper: %s / Qwen: %s' % (r['voice'], W.get(r['voice'], ''), Q.get(r['voice'], ''))
        out.append({'id': i, 'chap': r['chap'], 'kind': r['kind'], 'spk': r['spk'], 'changed_by_gemini': r['changed'],
                    'cls': '+'.join(sorted({f['cls'] for f in fs})), 'cat': ' / '.join(dict.fromkeys(f['cat'] for f in fs)),
                    'sev': max((f['sev'] for f in fs), key=lambda s: {'minor': 1, 'major': 2, 'critical': 3}[s]),
                    'ja': src, 'now': r['ko'], 'fix': per[i]['fix'], 'why': ' ‖ '.join(dict.fromkeys(f['why'] for f in fs)),
                    'screen': verdict, 'cells': cf})
    dump_jsonl(out, os.path.join(DATA, 'findings.jsonl'))
    import collections
    print('cells', len(out), 'by cls', collections.Counter(o['cls'] for o in out), 'by sev', collections.Counter(o['sev'] for o in out))
    print('screen', collections.Counter(o['screen'] for o in out))
    print('problems', problems)
    print('adult-only numbers', len(ADULT_ONLY))


if __name__ == '__main__':
    main()

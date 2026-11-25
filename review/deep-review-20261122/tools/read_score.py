# -*- coding: utf-8 -*-
"""읽힘 시험 채점: 원문을 모르는 독자(새 모델, 한국어만)가
 - 지금 줄에서 고칠 낱말에 걸렸나(못 알아봄·다른 뜻으로 읽음) → 결함이 독자에게 실제로 보이는가
 - 고친 줄에서는 걸리지 않았나 → 고칠 안이 읽히는가
 - 대조군(두 검수자 모두 OK 한 표본 줄)에서 걸린 비율 → 독자의 헛걸림 기준선
→ data\\read_result.json, 화면 출력
"""
import os, sys, json, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
from findings_spec import F as SPEC

FIND = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(DATA, 'findings.jsonl'), encoding='utf-8')}
spans_old, spans_new = collections.defaultdict(list), collections.defaultdict(list)
for f in SPEC:
    for i in f['ids']:
        spans_old[i].append(re.sub(r'\^n', ' / ', f['old'].lstrip('@')))
        spans_new[i].append(re.sub(r'\^n', ' / ', f['new'].lstrip('@')))


def load(name):
    p = os.path.join(ROOT, 'read', 'out_%s.jsonl' % name)
    if not os.path.exists(p): return {}
    out = {}
    for l in open(p, encoding='utf-8'):
        l = l.strip()
        if l:
            try:
                o = json.loads(l); out[o['rid']] = o
            except Exception:
                pass
    return out


def hit(words, spans):
    for w in words:
        a = re.sub(r'\s', '', w.get('word', ''))
        for s in spans:
            b = re.sub(r'[\s/]', '', s)
            if not a or not b: continue
            if a in b or b in a: return w
            for L in (3, 2):
                if any(a[i:i + L] in b for i in range(len(a) - L + 1)) and len(a) >= L: return w
    return None


def main():
    res = {}
    ctrl = {'flag': 0, 'n': 0}
    for cur, fix, keyf in (('R1', 'R2', '_read_key.json'), ('R3', 'R4', '_read_key2.json')):
        kp = os.path.join(DATA, keyf)
        if not os.path.exists(kp): continue
        key = json.load(open(kp, encoding='utf-8'))
        A, B = load(cur), load(fix)
        if not A or not B: print('missing', cur, fix); continue
        for rid, k in key.items():
            o = A.get(rid) or B.get(rid)
            if o is None: continue
            if k['type'] == 'C':
                ctrl['n'] += 1; ctrl['flag'] += bool(o.get('odd'))
                continue
            i = k['id']
            r = res.setdefault(i, {})
            if rid.startswith(cur):
                w = hit(o.get('odd') or [], spans_old[i])
                r['now'] = ('걸림: %s → %s' % (w['word'], w.get('read_as', ''))) if w else ('다른 곳 걸림' if o.get('odd') else '안 걸림')
                r['now_para'] = o.get('paraphrase', '')
            else:
                w = hit(o.get('odd') or [], spans_new[i])
                r['fix'] = ('걸림: %s → %s' % (w['word'], w.get('read_as', ''))) if w else ('다른 곳 걸림' if o.get('odd') else '안 걸림')
                r['fix_para'] = o.get('paraphrase', '')
    json.dump({'cells': res, 'control': ctrl}, open(os.path.join(DATA, 'read_result.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    c1 = collections.Counter(v.get('now', '—').split(':')[0] for v in res.values())
    c2 = collections.Counter(v.get('fix', '—').split(':')[0] for v in res.values())
    print('cells', len(res), 'now', dict(c1), 'fix', dict(c2), 'control false-alarm %d/%d' % (ctrl['flag'], ctrl['n']))
    good = sum(1 for v in res.values() if v.get('now', '').startswith('걸림') and v.get('fix') == '안 걸림')
    print('지금 걸림 & 고친 안 안 걸림', good)


if __name__ == '__main__':
    main()

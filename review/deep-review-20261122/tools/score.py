# -*- coding: utf-8 -*-
"""검수자 판정 채점: 심은 결함 재현율(유형별), 표본 오류율(층화 추정·95% 신뢰구간), 검수자 일치도(코헨 κ).

  python -I tools\\score.py A B [GPT]    → out\\score.md, data\\flags_union.jsonl
판정 파일: judge\\<이름>\\packet_*.jsonl (GPT 는 judge\\gpt\\result.jsonl 한 파일이면 그것)
"""
import os, sys, json, glob, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

KEY = json.load(open(os.path.join(DATA, '_judge_key.json'), encoding='utf-8'))
PL = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(DATA, 'planted.jsonl'), encoding='utf-8')}
ITEMS = {}
for f in glob.glob(os.path.join(ROOT, 'judge', 'packet_*.jsonl')):
    for l in open(f, encoding='utf-8'):
        o = json.loads(l); ITEMS[o['pid']] = o
POP = json.load(open(os.path.join(DATA, 'population.json'), encoding='utf-8'))
SAMPLE = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(DATA, 'sample.jsonl'), encoding='utf-8')}
SEVW = {'critical': 10, 'major': 5, 'minor': 1, 'neutral': 0}
TYPECAT = {'MEANING': {'ACC-MIS'}, 'OMISSION': {'ACC-OMI'}, 'ADDITION': {'ACC-ADD'}, 'PRONOUN': {'STY-PRON'},
           'REGISTER': {'STY-REG'}, 'TERM': {'TERM', 'LOC'}, 'HANJA': {'FLU-UNNAT:hanja'}, 'WASEI': {'FLU-UNNAT:wasei'},
           'FALSE_FRIEND': {'FLU-UNNAT:falsefriend'}, 'KOREAN': {'FLU-GRAM'}, 'BLATANT': set()}


def load(name):
    out = {}
    fs = glob.glob(os.path.join(ROOT, 'judge', name, '*.jsonl'))
    for f in fs:
        for l in open(f, encoding='utf-8'):
            l = l.strip()
            if not l: continue
            try:
                o = json.loads(l)
            except Exception:
                continue
            out[o.get('pid')] = o
    return out


def errs(o, minsev='minor'):
    if not o or o.get('verdict') != 'ERR': return []
    lv = SEVW[minsev]
    return [e for e in o.get('errors') or [] if SEVW.get(e.get('sev'), 0) >= lv]


def overlap(a, b):
    a, b = (a or '').replace(' ', ''), (b or '').replace(' ', '')
    if not a or not b: return False
    for L in (3, 2):
        for i in range(len(b) - L + 1):
            if b[i:i + L] in a: return True
    return False


def planted_hit(pid, o):
    p = PL[KEY[pid]['id']]
    es = errs(o)
    if not es: return False, False
    if p['type'] in ('OMISSION', 'BLATANT'):
        hit = True
    else:
        hit = any(overlap(e.get('ko_span'), p['span']) for e in es)
    cats = {e.get('cat') for e in es} | {'%s:%s' % (e.get('cat'), e.get('sub')) for e in es}
    typed = hit and (not TYPECAT[p['type']] or bool(cats & TYPECAT[p['type']]))
    return hit, typed


def wilson(k, n, z=1.96):
    if n == 0: return (0, 0, 0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0, c - h), min(1, c + h)


def strat_rate(flag):
    """층화 추정: 층 가중치 N_h/N. 분산 Σ W_h² p_h(1-p_h)/(n_h-1) (n_h=1 이면 전체 p 로 대신)."""
    N = POP['N']
    by = collections.defaultdict(list)
    for cid, s in SAMPLE.items():
        by[s['stratum']].append(1 if flag.get(cid) else 0)
    allk = sum(sum(v) for v in by.values()); alln = sum(len(v) for v in by.values())
    pall = allk / alln
    est = var = 0
    for h, v in by.items():
        Wh = POP['strata'][h]['N'] / N
        ph = sum(v) / len(v)
        est += Wh * ph
        nh = len(v)
        pv = ph if nh > 1 else pall
        var += Wh * Wh * pv * (1 - pv) / max(nh - 1, 1) * (1 - nh / POP['strata'][h]['N'])
    se = math.sqrt(var)
    return est, max(0, est - 1.96 * se), est + 1.96 * se


def kappa(a, b):
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa = sum(a) / n; pb = sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0, po


def main():
    names = sys.argv[1:] or ['A', 'B']
    J = {n: load(n) for n in names}
    L = []
    P = L.append
    P('# 검수자 채점 (%s)\n' % ', '.join(names))
    for n in names:
        miss = [pid for pid in KEY if pid not in J[n]]
        bad = 0
        for pid, o in J[n].items():
            if pid not in ITEMS: continue
            for e in o.get('errors') or []:
                ks = (e.get('ko_span') or '').replace(' ', '')
                if ks and ks not in ITEMS[pid]['ko'].replace(' ', ''): bad += 1
        P('- %s: 판정 %d / %d칸, 빠진 칸 %d, ko_span 이 한국어에 없는 지적 %d' % (n, len(J[n]), len(KEY), len(miss), bad))
    # 심은 결함
    P('\n## 심은 결함 재현율(유형별) — 찾음 / 심음 (괄호: 유형까지 맞힘)\n')
    P('| 유형 | ' + ' | '.join(names) + ' |')
    P('|---|' + '---|' * len(names))
    tot = {n: [0, 0, 0] for n in names}
    types = list(TYPECAT)
    rows = collections.defaultdict(dict)
    for t in types:
        pids = [pid for pid, k in KEY.items() if k['planted'] and PL[k['id']]['type'] == t]
        cells = []
        for n in names:
            h = ty = 0
            for pid in pids:
                a, b = planted_hit(pid, J[n].get(pid))
                h += a; ty += b
                rows[pid][n] = (a, b)
            tot[n][0] += h; tot[n][1] += ty; tot[n][2] += len(pids)
            cells.append('%d/%d (%d)' % (h, len(pids), ty))
        P('| %s | %s |' % (t, ' | '.join(cells)))
    P('| **전체** | %s |' % ' | '.join('**%d/%d** (%d) = %.0f%%' % (tot[n][0], tot[n][2], tot[n][1], 100 * tot[n][0] / tot[n][2]) for n in names))
    if len(names) >= 2:
        both = sum(1 for pid in rows if all(rows[pid][n][0] for n in names[:2]))
        anyh = sum(1 for pid in rows if any(rows[pid][n][0] for n in names[:2]))
        P('\n%s·%s 둘 다 찾음 %d, 하나라도 찾음 %d / %d' % (names[0], names[1], both, anyh, len(rows)))
    P('\n놓친 심은 결함:')
    for pid in sorted(rows):
        m = [n for n in names if not rows[pid][n][0]]
        if m: P('- %s %s %s: 놓침 %s' % (pid, KEY[pid]['id'], PL[KEY[pid]['id']]['type'], ','.join(m)))
    # 표본(진짜 칸)
    holdp = sorted({pid for n in names for pid, o in J[n].items() if o.get('verdict') == 'HOLD' and pid in KEY and not KEY[pid]['planted']})
    real = [pid for pid, k in KEY.items() if not k['planted'] and pid not in holdp]
    for pid in holdp:
        SAMPLE.pop(KEY[pid]['id'], None)
    P('\n정책 보류로 표본에서 뺀 칸(검수자가 HOLD): %d — %s' % (len(holdp), ' '.join(KEY[p]['id'] for p in holdp)))
    P('\n## 표본 %d칸(손대지 않은 칸) — 검수자별 원판정(사람 확인 전)\n' % len(real))
    P('| 검수자 | 오류 칸(minor 이상) | 층화 추정 오류율 [95%] | major 이상 칸 | 층화 추정 [95%] | MQM 점수 합(칸당) |')
    P('|---|---|---|---|---|---|')
    flagsets = {}
    for n in names:
        f1 = {KEY[pid]['id']: bool(errs(J[n].get(pid))) for pid in real}
        f5 = {KEY[pid]['id']: bool(errs(J[n].get(pid), 'major')) for pid in real}
        flagsets[n] = (f1, f5)
        e1 = strat_rate(f1); e5 = strat_rate(f5)
        sc = sum(sum(SEVW.get(e.get('sev'), 0) for e in errs(J[n].get(pid))) for pid in real)
        P('| %s | %d | %.1f%% [%.1f–%.1f] | %d | %.1f%% [%.1f–%.1f] | %d (%.2f) |' % (
            n, sum(f1.values()), 100 * e1[0], 100 * e1[1], 100 * e1[2], sum(f5.values()), 100 * e5[0], 100 * e5[1], 100 * e5[2], sc, sc / len(real)))
    if len(names) >= 2:
        P('\n## 검수자 일치도(표본 %d칸)\n' % len(real))
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                ids = [KEY[pid]['id'] for pid in real]
                k1, p1 = kappa([flagsets[a][0][x] for x in ids], [flagsets[b][0][x] for x in ids])
                k5, p5 = kappa([flagsets[a][1][x] for x in ids], [flagsets[b][1][x] for x in ids])
                P('- %s–%s: 오류 있음/없음 κ = %.2f (일치 %.1f%%) · major 이상 κ = %.2f (일치 %.1f%%)' % (a, b, k1, 100 * p1, k5, 100 * p5))
    open(os.path.join(OUT, 'score.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    # 사람 확인용: 진짜 칸에서 누구라도 짚은 것
    union = []
    for pid in real:
        es = {n: errs(J[n].get(pid)) for n in names}
        if any(es.values()):
            it = ITEMS[pid]
            union.append({'pid': pid, 'id': KEY[pid]['id'], 'chap': it['chap'], 'lt': it['lt'], 'spk': it['spk'],
                          'ja': it.get('ja') or ('W: ' + it.get('asr_whisper', '') + ' | Q: ' + it.get('asr_qwen', '')),
                          'ko': it['ko'], 'context': it['context'], 'by': {n: es[n] for n in names if es[n]}})
    dump_jsonl(union, os.path.join(DATA, 'flags_union.jsonl'))
    print('union flagged real cells', len(union))


if __name__ == '__main__':
    main()

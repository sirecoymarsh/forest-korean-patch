# -*- coding: utf-8 -*-
"""전체 대본 → 칸 말뭉치  data\\corpus.jsonl

칸마다: id(대본:슬롯) file slot chap kind(MSG/SUB/CHQ/CHO/APP) seq(대본 안 명령 순서)
        k(같은 종류 순번) spk(^g 코드) voice ja ko old en changed hold
- MSG 는 일본어 대본의 k번째 0x51 과 짝. SUB 는 일본어 글이 없다(음성뿐) → gem_heard(제미나이 받아쓰기).
- 외곽선(OUT, 0x20 a0=45~48)은 몸체와 같으므로 뺀다.
"""
import os, re, json, glob, collections
import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

HOLD_IDS = set()
for f in glob.glob(r'P:\AI\forest-gemini-review\data\verdicts\*.jsonl'):
    for l in open(f, encoding='utf-8'):
        if l.strip():
            o = json.loads(l)
            if str(o.get('verdict', '')).upper().startswith('HOLD'):
                HOLD_IDS.add(o['id'])

GH = {}
for f in glob.glob(os.path.join(GEM, 'sub_revised_*.json')):
    for x in json.load(open(f, encoding='utf-8')):
        GH['%s:%d' % (x['sid'], x['c_slot'])] = x.get('ja_heard', '')


def dk(b): return b.decode('cp949', 'replace')
def dj(b): return b.decode('cp932', 'replace')


def main():
    rows = []
    stat = collections.Counter()
    for p in sorted(glob.glob(os.path.join(CUR, '*.gsc'))):
        f = os.path.basename(p)
        sid = f[:4]
        cc, cs = walk(p)
        oc, os_ = walk(os.path.join(OLD, f))
        assert cc == oc, 'cmd differs ' + f
        jm, jch = [], []
        if os.path.exists(os.path.join(JA, f)):
            jc, js = walk(os.path.join(JA, f))
            for _, op, a in jc:
                if op == 0x51: jm.append((dj(js[a[5]]), a[1]))
                elif op == 0x0E: jch.append((dj(js[a[1]]), [dj(js[s]) if s else '' for s in a[7:7 + a[0]]]))
        en = walk(os.path.join(EN, f))[1] if os.path.exists(os.path.join(EN, f)) else None
        km = kc = 0
        seq = 0
        voice42 = None
        seen = set()

        def add(slot, kind, **kw):
            nonlocal seq
            if slot in seen: return
            seen.add(slot)
            ko = dk(cs[slot]); old = dk(os_[slot])
            m = re.match(r'\^g(\d{3})', ko)
            i = '%s:%d' % (sid, slot)
            r = dict(id=i, file=sid, slot=slot, chap=CHAP.get(sid), kind=kind, seq=seq,
                     spk=m.group(1) if m else '', ko=ko, old=old, changed=(ko != old),
                     en=dj(en[slot]) if en is not None and slot < len(en) else '',
                     hold=('file' if sid in HOLD_FILES else ('cell' if i in HOLD_IDS else '')))
            r.update(kw)
            rows.append(r); seq += 1
            stat[kind] += 1

        for _, op, a in cc:
            if op == 0x42:
                voice42 = a[0]
            elif op == 0x51:
                ja, jv = jm[km] if km < len(jm) else ('', None)
                add(a[5], 'MSG', k=km, voice=a[1] or None, ja=ja)
                km += 1
            elif op == 0x52:
                add(a[4], 'APP', ja='')
            elif op == 0x20 and a and a[0] == 49:
                add(a[5], 'SUB', voice=voice42, ja='', gem_heard=GH.get('%s:%d' % (sid, a[5]), ''))
            elif op == 0x0E:
                q, opts = jch[kc] if kc < len(jch) else ('', [])
                add(a[1], 'CHQ', k=kc, ja=q)
                for t, s in enumerate(a[7:7 + a[0]]):
                    if s: add(s, 'CHO', k=kc, opt=t, ja=opts[t] if t < len(opts) else '')
                kc += 1
    dump_jsonl(rows, os.path.join(DATA, 'corpus.jsonl'))
    print(dict(stat), 'rows', len(rows))
    body = [r for r in rows if r['kind'] == 'MSG' and r['chap']]
    print('MSG with chapter', len(body), 'changed', sum(r['changed'] for r in body),
          'hold file', sum(r['hold'] == 'file' for r in body), 'hold cell', sum(r['hold'] == 'cell' for r in body))
    sub = [r for r in rows if r['kind'] == 'SUB']
    print('SUB', len(sub), 'changed', sum(r['changed'] for r in sub), 'with gem_heard', sum(bool(r['gem_heard']) for r in sub),
          'voices', len({r['voice'] for r in sub}))
    print('per chap MSG', collections.Counter(r['chap'] for r in body))


if __name__ == '__main__':
    main()

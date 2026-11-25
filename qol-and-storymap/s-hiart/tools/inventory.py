# -*- coding: utf-8 -*-
"""Forest 그림 묶음 목록: 이름·크기(WCG 머리)·무리별 장수."""
import sys, os, struct, json, collections
sys.path.insert(0, r'P:\AI\forest-kr-build\tools')
import xfl
G = r'Y:\AI\forest-qol-test-hiart\game'
out = []
for arc in ['grpe.xfl','grpo.xfl','grpo_bg.xfl','grpo_bu.xfl','grpo_ci.xfl','grpo_f.xfl','grps.xfl']:
    p = os.path.join(G, arc)
    idx = xfl.read_index(p)
    with open(p,'rb') as f:
        for name, off, size in idx:
            f.seek(off); h = f.read(16)
            w = hh = None; kind = h[:2]
            if h[:2] == b'WG':
                flags, bpp, _ = struct.unpack_from('<HHH', h, 2)
                w, hh = struct.unpack_from('<II', h, 8)
                kind = 'WG%04x_%d' % (flags, bpp)
            else:
                kind = h[:4].hex()
            out.append(dict(arc=arc, name=name, size=size, w=w, h=hh, kind=kind))
json.dump(out, open(r'Y:\AI\forest-4k\inventory_raw.json','w',encoding='utf-8'), ensure_ascii=False, indent=0)
by = collections.defaultdict(list)
for e in out: by[e['arc']].append(e)
for arc, es in by.items():
    dims = collections.Counter((e['w'], e['h']) for e in es)
    kinds = collections.Counter(e['kind'] for e in es)
    exts = collections.Counter(os.path.splitext(e['name'])[1] for e in es)
    print(arc, len(es), 'files', sum(e['size'] for e in es)//1024//1024, 'MB')
    print('  ext', dict(exts)); print('  kind', dict(kinds.most_common(6)))
    print('  dims', dims.most_common(12))
    print('  names', [e['name'] for e in es[:12]], '...', [e['name'] for e in es[-6:]])

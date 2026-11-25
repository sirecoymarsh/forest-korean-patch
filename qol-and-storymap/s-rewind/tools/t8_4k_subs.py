# -*- coding: utf-8 -*-
"""큰 창 + 4K 글자·그림에서 자막 자리로 되감기: 처음 지날 때와 되감은 뒤의 그림을 둘 다 남긴다(눈으로 볼 것).
사용: python -I t8_4k_subs.py <출력 이름> [걸음 수]"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv, rw

NAME = sys.argv[1] if len(sys.argv) > 1 else 't8'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 50
r = drv.Run(NAME, settle=1.8); g = r.g
ok = False
try:
    r.start_new_game()
    r.first_pass(N)
    first = list(r.stops); pos = len(first) - 1

    def goto(i, tag, compare=True):
        global pos
        if i < pos:
            b = r.back(pos - i, tag, compare=False)
            if b: pos = i
        elif i > pos:
            r.fwd(i - pos, tag, compare=False); pos = i

    subs = [i for i, s in enumerate(first) if s['sub']]
    plain = [i for i, s in enumerate(first) if not s['sub'] and s['op'] == 0x51 and i > 5]
    r.L('subtitle stops', subs, 'client', g.client())
    saved = 0
    for i in (subs[-3:] + plain[-2:]):
        goto(i + 1, 'past%d' % i)
        goto(i, 'onto%d' % i)
        for wait in (0.0, 2.0):                     # 바로 뒤와 2초 뒤(4배 그림이 뒤늦게 올라오는지)
            if wait: time.sleep(wait)
            img = g.shot()
            sid = first[i]['id']
            ref = r.first_img(sid)
            d = rw.diff(ref, img, r.mask(img), 8)
            r.L('  stop', sid, 'sub' if first[i]['sub'] else 'plain', 'after %.1f s: diff pixels' % (r.settle + wait), d['n'], d.get('box') or '')
            r.cmp.append(dict(tag='onto%d@%.1f' % (i, wait), id=sid, n=d['n'], box=d.get('box')))
            if d['n'] and saved < 6:
                saved += 1
                b = d['box']; pad = 40
                box = (max(0, b[0] - pad), max(0, b[1] - pad), min(img.size[0], b[2] + pad), min(img.size[1], b[3] + pad))
                ref.crop(box).save(os.path.join(r.out, 'sub%02d_%s_first.png' % (saved, sid.replace(':', '_'))))
                img.crop(box).save(os.path.join(r.out, 'sub%02d_%s_again.png' % (saved, sid.replace(':', '_'))))
                r.L('   saved crop', box)
    ok = True
finally:
    try:
        r.summary(ok)
    finally:
        r.finish(ok)

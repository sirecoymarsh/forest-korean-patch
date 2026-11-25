# -*- coding: utf-8 -*-
"""큰 창에서 「맨 처음까지 되감고 다시 읽기」의 작은 화소 차이가 무엇인지 본다(차이 덩어리마다 잘라서 남김)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv, rw
import numpy as np
from PIL import Image

NAME = sys.argv[1] if len(sys.argv) > 1 else 't10'
r = drv.Run(NAME, settle=1.8); g = r.g
ok = False
try:
    r.start_new_game()
    r.first_pass(6)
    r.back(1000, 'all-the-way', compare=False)
    for j in range(5):
        s = g.state(); n0 = len(r.stops)
        if not (s['click'] or s['choice']): s, _ = r.at_stop(40, need_new=False)
        r.go(s)
        s, st = r.at_stop(60, n0)
        img = r.shot(); sid = st['id']
        if sid not in r.shots: continue
        ref = r.first_img(sid)
        d = rw.diff(ref, img, r.mask(img), 8)
        x = np.asarray(ref, dtype=np.int16); y = np.asarray(img, dtype=np.int16)
        dd = np.abs(x - y).max(axis=2)
        for m in r.mask(img): dd[m[1]:m[3], m[0]:m[2]] = 0
        big = dd > 8
        r.L('stop', sid, 'diff pixels', d['n'], d.get('box') or '', 'max level diff', int(dd.max()), 'pixels over 30 levels', int((dd > 30).sum()))
        if d['n']:
            ys, xs = big.nonzero()
            cx, cy = int(np.median(xs)), int(np.median(ys))
            box = (max(0, cx - 60), max(0, cy - 40), cx + 60, cy + 40)
            pair = Image.new('RGB', (120 * 4 * 2 + 6, 80 * 4), (255, 0, 255))
            pair.paste(ref.crop(box).resize((480, 320), Image.NEAREST), (0, 0)); pair.paste(img.crop(box).resize((480, 320), Image.NEAREST), (486, 0))
            pair.save(os.path.join(r.out, 'pair_%s.png' % sid.replace(':', '_')))
            r.L('  saved pair around', (cx, cy))
    ok = True
finally:
    try:
        r.summary(ok)
    finally:
        r.finish(ok)

# -*- coding: utf-8 -*-
"""remnant.py 의 배율이 정수가 아닐 때 판(캡처 크기/800 을 배율로)."""
import glob, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from remnant import stretch
d = sys.argv[1]; bad = 0
files = sorted(glob.glob(os.path.join(d, '*_win.png')))
for f in files:
    n = f[:-8]
    if not os.path.exists(n + '_engine1x.png'): continue
    cap = np.asarray(Image.open(f).convert('RGB')).astype(int); F = np.asarray(Image.open(n + '_engine1x.png').convert('RGB'))
    Hh, Ww = cap.shape[:2]; k = Ww / 800
    up = stretch(F, Ww, Hh).astype(int); sus = []
    for y0 in (478, 504, 530):
        for x0 in range(170, 700, 10):
            if (F[y0:y0 + 24, x0:x0 + 10].max(-1) > 120).sum() < 12: continue
            ys = slice(int(y0 * k), int((y0 + 24) * k)); xs = slice(int(x0 * k), int((x0 + 10) * k))
            a = cap[ys, xs]; b = up[ys, xs]; m = (a.max(-1) > 40) | (b.max(-1) > 40)
            if m.sum() < 30: continue
            mad = np.abs(a - b)[m].mean()
            if mad < 8: sus.append((x0, y0, round(float(mad), 2)))
    if sus: bad += 1; print(os.path.basename(n), sus[:4])
print('frames', len(files), 'with 1x remnant', bad)

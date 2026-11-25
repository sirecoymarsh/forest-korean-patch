# -*- coding: utf-8 -*-
"""캡처에서 흐린 1배 글자가 남은 칸 찾기: 캡처와 「앞 판을 같은 쌍선형으로 늘린 것」이 거의 같은데 글자가 있는 칸."""
import sys, glob, os
import numpy as np
from PIL import Image


def stretch(a, cw, ch):
    h, w, _ = a.shape
    ys = (np.arange(ch) + 0.5) * h / ch - 0.5; xs = (np.arange(cw) + 0.5) * w / cw - 0.5
    y0 = np.floor(ys).astype(int); fy = ys - y0; y1 = np.clip(y0 + 1, 0, h - 1); fy[y0 < 0] = 0; y0 = np.clip(y0, 0, h - 1)
    x0 = np.floor(xs).astype(int); fx = xs - x0; x1 = np.clip(x0 + 1, 0, w - 1); fx[x0 < 0] = 0; x0 = np.clip(x0, 0, w - 1)
    a = a.astype(np.float32)
    top = a[y0][:, x0] * (1 - fx)[None, :, None] + a[y0][:, x1] * fx[None, :, None]
    bot = a[y1][:, x0] * (1 - fx)[None, :, None] + a[y1][:, x1] * fx[None, :, None]
    return np.clip(top * (1 - fy)[:, None, None] + bot * fy[:, None, None] + 0.5, 0, 255).astype(np.uint8)


def check(win, eng, rows=((478, 24), (504, 24), (530, 24)), x_range=(170, 700), k=3):
    cap = np.asarray(Image.open(win).convert('RGB')).astype(int)
    F = np.asarray(Image.open(eng).convert('RGB'))
    up = stretch(F, F.shape[1] * k, F.shape[0] * k).astype(int)
    sus = []
    for y0, hh in rows:
        for x0 in range(x_range[0], x_range[1], 10):
            if (F[y0:y0 + hh, x0:x0 + 10].max(-1) > 120).sum() < 12: continue   # 글자 화소가 넉넉한 칸만
            a = cap[y0 * k:(y0 + hh) * k, x0 * k:(x0 + 10) * k]; b = up[y0 * k:(y0 + hh) * k, x0 * k:(x0 + 10) * k]
            m = (a.max(-1) > 40) | (b.max(-1) > 40)
            if m.sum() < 30: continue
            mad = np.abs(a - b)[m].mean()
            if mad < 8.0: sus.append((x0, y0, round(float(mad), 2)))
    return sus


if __name__ == '__main__':
    d = sys.argv[1]
    bad = 0
    files = sorted(glob.glob(os.path.join(d, '*_win.png')))
    for f in files:
        n = f[:-8]
        s = check(f, n + '_engine1x.png')
        if s: bad += 1; print(os.path.basename(n), s[:6])
    print('frames', len(files), 'with 1x remnant', bad)

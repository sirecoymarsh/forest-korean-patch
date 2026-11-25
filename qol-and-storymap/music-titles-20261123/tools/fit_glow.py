# -*- coding: utf-8 -*-
import numpy as np, itertools, json
from PIL import Image, ImageFilter
B = 'Y:/AI/claude-work/forest-music-titles/back'
H, W, SS = 26, 56, 4


def dil(m, n):
    for _ in range(n):
        p = np.pad(m, 1); m = p[1:-1,1:-1]|p[:-2,1:-1]|p[2:,1:-1]|p[1:-1,:-2]|p[1:-1,2:]|p[:-2,:-2]|p[:-2,2:]|p[2:,:-2]|p[2:,2:]
    return m


def stadium(cx, cy, hx, hy, sig):
    gy, gx = np.mgrid[0:H * SS, 0:W * SS]
    x = (gx + 0.5) / SS - cx; y = (gy + 0.5) / SS - cy
    r = hy; ex = np.maximum(np.abs(x) - (hx - r), 0)
    inside = (ex ** 2 + y ** 2) <= r ** 2
    im = Image.fromarray((inside * 255).astype(np.uint8)).resize((W, H), Image.BOX)
    if sig > 0: im = im.filter(ImageFilter.GaussianBlur(sig))
    return np.array(im).astype(float)


res = {}
for n in (4730, 4740):
    a = np.array(Image.open(f'{B}/ja_{n}.png').convert('RGBA')).astype(float)
    text = (a[..., 2] > 0) & (a[..., 3] > 0)
    dark = (a[..., 3] > 0) & (a[..., :3].sum(2) < (a[..., :3].sum(2)[(~dil(text, 3)) & (a[..., 3] > 250)].mean() * 0.85))
    clean = ~dil(text | dark, 1)
    best = None
    for cx, cy, hx, hy, sig in itertools.product(np.arange(27.0, 29.01, 0.5), np.arange(12.0, 14.01, 0.5), np.arange(23.0, 28.01, 0.5), np.arange(6.0, 10.01, 0.5), (0.6, 0.9, 1.2, 1.6, 2.0)):
        m = stadium(cx, cy, hx, hy, sig)
        e = ((m - a[..., 3]) ** 2)[clean].mean()
        if best is None or e < best[0]: best = (e, cx, cy, hx, hy, sig)
    e, cx, cy, hx, hy, sig = best
    op = clean & (a[..., 3] > 250)
    col = np.median(a[op][:, :3], 0)
    rim = clean & (a[..., 3] > 60) & (a[..., 3] < 250)
    print(n, 'clean px', int(clean.sum()), 'best rmse %.1f' % np.sqrt(e), dict(cx=cx, cy=cy, hx=hx, hy=hy, sig=sig), 'opaque clean color', col.tolist(), 'n', int(op.sum()), 'rim color med', np.median(a[rim][:, :3], 0).tolist() if rim.any() else None)
    res[n] = dict(cx=float(cx), cy=float(cy), hx=float(hx), hy=float(hy), sig=float(sig), color=[float(c) for c in col], rmse=float(np.sqrt(e)))
json.dump(res, open(f'{B}/glow_fit.json', 'w'), indent=1)

# -*- coding: utf-8 -*-
"""달랐던 그림 쌍을 재고(다른 화소 수·가장 큰 차이·뭉친 모양), 눈으로 볼 조각 그림을 만든다.
 - 큰 창(4K 글자·그림)의 화면 견주기에서 몇 화소~수백 화소가 다른 것이 가장자리 몇 화소인지, 덩어리(빠진 그림)인지 가린다.
 - 조각 그림: 처음 | 다시 | 다른 곳(빨강) 을 나란히, 4배로 키워서 out\\<결과 이름>\\ 에 둔다.
사용: python -I diff_review.py <결과 이름> <처음.png> <다시.png> [x0,y0,x1,y1 = 볼 상자(없으면 다른 곳 가운데 가장 큰 덩어리)] [--scale N]"""
import os, sys
import numpy as np
from PIL import Image

OUT = r'Y:\AI\forest-qol-test-rewind\out'
args = [a for a in sys.argv[1:] if not a.startswith('--')]
scale = int(next((a.split('=')[1] for a in sys.argv[1:] if a.startswith('--scale=')), 4))
name, pa, pb = args[0], args[1], args[2]
box = tuple(int(v) for v in args[3].split(',')) if len(args) > 3 else None
a = np.asarray(Image.open(pa).convert('RGB')).astype(np.int16); b = np.asarray(Image.open(pb).convert('RGB')).astype(np.int16)
assert a.shape == b.shape, (a.shape, b.shape)
d = np.abs(a - b).max(axis=2)
m = d > 8
ys, xs = m.nonzero()
print('%s vs %s: size %dx%d, differing pixels (more than 8 levels) %d' % (os.path.basename(pa), os.path.basename(pb), a.shape[1], a.shape[0], len(ys)))
if len(ys):
    print('  box of all differing pixels: (%d, %d, %d, %d)' % (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    v = d[m]
    print('  size of the differences in levels (0-255): max %d, median %d; pixels over 32 levels: %d, over 64: %d, over 128: %d' % (v.max(), int(np.median(v)), int((v > 32).sum()), int((v > 64).sum()), int((v > 128).sum())))
    # 뭉친 덩어리(8방향으로 이어진 것)
    pts = set(zip(xs.tolist(), ys.tolist())); comps = []
    while pts:
        seed = pts.pop(); stack = [seed]; comp = [seed]
        while stack:
            x, y = stack.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in pts: pts.remove(q); stack.append(q); comp.append(q)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    def cbox(c):
        cx = [p[0] for p in c]; cy = [p[1] for p in c]
        return (min(cx), min(cy), max(cx) + 1, max(cy) + 1)
    print('  clumps: %d; the largest: %s' % (len(comps), ', '.join('%d px in %s' % (len(c), cbox(c)) for c in comps[:6])))
    if box is None:
        x0, y0, x1, y1 = cbox(comps[0]); pad = 24
        box = (max(0, x0 - pad), max(0, y0 - pad), min(a.shape[1], x1 + pad), min(a.shape[0], y1 + pad))
if box is None: box = (0, 0, min(a.shape[1], 400), min(a.shape[0], 300))
x0, y0, x1, y1 = box
ca = a[y0:y1, x0:x1].astype(np.uint8); cb = b[y0:y1, x0:x1].astype(np.uint8)
cm = cb.copy(); mm = m[y0:y1, x0:x1]; cm[mm] = (255, 0, 0)
w = x1 - x0; h = y1 - y0
sheet = Image.new('RGB', (w * 3 + 16, h), (40, 40, 40))
for i, c in enumerate((ca, cb, cm)): sheet.paste(Image.fromarray(c), (i * (w + 8), 0))
if scale != 1: sheet = sheet.resize((sheet.size[0] * scale, sheet.size[1] * scale), Image.NEAREST)
if sheet.size[0] > 1800: sheet = sheet.resize((1800, max(1, sheet.size[1] * 1800 // sheet.size[0])), Image.LANCZOS)
os.makedirs(os.path.join(OUT, name), exist_ok=True)
out = os.path.join(OUT, name, 'review_%s_%d_%d.png' % (os.path.splitext(os.path.basename(pb))[0], x0, y0))
sheet.save(out)
print('  crop (first | again | differing in red) box %s -> %s (%dx%d)' % (box, out, sheet.size[0], sheet.size[1]))

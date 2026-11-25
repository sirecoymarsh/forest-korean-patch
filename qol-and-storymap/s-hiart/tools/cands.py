# -*- coding: utf-8 -*-
import json, cv2, numpy as np, os
fc = json.load(open(r'Y:\AI\forest-4k\first_chapter.json'))['uses']
SRC = r'Y:\AI\forest-4k\src'
def skin(p):
    im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    a = im[:, :, 3] if im.shape[2] == 4 else np.full(im.shape[:2], 255, np.uint8)
    ycc = cv2.cvtColor(im[:, :, :3], cv2.COLOR_BGR2YCrCb)
    y, cr, cb = ycc[:, :, 0], ycc[:, :, 1], ycc[:, :, 2]
    m = (cr > 138) & (cr < 175) & (cb > 85) & (cb < 128) & (y > 70) & (a > 128)
    return m.sum() / max(1, (a > 128).sum()), im.shape[1], im.shape[0]
rows = []
for k, v in sorted(fc.items()):
    if v['first'] not in (0, 1): continue
    arc, n = k.split('/')
    p = os.path.join(SRC, arc, n + '.png')
    if not os.path.exists(p): continue
    s, w, h = skin(p)
    rows.append((arc, n, v['first'], round(s, 3), w, h, v['scripts'][:4]))
for r in rows: print(r)
json.dump(rows, open(r'Y:\AI\forest-4k\cands_ch01.json', 'w'))

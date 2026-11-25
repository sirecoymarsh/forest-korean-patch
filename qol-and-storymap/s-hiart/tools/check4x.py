# -*- coding: utf-8 -*-
"""디스크에 쓴 4배 그림을 다시 읽어 따로 검사(만든 쪽 수치와 독립): 크기, 검은 그림, 1배로 줄여 원본과 비교, 넓은 색 이동, 투명도 손실."""
import os, json, numpy as np, cv2
from concurrent.futures import ProcessPoolExecutor
OUT = r'Y:\AI\forest-4k\out'; SRC = r'Y:\AI\forest-4k\src'


def one(row):
    key, fn = row[0], row[1]
    src = cv2.imread(os.path.join(SRC, *key.split('/')) + '.png', cv2.IMREAD_UNCHANGED)
    if src.shape[2] == 3: src = cv2.cvtColor(src, cv2.COLOR_BGR2BGRA)
    out = cv2.imread(os.path.join(OUT, *fn.split('/')), cv2.IMREAD_UNCHANGED)
    if out is None: return key, {'bad': 'unreadable'}
    if out.ndim == 2 or out.shape[2] == 3: out = cv2.cvtColor(out, cv2.COLOR_BGR2BGRA) if out.ndim == 3 else cv2.cvtColor(out, cv2.COLOR_GRAY2BGRA)
    h, w = src.shape[:2]
    r = {}
    if out.shape[:2] != (h * 4, w * 4): return key, {'bad': 'size %s' % (out.shape[:2],)}
    a1 = src[:, :, 3].astype(np.float64)
    vis = a1 > 0
    small = cv2.resize(out, (w, h), interpolation=cv2.INTER_AREA).astype(np.float64)
    if vis.any() and small[:, :, :3][vis].mean() < 2 and src[:, :, :3][vis].mean() > 10: r['bad'] = 'black'
    opaque = a1 == 255
    if opaque.sum() > 100:
        d = np.abs(small[:, :, :3][opaque] - src[:, :, :3].astype(np.float64)[opaque])
        r['mad'] = round(float(d.mean()), 2)
        mse = float((d ** 2).mean()); r['psnr'] = round(99.0 if mse == 0 else 10 * np.log10(255 * 255 / mse), 1)
        # 넓은 색 이동: 32×32 로 흐린 평균색 차이의 최대
        m = opaque.astype(np.float64)   # 불투명 화소만으로 흐린 평균(투명 가장자리 색이 섞이지 않게)
        mb = cv2.blur(m, (31, 31))
        bs = cv2.blur(small[:, :, :3] * m[:, :, None], (31, 31)) / np.maximum(mb, 1e-6)[:, :, None]
        bo = cv2.blur(src[:, :, :3].astype(np.float64) * m[:, :, None], (31, 31)) / np.maximum(mb, 1e-6)[:, :, None]
        inner = mb > 0.98
        r['wide_shift'] = round(float(np.abs(bs - bo)[inner].max()), 1) if inner.any() else 0.0
    if (a1 < 255).any():
        lost = max(0.0, a1.sum() - small[:, :, 3].sum()) / max(1.0, a1.sum()) * 100
        r['lost_alpha'] = round(lost, 2)
    return key, r


if __name__ == '__main__':
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(OUT, 'index.tsv'), encoding='utf-8') if l.strip() and not l.startswith('#')]
    res = {}
    with ProcessPoolExecutor(6) as ex:
        for k, r in ex.map(one, rows, chunksize=8): res[k] = r
    json.dump(res, open(os.path.join(OUT, 'check.json'), 'w'), indent=0, sort_keys=True)
    bad = {k: r for k, r in res.items() if 'bad' in r}
    mads = sorted((r['mad'], k) for k, r in res.items() if 'mad' in r)
    ps = sorted((r['psnr'], k) for k, r in res.items() if 'psnr' in r)
    ws = sorted((r['wide_shift'], k) for k, r in res.items() if 'wide_shift' in r)
    la = sorted((r['lost_alpha'], k) for k, r in res.items() if 'lost_alpha' in r)
    print('checked', len(res), 'bad', len(bad), bad)
    print('opaque MAD: median %.2f max %s' % (mads[len(mads) // 2][0], mads[-3:]))
    print('PSNR(1x): median %.1f min %s' % (ps[len(ps) // 2][0], ps[:3]))
    print('wide colour shift max %s' % ws[-3:])
    print('lost alpha %% max %s (n=%d)' % (la[-3:], len(la)))

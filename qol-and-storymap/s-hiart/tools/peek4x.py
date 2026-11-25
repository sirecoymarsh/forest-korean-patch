import sys, os, numpy as np, cv2
OUT = r'Y:\AI\forest-4k\out'; SRC = r'Y:\AI\forest-4k\src'
key = sys.argv[1]
src = cv2.imread(os.path.join(SRC, *key.split('/')) + '.png', cv2.IMREAD_UNCHANGED)
if src.shape[2] == 3: src = cv2.cvtColor(src, cv2.COLOR_BGR2BGRA)
fn = [l.split('\t')[1] for l in open(os.path.join(OUT, 'index.tsv'), encoding='utf-8') if l.startswith(key + '\t')][0]
out = cv2.imread(os.path.join(OUT, *fn.split('/')), cv2.IMREAD_UNCHANGED)
if out.shape[2] == 3: out = cv2.cvtColor(out, cv2.COLOR_BGR2BGRA)
h, w = src.shape[:2]
small = cv2.resize(out, (w, h), interpolation=cv2.INTER_AREA).astype(np.float64)
op = src[:, :, 3] == 255
m = op.astype(np.float64); mb = cv2.blur(m, (31, 31))
bs = cv2.blur(small[:, :, :3] * m[:, :, None], (31, 31)) / np.maximum(mb, 1e-6)[:, :, None]
bo = cv2.blur(src[:, :, :3].astype(np.float64) * m[:, :, None], (31, 31)) / np.maximum(mb, 1e-6)[:, :, None]
d = np.abs(bs - bo).max(axis=2); d[mb <= 0.98] = 0
y, x = np.unravel_index(np.argmax(d), d.shape)
print(key, 'max wide shift %.1f at (%d,%d) src mean %s out mean %s' % (d[y, x], x, y, bo[y, x].round(1), bs[y, x].round(1)))
pd = np.abs(small[:, :, :3] - src[:, :, :3]).max(axis=2); pd[~op] = 0
print(' per-pixel |diff|>24 share of opaque: %.2f%%' % (100 * (pd > 24).sum() / max(1, op.sum())))
if len(sys.argv) > 2:   # 눈으로: 원본 1배(4배 최근접) | 4배, 최대 차이 자리 둘레 120×90(1배)
    cx, cy = (x, y) if sys.argv[2] == 'auto' else map(int, sys.argv[2].split(','))
    x0, y0 = max(0, min(w - 120, cx - 60)), max(0, min(h - 90, cy - 45))
    bg = np.full((360, 480, 3), 70, np.uint8)
    def comp(img):
        a = img[:, :, 3:4].astype(np.float64) / 255
        return (img[:, :, :3] * a + bg * (1 - a)).astype(np.uint8)
    o1 = cv2.resize(src[y0:y0 + 90, x0:x0 + 120], (480, 360), interpolation=cv2.INTER_NEAREST)
    o4 = out[y0 * 4:y0 * 4 + 360, x0 * 4:x0 * 4 + 480]
    cv2.imwrite(sys.argv[3], np.hstack([comp(o1), np.full((360, 8, 3), 20, np.uint8), comp(o4)]))

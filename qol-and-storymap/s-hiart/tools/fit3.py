import sys, numpy as np, cv2
sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
from fit1 import frame, src

n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
F = frame(n).astype(np.int64)[:, :, :3]
bg = src('.\\grpe\\4040')[:, :, :3].astype(np.int64) >> 1
v = src('.\\grpo_bg\\4203').astype(np.int64)
a = v[:, :, 3:4]
m = ((a[:, :, 0] > 0) & (a[:, :, 0] < 255))
# 글자 자리(아래 대사) 빼기
m[440:, :] = False
s = v[:, :, :3]
cands = {
    '/255 round': (s * a + bg * (255 - a) + 127) // 255,
    '/255 floor': (s * a + bg * (255 - a)) // 255,
    '>>8 a': (s * a + bg * (256 - a)) >> 8,
    '>>8 a+1': (s * (a + 1) + bg * (255 - a)) >> 8,
    'bg+((s-bg)*a>>8)': bg + (((s - bg) * a) >> 8),
    'bg+((s-bg)*a/255)': bg + ((s - bg) * a) // 255,
    'bg+((s-bg)*a/255 trunc0)': bg + np.trunc((s - bg) * a / 255).astype(np.int64),
}
print('semi pixels', m.sum())
for k, c in cands.items():
    d = np.abs(c[m] - F[m])
    print('%-28s exact %.4f  mean %.3f max %d' % (k, (d.max(axis=1) == 0).mean(), d.mean(), d.max()))
more = {
 'sep floor/255': (s * a) // 255 + (bg * (255 - a)) // 255,
 'sep round/255': (s * a + 127) // 255 + (bg * (255 - a) + 127) // 255,
 'sep >>8': (s * a >> 8) + (bg * (255 - a) >> 8),
 'sep >>8 (a,256-a)': (s * a >> 8) + (bg * (256 - a) >> 8),
 'sep >>8 a+1': (s * (a + 1) >> 8) + (bg * (256 - (a + 1)) >> 8),
}
for k, c in more.items():
    d = np.abs(c[m] - F[m])
    print('%-28s exact %.4f  mean %.3f max %d' % (k, (d.max(axis=1) == 0).mean(), d.mean(), d.max()))
# 잔차를 a 에 대해
c = (s * a + bg * (255 - a)) // 255
r = (F - c)[m]; aa = a[:, :, 0][m]
for lo in range(0, 256, 32):
    sel = (aa >= lo) & (aa < lo + 32)
    if sel.any(): print('a %3d-%3d' % (lo, lo + 31), 'mean res', r[sel].mean(axis=0).round(2), 'n', sel.sum())

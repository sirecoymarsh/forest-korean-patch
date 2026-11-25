import sys, numpy as np, cv2
sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
from fit1 import frame, src

F = frame(int(sys.argv[1]) if len(sys.argv) > 1 else 13).astype(np.int32)[:, :, :3]
bg = src('.\\grpe\\4040')[:, :, :3].astype(np.int32)
v = src('.\\grpo_bg\\4203').astype(np.int32)
a = v[:, :, 3]
# 층 10 이 완전 투명한 곳에서 CG 와 화면 비교
m = a == 0
f, b = F[m], bg[m]
print('pixels', m.sum())
for c in range(3):
    x = b[:, c].astype(np.float64); y = f[:, c].astype(np.float64)
    A = np.vstack([x, np.ones_like(x)]).T
    k, c0 = np.linalg.lstsq(A, y, rcond=None)[0]
    print('ch', c, 'fit y = %.4f x + %.2f' % (k, c0), 'max res', np.abs(y - (k * x + c0)).max())
# 표본
for (yy, xx) in [(10, 10), (300, 20), (590, 790), (100, 700)]:
    print((yy, xx), 'frame', F[yy, xx], 'cg', bg[yy, xx], 'a', a[yy, xx])
# 층 10 이 완전 불투명한 곳
m2 = a == 255
d = np.abs(F[m2] - v[:, :, :3][m2])
print('opaque bg layer diff mean', d.mean(), 'max', d.max(), 'n', m2.sum())

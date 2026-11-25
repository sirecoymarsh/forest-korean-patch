"""엔진 화소(bits_*)로 섞기 공식 맞추기: 3차 추적의 frame 과 층 0(4040, >>1)·층 10(4203)."""
import sys, os, numpy as np
TR = r'Y:\AI\forest-qol-test-hiart\game\forest-chart-progress\hiart-trace'


def bits(name, w, h):
    return np.fromfile(os.path.join(TR, 'bits___%s_%dx%d.bgra' % (name, w, h)), np.uint8).reshape(h, w, 4).astype(np.int64)


n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
F = np.fromfile(os.path.join(TR, 'frame_%04d.bgra' % n), np.uint8).reshape(600, 800, 4).astype(np.int64)[:, :, :3]
cg = bits('grpe_4040', 800, 600)[:, :, :3]
v = bits('grpo_bg_4203', 800, 600)
A = v[:, :, 3:4]          # 엔진 투명도(0 = 불투명)
a = 255 - A
s = v[:, :, :3]
for dk, d in [('cg>>1', cg >> 1), ('cg/2 round', (cg + 1) >> 1)]:
    m = (A[:, :, 0] > 0) & (A[:, :, 0] < 255)
    m[440:, :] = False
    cands = {
        '(s*a+d*A)/255': (s * a + d * A) // 255,
        '(s*a+d*A+127)/255': (s * a + d * A + 127) // 255,
        '(s*a+d*A)>>8': (s * a + d * A) >> 8,
        'd+((s-d)*a>>8)': d + (((s - d) * a) >> 8),
        'd+((s-d)*a/255)': d + ((s - d) * a) // 255,
        's+((d-s)*A>>8)': s + (((d - s) * A) >> 8),
        's+((d-s)*A/255)': s + ((d - s) * A) // 255,
        '(s*(a+1)+d*(256-(a+1)))>>8': (s * (a + 1) + d * (255 - a)) >> 8,
        '(s*(256-A)+d*A)>>8': (s * (256 - A) + d * A) >> 8,
        '(s*(255-A)+d*(A+1))>>8': (s * (255 - A) + d * (A + 1)) >> 8,
    }
    print(dk, 'semi', m.sum(), 'opaque-zero-check', np.abs(F[A[:, :, 0] == 0] - s[A[:, :, 0] == 0]).max())
    for k, c in cands.items():
        dd = np.abs(c[m] - F[m])
        print('  %-30s exact %.4f mean %.3f max %d' % (k, (dd.max(axis=1) == 0).mean(), dd.mean(), dd.max()))
print('--- weight per alpha')
d = cg >> 1
m = (A[:, :, 0] > 0) & (A[:, :, 0] < 255); m[440:, :] = False
aa = a[:, :, 0][m]; S = s[m]; D = d[m]; FF = F[m]
for av in sorted(set(aa.tolist()))[::max(1, len(set(aa.tolist())) // 24)]:
    sel = aa == av
    num = ((FF - D) * (S - D))[sel].sum(); den = ((S - D) ** 2)[sel].sum()
    if den > 0: print('a=%3d  w*255=%.2f  n=%d' % (av, 255 * num / den, sel.sum()))

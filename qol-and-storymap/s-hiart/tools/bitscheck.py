import sys, os, glob, numpy as np, cv2
sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
from fnvcheck import bgra
TR = r'Y:\AI\forest-qol-test-hiart\game\forest-chart-progress\hiart-trace'
for p in sorted(glob.glob(os.path.join(TR, 'bits_*.bgra'))):
    base = os.path.basename(p)[5:-5]          # ___grpo_f_0302_394x600
    parts = base.strip('_').split('_')
    wh = parts[-1]; w, h = map(int, wh.split('x'))
    key = '_'.join(parts[:-1])
    folder, num = key.rsplit('_', 1)
    k = folder + '/' + num
    if not os.path.exists('Y:\\AI\\forest-4k\\src\\' + k.replace('/', '\\') + '.png'):
        continue
    e = np.fromfile(p, np.uint8).reshape(h, w, 4).astype(np.int32)
    s = bgra(k).astype(np.int32)
    if s.shape != e.shape:
        print(k, 'shape', s.shape, e.shape); continue
    a = s[:, :, 3]; ea = e[:, :, 3]
    print(k, 'rgb exact where a==255: %.4f' % (np.abs(e[:, :, :3] - s[:, :, :3])[a == 255].max(axis=-1) == 0).mean() if (a == 255).any() else '-',
          'alpha relation:', sorted(set(zip(a.ravel()[::97].tolist(), ea.ravel()[::97].tolist())))[:12])
    semi = (a > 0) & (a < 255)
    if semi.any():
        d = e[:, :, :3][semi] - s[:, :, :3][semi]
        print('   semi n', semi.sum(), 'rgb diff mean', d.mean(axis=0).round(2), 'max', np.abs(d).max())
        # 엔진 rgb 가 미리 곱한 값인가
        pm = s[:, :, :3] * a[:, :, None] // 255
        print('   vs premul diff', np.abs(e[:, :, :3][semi] - pm[semi]).mean().round(3))
        # 알파 대응 전체
        pairs = np.unique(np.stack([a[semi], ea[semi]], 1), axis=0)
        print('   alpha map sample', pairs[::max(1, len(pairs) // 15)].tolist())

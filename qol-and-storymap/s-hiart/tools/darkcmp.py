"""4차 추적: 층 0 의 칸을 어두운 4040(장면 3039)과 밝은 3613(장면 3021) 사이에서 비교 + 화면 밝기 비."""
import sys, os, numpy as np, cv2
sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import trace_read as t
TR4 = r'Y:\AI\claude-work\forest-hiart\trace4'
ev = [e for e in t.read(os.path.join(TR4, 'trace.bin')) if e[0] == 'D']


def frame(n):
    return np.fromfile(os.path.join(TR4, 'frame_%04d.bgra' % n), np.uint8).reshape(600, 800, 4)[:, :, :3].astype(np.float64)


def src(k):
    return cv2.imread('Y:\\AI\\forest-4k\\src\\' + k.replace('/', '\\') + '.png', cv2.IMREAD_COLOR).astype(np.float64)


picks = {}
for e in ev:
    for r in e[3]:
        if r['idx'] == 0 and r['w'] == 800:
            k = r['path'][2:].replace('\\', '/')
            picks.setdefault(k, []).append((e[2], r))
for k in ('grpe/4040', 'grpe/3613'):
    if k not in picks: continue
    n, r = picks[k][-1]
    F = frame(n); S = src(k)
    sel = (S.sum(axis=2) > 60)
    print(k, 'dump', n, 'frame/src brightness ratio %.3f' % (F[sel].mean() / S[sel].mean()))
    picks[k] = r
a, b = picks.get('grpe/4040'), picks.get('grpe/3613')
if isinstance(a, dict) and isinstance(b, dict):
    for name, off, size in (('layer', 0, 0x364), ('img', 0, 0x10c)):
        A = a['L'] if name == 'layer' else a['I']; B = b['L'] if name == 'layer' else b['I']
        diffs = [(o, t.i32(A, o), t.i32(B, o)) for o in range(0, size - 3, 4) if t.i32(A, o) != t.i32(B, o)]
        print(name, 'differing dwords:', ' '.join('%x:%d/%d' % d for d in diffs if abs(d[1]) < 1 << 20 and abs(d[2]) < 1 << 20))

"""전환 분석: 상태가 바뀐 기록 번호 a 앞 화면(옛)과 전환이 끝난 화면(새) 사이를 화면마다 t 로 설명할 수 있나."""
import sys, os, numpy as np
sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import trace_read as t
TR = t.TR


def frame(n):
    return np.fromfile(os.path.join(TR, 'frame_%04d.bgra' % n), np.uint8).reshape(600, 800, 4)[:, :, :3].astype(np.float64)


a, b = int(sys.argv[1]), int(sys.argv[2])     # 바뀐 기록, 끝 기록(안정)
ev = {e[2]: e for e in t.read() if e[0] == 'D'}
old = frame(a - 1)
new = frame(b)
d = new - old
mag = np.abs(d).max(axis=2)
sel = mag > 24
print('changed px', sel.sum())
ys, xs = np.nonzero(sel)
print('bbox', xs.min(), ys.min(), xs.max(), ys.max())
for n in range(a - 1, min(b, a + 40) + 1):
    if n not in ev: continue
    F = frame(n)
    num = ((F - old) * d).sum(axis=2); den = (d * d).sum(axis=2)
    tt = np.where(sel, num / np.maximum(den, 1), np.nan)
    tv = tt[sel]
    res = np.abs(F - (old + np.nan_to_num(tt)[:, :, None] * d)).max(axis=2)[sel]
    # 글로벌 t 로 설명
    tg = float(np.nanmedian(tv))
    resg = np.abs(F - (old + tg * d)).max(axis=2)[sel]
    # 위치별 t 분포(왼쪽·오른쪽·위·아래)
    q = [np.nanmedian(tt[sel & (np.arange(800)[None, :] < 400)]), np.nanmedian(tt[sel & (np.arange(800)[None, :] >= 400)]),
         np.nanmedian(tt[sel & (np.arange(600)[:, None] < 300)]), np.nanmedian(tt[sel & (np.arange(600)[:, None] >= 300)])]
    print('%4d tick %d  t med %.3f p10 %.3f p90 %.3f | global-res p99 %.1f | LRTB %s' % (n, ev[n][1], tg, np.nanpercentile(tv, 10), np.nanpercentile(tv, 90),
          np.percentile(resg, 99), ' '.join('%.2f' % x for x in q)))

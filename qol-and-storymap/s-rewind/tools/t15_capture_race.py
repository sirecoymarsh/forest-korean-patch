# -*- coding: utf-8 -*-
"""찍기 도구(PrintWindow)가 엔진의 그림 합성 한가운데를 찍는 일이 있는가 — 되감기와 상관없이.

t5(h5)에서 95번 견준 것 중 한 번, 대사 2100:3586 의 그림 아래 절반이 검게 찍혔다(위 325줄만 그려지고 대사 창도 글도 없음).
같은 길을 10번 다시 지나며 0.1·0.5·0.9·1.3초에 찍었을 때(t14)는 한 번도 그렇지 않았다.
엔진의 WM_PAINT 처리(0x43df60)는 합성 그림 [엔진+0x9c] 을 잠금 없이 통째로 찍는다(0x43d000) — 찍기 도구가 그 길을 탄다면,
VM 스레드가 그 그림을 다시 짜는 한가운데를 찍을 수 있다. 여기서는 그것을 되감기 없이 확인한다:
처음부터 그냥 읽어 가며(되감기를 한 번도 누르지 않는다) 대사가 클릭을 기다리는 동안 쉬지 않고 찍어, 덜 짜인 그림이 섞여 나오는지 센다.
rewind=0 으로도 돌려 본다(모듈이 꺼져 있어도 나오면 되감기와 무관).
사용: python -I t15_capture_race.py <이름> [대사 수=45] [대사마다 찍는 시간(초)=1.2]"""
import os, sys, time
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv, rw

NAME = sys.argv[1] if len(sys.argv) > 1 else 't15'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 45
DUR = float(sys.argv[3]) if len(sys.argv) > 3 else 1.2
r = drv.Run(NAME); g = r.g


def wait_click(timeout=90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        g.poke(); s = g.state()
        if s['click'] or s['choice']: return s
        if s['typing']: g.w32(0x4663d4, 1)
        if not g.alive(): raise RuntimeError('game exited')
        time.sleep(0.01)
    return None


rows = []; big = []; small = []; total = 0; failed = 0
ok = False
try:
    r.start_new_game()
    cap = None
    for i in range(N):
        s = wait_click()
        assert s, 'no click wait at step %d (%s)' % (i, g.state())
        if s['choice']:
            r.L('choice at step', i, '- answering'); assert r.go(s); continue
        if cap is None: cap = rw.FastCap(g)
        sid = '%04d:%d' % (s['sid'], s['pc'])
        t0 = time.time(); frames = []
        while time.time() - t0 < DUR:
            t = time.time() - t0
            okc, a = cap.grab()
            if not okc: failed += 1; continue
            frames.append((t, a))
        total += len(frames)
        ref = frames[-1][1]
        mask = r.mask(Image.fromarray(ref))
        nb = ns = 0
        for t, a in frames[:-1]:
            n, box = rw.ndiff(ref, a, mask)
            if not n: continue
            if n > 2000:
                nb += 1; big.append(dict(step=i, id=sid, at=round(t, 3), n=n, box=box))
                if len(big) <= 8: Image.fromarray(a).save(os.path.join(r.out, 'big_%02d_%s_at%.3f.png' % (len(big), sid.replace(':', '_'), t)))
                if len(big) <= 8 and nb == 1: Image.fromarray(ref).save(os.path.join(r.out, 'ref_%s.png' % sid.replace(':', '_')))
            else:
                ns += 1; small.append(dict(step=i, id=sid, at=round(t, 3), n=n, box=box))
        rows.append(dict(step=i, id=sid, frames=len(frames), big=nb, small=ns))
        r.L('step %d %s: %d captures in %.1f s, differing from the last one: big %d, small %d%s' % (
            i, sid, len(frames), DUR, nb, ns, ('  ' + str([(b['at'], b['n'], b['box']) for b in big[-nb:]])[:200]) if nb else ''))
        g.key(0x0D)
        g.wait(lambda z: not z['click'], 2.0, 0.005)
    r.L('RESULT lines %d, captures %d (failed %d), half-built pictures %d on %d lines, small differences %d' % (
        len(rows), total, failed, len(big), len(set(b['step'] for b in big)), len(small)))
    if small:
        ats = sorted(x['at'] for x in small)
        r.L('  small differences: when %.2f..%.2f s after the click wait began, sizes %s, boxes %s' % (
            ats[0], ats[-1], sorted(set(x['n'] for x in small))[:12], sorted(set(x['box'] for x in small))[:6]))
    ok = True
finally:
    try:
        r.summary(ok, dict(rows=rows, big=big, small=small[:200], captures=total, failed=failed))
    finally:
        q = r.finish(ok)
        print('RESULT ok %s, normal quit %s' % (ok, q))

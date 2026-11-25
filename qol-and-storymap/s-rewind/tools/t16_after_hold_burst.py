# -*- coding: utf-8 -*-
"""붙잡힌 소리 자막을 Enter 로 넘긴 뒤의 화면을 쉬지 않고 찍는다 — h5 에서 아래 절반이 검게 찍힌 한 번을 다시 내 보려고.

h5 의 그 길: 대사 3278 로 되감음 → Enter 로 소리 자막 3308 에 다시 들어감(다시 보는 것 → 음성이 끝나면 붙잡힘) → 0.5초 뒤 Enter → 전환 → 대사 3586 → 0.5초 뒤 한 장.
같은 날 같은 길을 「자막으로 바로 되감아」 들어간 11번은 온전했다. 그래서 두 가지를 섞는다: fwd(앞 대사에서 Enter 로 들어감) / back(자막으로 바로 되감음).
Enter 를 누른 때부터 쉬지 않고 찍어서, 대사가 클릭을 기다리기 시작한 뒤의 그림들을 처음 지날 때의 그림과 견준다.
 - 덜 된 그림이 한두 장 스쳐 가면: 엔진이 그림을 다시 짜는 한가운데를 찍은 것(찍는 도구의 길).
 - 덜 된 그림이 계속 남으면: 화면이 정말 그렇다 → 고쳐야 한다.
사용: python -I t16_after_hold_burst.py <이름> [되풀이=24] [찍는 시간(초)=2.4] [자막 id] [다음 대사 id] [앞 대사 id]"""
import os, sys, time
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv, rw

NAME = sys.argv[1] if len(sys.argv) > 1 else 't16'
LOOPS = int(sys.argv[2]) if len(sys.argv) > 2 else 24
BURST = float(sys.argv[3]) if len(sys.argv) > 3 else 2.4
UNIT = sys.argv[4] if len(sys.argv) > 4 else '2100:3308'
LINE = sys.argv[5] if len(sys.argv) > 5 else '2100:3586'
PREV = sys.argv[6] if len(sys.argv) > 6 else '2100:3278'
r = drv.Run(NAME, settle=0.45); g = r.g
rows = []; torn_all = []
ok = False
try:
    r.start_new_game()
    n0 = len(r.stops)
    s, st = r.at_stop(150, n0)
    for i in range(80):
        st = r.fwd_lines(1)
        if st['id'] == LINE: break
    assert st['id'] == LINE, 'line not reached'
    cap = rw.FastCap(g)
    time.sleep(1.5)
    okc, ref = cap.grab(); assert okc
    Image.fromarray(ref).save(os.path.join(r.out, 'ref.png'))
    mask = r.mask(Image.fromarray(ref))
    for k in range(LOOPS):
        mode = 'back' if k % 3 == 2 else 'fwd'
        if mode == 'fwd':
            b = r.back(2, 'p%02d' % k, compare=False)
            assert b and b['id'] == PREV, (b and b['id'])
            s = g.state(); n0 = len(r.stops)
            r.go(s)
            s, st = r.at_stop(60, n0)                    # 자막이 붙잡혀 클릭을 기다릴 때 돌아온다
        else:
            b = r.back(1, 'p%02d' % k, compare=False)    # 자막으로 바로: back 이 붙잡힐 때까지 기다린다
            st = r.stops[-1]
        assert st and st['id'] == UNIT and g.state()['click'], (st, g.state())
        r.shot()                                         # h5 와 같은 박자(0.45초 뒤 한 장)
        # Enter → 쉬지 않고 찍는다
        t_enter = time.time(); g.key(0x0D)
        frames = []; t_click = None; released = False
        while time.time() - t_enter < BURST:
            g.poke(); s = g.state()
            if not s['click']: released = True
            if s['typing'] and not s['click']: g.w32(0x4663d4, 1)      # 시험 가속(at_stop 과 같다)
            okc, a = cap.grab(); t = time.time() - t_enter
            if not okc: continue
            at_line = released and bool(s['click'])
            if at_line and t_click is None: t_click = t
            frames.append((t, at_line, a, (s['typing'], s['click'], s['pc'])))
        r.pump()
        assert r.stops[-1]['id'] == LINE, r.stops[-1]
        assert t_click is not None, 'line did not come to its click wait within the burst'
        after = [f for f in frames if f[1]]
        torn = []; small = 0
        for j, (t, _, a, z) in enumerate(after):
            n, box = rw.ndiff(ref, a, mask)
            if n > 2000: torn.append(dict(k=k, mode=mode, at=round(t - t_click, 3), n=n, box=box, state=z, j=j))
            elif n: small += 1
        nl, _ = rw.ndiff(ref, after[-1][2], mask)
        for x in torn[:3]:
            if len(torn_all) < 12:
                Image.fromarray(after[x['j']][2]).save(os.path.join(r.out, 'torn_p%02d_%s_at%.3f.png' % (k, mode, x['at'])))
        torn_all += torn
        rows.append(dict(k=k, mode=mode, t_click=round(t_click, 3), frames_after=len(after), torn=len(torn), small=small, last_diff=nl,
                         torn_at=[x['at'] for x in torn][:40]))
        r.L('pass %d (%s): click wait %.2f s after Enter, %d captures after that: half-built %d%s, small differences %d, last capture differs by %d' % (
            k, mode, t_click, len(after), len(torn), (' at ' + str([x['at'] for x in torn][:12]) + ' box ' + str(torn[0]['box'])) if torn else '', small, nl))
        del frames, after
        s, st = r.at_stop(20, need_new=False)
    bad = [x for x in rows if x['torn']]
    stay = [x for x in rows if x['last_diff']]
    r.L('RESULT passes %d (fwd %d, back %d): with a half-built picture %d (fwd %d, back %d), still wrong at the end of the burst %d' % (
        len(rows), len([x for x in rows if x['mode'] == 'fwd']), len([x for x in rows if x['mode'] == 'back']),
        len(bad), len([x for x in bad if x['mode'] == 'fwd']), len([x for x in bad if x['mode'] == 'back']), len(stay)))
    ok = not stay
finally:
    try:
        r.summary(ok, dict(rows=rows, torn=torn_all[:200]))
    finally:
        q = r.finish(ok)
        print('RESULT ok %s, normal quit %s' % (ok, q))

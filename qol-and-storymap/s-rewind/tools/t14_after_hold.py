# -*- coding: utf-8 -*-
"""붙잡힌 소리 자막을 넘긴 뒤(Enter) 화면 전환을 거쳐 다음 대사가 뜰 때, 화면이 온전한가.
t5(h5)에서 한 번, 그 대사의 그림 아래 절반이 검게 찍혔다(2100:3308 → 전환 → 2100:3586). 찍기 도구의 탓인지 화면이 정말 그런지 가린다:
같은 길을 여러 번 지나며 대사가 뜬 뒤 0.1·0.5·0.9·1.3초에 네 번씩 찍어, 처음 그림과 견준다.
 - 네 장이 모두 같으면 화면은 온전하다.
 - 앞 장만 다르고 뒤 장이 같으면: 그 사이에 화면이 다시 그려졌거나(대기 표시 말고는 다시 그릴 일이 없다) 찍기가 덜 된 것.
사용: python -I t14_after_hold.py <이름> [되풀이=10] [자막 id=2100:3308] [다음 대사 id=2100:3586]"""
import os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv, rw

NAME = sys.argv[1] if len(sys.argv) > 1 else 't14'
LOOPS = int(sys.argv[2]) if len(sys.argv) > 2 else 10
UNIT = sys.argv[3] if len(sys.argv) > 3 else '2100:3308'
LINE = sys.argv[4] if len(sys.argv) > 4 else '2100:3586'
r = drv.Run(NAME, settle=0.45); g = r.g
rnd = random.Random(14)
rows = []
ok = False
try:
    r.start_new_game()
    n0 = len(r.stops)
    s, st = r.at_stop(150, n0)
    first = None
    for i in range(80):
        st = r.fwd_lines(1)
        if st['id'] == LINE:
            time.sleep(1.5); first = g.shot(); first.save(os.path.join(r.out, 'first.png')); break
    assert first is not None, 'line not reached'
    for k in range(LOOPS):
        # 그 자막으로 되감는다(다시 보는 것 → 음성이 끝나면 붙잡힌다)
        h = r.hist()
        hu = [s['hist'] for s in r.stops if s['id'] == UNIT][-1]
        n0 = len(r.stops)
        b = r.press(h - hu)
        assert b and b['id'] == UNIT, (b and b['id'])
        units, _ = r.watch(n0, 60, on_hold='stop')
        assert units and units[-1]['held'], 'not held'
        time.sleep(rnd.uniform(0.0, 1.2))
        n1 = len(r.stops)
        fast = (k % 2 == 0)                       # 번갈아: 전환 효과를 한꺼번에 끝내기(시험 가속과 같은 깃발) / 그대로 두기
        r.fasttype = fast
        t_enter = time.time(); g.key(0x0D)
        # 다음 대사가 다 찍혀 클릭을 기다릴 때까지
        s, st = r.at_stop(60, n1)
        t_ready = time.time()
        assert st and st['id'] == LINE, st
        shots = []
        for at in (0.1, 0.5, 0.9, 1.3):
            while time.time() - t_ready < at: time.sleep(0.01)
            img = g.shot()
            d = rw.diff(first, img, r.mask(img), 8)
            shots.append(d['n'])
            if d['n'] and len([x for x in os.listdir(r.out) if x.startswith('bad_')]) < 6:
                img.save(os.path.join(r.out, 'bad_%02d_at%.1f.png' % (k, at)))
        rows.append(dict(k=k, fast=fast, wait=round(t_ready - t_enter, 2), diffs=shots))
        r.L('pass %d (%s): ready %.2f s after Enter, diff pixels at 0.1/0.5/0.9/1.3 s: %s' % (k, 'effect cut short' if fast else 'effect left alone', t_ready - t_enter, shots))
    bad_any = [x for x in rows if any(x['diffs'])]
    bad_late = [x for x in rows if x['diffs'][-1]]
    r.L('RESULT passes %d, with any differing shot %d, still differing at 1.3 s %d' % (len(rows), len(bad_any), len(bad_late)))
    ok = not bad_late
finally:
    try:
        r.summary(ok, dict(rows=rows))
    finally:
        q = r.finish(ok)
        print('RESULT ok %s, normal quit %s' % (ok, q))

# -*- coding: utf-8 -*-
"""소리 자막이 흐르는 동안의 소리 크기 흐름을 0.25초 칸으로 적어, 처음 지날 때와 되감은 뒤를 나란히 본다.
연달아 흐르는 두 자막(2100:7554 → 2100:7754 → 대사 2100:8144)에서:
 P1 처음 지날 때
 P2 앞 대사(2100:7468)로 되감아 넘김(Enter)
 P3 다음 대사에서 되감기 한 번(둘째 자막부터)
 P4 둘째 자막이 막 시작했을 때 되감기(첫째 자막부터)
사용: python -I t12_env.py <이름> [목표 대사 id=2100:8144]"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv, audio

NAME = sys.argv[1] if len(sys.argv) > 1 else 't12'
TARGET = sys.argv[2] if len(sys.argv) > 2 else '2100:8144'
r = drv.Run(NAME, settle=0.3); g = r.g
found = []


def peak_now():
    global found
    if not found: found = audio.sessions(g.pid)
    try:
        p, m = audio.peak(found)
    except OSError:
        audio.release(found); found = []; return -1.0          # 못 읽은 표시
    if m is False: g.mute()
    return p


def watch(n0, timeout=120, press_at=None):
    """다음에 클릭을 기다리며 멈출 때까지: 그 사이의 (시각, 소리 크기)와 자리 사건을 모두 적는다.
    press_at = (자막 id, 뜬 뒤 초): 그 자막이 뜨고 그만큼 지나면 되감기 한 번."""
    seen = n0; t0 = time.time(); env = []; marks = []; pressed = False
    while time.time() - t0 < timeout:
        g.poke(); r.pump(); now = time.time()
        while seen < len(r.stops):
            st = r.stops[seen]; seen += 1
            marks.append((now - t0, st['id'], st['unit']))
        env.append((now - t0, peak_now()))
        if press_at and not pressed:
            m = [t for t, i, u in marks if i == press_at[0] and u]
            if m and now - t0 - m[-1] >= press_at[1]:
                g.rewind(1); pressed = True; marks.append((now - t0, 'PRESS', False))
        z = g.state()
        if (z['click'] or z['choice']) and len(r.stops) > n0 and not r.stops[-1]['unit'] and seen == len(r.stops):
            time.sleep(0.05); r.pump()
            if seen == len(r.stops): return env, marks
        if z['typing'] and not z['click']: g.w32(0x4663d4, 1)
        if not g.alive(): raise RuntimeError('game exited')
        time.sleep(0.006)
    raise RuntimeError('no stop')


def show(tag, env, marks):
    """자리 사건마다 그 뒤의 소리 크기를 0.25초 칸의 가장 큰 값으로."""
    r.L('== %s' % tag)
    pts = [(t, i) for t, i, u in marks]
    for k, (t, i) in enumerate(pts):
        end = pts[k + 1][0] if k + 1 < len(pts) else env[-1][0]
        cells = []
        a = t
        while a < end:
            v = [p for tt, p in env if a <= tt < min(a + 0.25, end)]
            bad = any(p < 0 for p in v)
            cells.append(('??' if bad else '%2d' % min(99, int(round(max(v or [0]) * 100)))))
            a += 0.25
        r.L('   %-10s +%.2fs for %.2fs | %s' % (i, t, end - t, ' '.join(cells)))
    return dict(tag=tag, marks=marks, env=[(round(t, 3), round(p, 4)) for t, p in env])


out = []
ok = False
try:
    g.skip_events()
    assert g.wait_title()
    time.sleep(1.0)
    g.w16(0x466450, 0)
    time.sleep(0.3)
    g.click(607, 286)
    n0 = len(r.stops)
    s, st = r.at_stop(150, n0)
    order = [st['id']]
    last = None
    for i in range(200):
        n0 = len(r.stops); r.go(g.state())
        env, marks = watch(n0)
        ids = [m[1] for m in marks]
        if ids[-1] == TARGET:
            out.append(show('P1 first pass (from %s)' % order[-1], env, marks)); order.append(ids[-1]); break
        order.append(ids[-1])
    assert order[-1] == TARGET, 'target not reached: %s' % order[-5:]
    units = [m[1] for m in out[0]['marks'] if m[2]]
    prev = order[-2]
    r.L('units', units, 'line before', prev)
    # P2: 앞 대사로 되감아 넘김
    b = r.back(len(units) + 1, 'to-prev', compare=False)
    assert b and b['id'] == prev, b
    n0 = len(r.stops); r.go(g.state())
    env, marks = watch(n0); out.append(show('P2 back to the line before, then Enter', env, marks))
    # P3: 다음 대사에서 되감기 한 번
    n0 = len(r.stops); g.rewind(1)
    env, marks = watch(n0); out.append(show('P3 one rewind at the next line', env, marks))
    # P4: 한 번 더, 그리고 마지막 자막이 막 시작했을 때(0.15초) 다시
    if len(units) > 1:
        n0 = len(r.stops); g.rewind(1)
        env, marks = watch(n0, press_at=(units[-1], 0.15)); out.append(show('P4 rewind again right after the last one started', env, marks))
    ok = True
finally:
    g.w16(0x466450, 1)
    try:
        json.dump(out, open(os.path.join(r.out, 'env.json'), 'w', encoding='utf-8'))
        r.summary(ok)
    finally:
        audio.release(found)
        q = r.finish(ok)
        print('RESULT ok %s, normal quit %s' % (ok, q))

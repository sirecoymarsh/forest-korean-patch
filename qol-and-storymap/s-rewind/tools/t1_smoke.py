# -*- coding: utf-8 -*-
"""연기 시험: 타이틀 → 처음부터 → 몇 줄 넘김 → 되감기 한 번 → 정상 종료. 상태 흐름을 그대로 적는다."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rw

OUT = r'Y:\AI\forest-qol-test-rewind\out\t1'
g = rw.Game(OUT)
ok = False
try:
    g.skip_events()
    s = g.wait_title()
    g.L('title', s, 'client', g.client() if g.h else None)
    assert s, 'title not reached'
    time.sleep(1.0)
    g.shot('00_title')
    for l in g.new_events(): g.L('  ev', l)
    g.click(607, 286)                      # 처음부터
    last = None; stops = 0; t0 = time.time(); shots = 0
    while time.time() - t0 < 150 and stops < 14:
        g.poke()
        s = g.state()
        key = (s['sid'], s['pc'], s['click'], s['typing'], s['choice'], s['select'], s['depth'], s['nested'])
        if key != last:
            g.L('state', s); last = key
        if s['click']:
            stops += 1
            time.sleep(0.25)
            if shots < 4: g.shot('stop_%02d' % stops); shots += 1
            g.key(0x0D)                    # Enter
            g.wait(lambda z: not z['click'] or (z['sid'], z['pc']) != (s['sid'], s['pc']), 5)
        elif s['choice']:
            g.L('choice reached'); g.shot('choice_%02d' % stops); break
        else:
            time.sleep(0.05)
    for l in g.new_events(): g.L('  ev', l)
    # 지금 멈춘 자리에서 되감기 한 걸음
    s = g.wait(lambda z: z['click'] == 1, 30)
    g.L('before rewind', s)
    time.sleep(0.5); a = g.shot('before_rewind')
    g.rewind(1)
    time.sleep(0.2)
    s2 = g.wait(lambda z: z['click'] == 1, 20)
    g.L('after rewind', s2)
    time.sleep(0.8); b = g.shot('after_rewind')
    for l in g.new_events(): g.L('  ev', l)
    ok = True
finally:
    q = g.quit() if g.alive() and g.h else False
    g.L('normal quit', q, 'ok', ok)
    for l in g.new_events()[-6:]: g.L('  ev', l)
    g.close()

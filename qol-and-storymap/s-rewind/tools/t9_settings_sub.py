# -*- coding: utf-8 -*-
"""원래 결함 확인: 노란 자막이 떠 있는 대사에서 설정 화면(오른쪽 클릭)을 열었다 닫으면 자막이 돌아오는가.
되감기와 무관한 엔진 동작이다(되감기 요청은 한 번도 보내지 않는다).
사용: python -I t9_settings_sub.py <출력 이름> [걸음 수]"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv, rw

NAME = sys.argv[1] if len(sys.argv) > 1 else 't9'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 60
r = drv.Run(NAME, settle=0.5); g = r.g
checks = []


def check(name, cond, extra=''):
    checks.append(dict(name=name, ok=bool(cond), extra=str(extra)))
    r.L(('YES ' if cond else 'NO  ') + name, extra)


ok = False
try:
    r.start_new_game()
    # 자막이 있는 자리에 닿을 때까지 읽는다(자막 자리에서 멈춤)
    n0 = len(r.stops); hit = None
    for i in range(N):
        s, st = r.at_stop(60, n0)
        assert s, 'no stop'
        n0 = len(r.stops)
        if st['sub'] and st['op'] == 0x51 and i > 5: hit = st; break
        r.go(s)
    assert hit, 'no subtitle stop within %d stops' % N
    before = r.shot()
    before.save(os.path.join(r.out, 'before_settings.png'))
    g.click(400, 300, button='r')
    opened = g.wait(lambda z: z['settings'] == 1, 6)
    time.sleep(0.8)
    g.click(400, 300, button='r')
    closed = g.wait(lambda z: z['settings'] == 0, 6)
    g.wait(lambda z: z['click'] == 1, 10)
    after = r.shot()
    after.save(os.path.join(r.out, 'after_settings.png'))
    d = rw.diff(before, after, r.mask(after), 8)
    r.L('subtitle stop', hit['id'], 'settings opened', bool(opened), 'closed', bool(closed), 'diff', d)
    # 자막 자리(논리 좌표 170~790 × 44~200) 안에서 달라진 화소
    box = d.get('box')
    in_sub = bool(box) and box[1] < 210 and box[0] >= 160
    check('settings screen opened and closed at a subtitle line', opened and closed)
    check('screen is the same after closing the settings screen (subtitle kept)', d['n'] == 0, 'diff pixels %s box %s' % (d['n'], box))
    check('the difference is in the subtitle area', in_sub, box)
    # ---- 같은 자리에서 저장 → 두 줄 읽고 → 불러오기(엔진의 「다시 세우기」 길): 자막이 돌아오는가
    n = len(r.other)
    g.post(0x104, 0x30, 0x20000001); g.post(0x105, 0x30, 0xE0000001)     # Alt+0 = 0번 칸에 저장(원작 키)
    t0 = time.time()
    while time.time() - t0 < 6:
        r.pump(); g.poke()
        if any('save 0 fingerprint' in l or 'save not verified' in l for l in r.other[n:]): break
        time.sleep(0.1)
    saved = any('save 0 fingerprint' in l for l in r.other[n:])
    r.fwd(2, 'after-save', compare=False)
    g.w16(0x466468, 0)
    g.key(ord('L'))
    opened = g.wait(lambda z: g.u32(0x466414) == 1, 8)
    time.sleep(0.8)
    nst = len(r.stops)
    g.click(235, 168)
    g.answer_yes()
    s2, st2 = r.at_stop(40, nst)
    loaded = r.shot()
    loaded.save(os.path.join(r.out, 'after_load.png'))
    d2 = rw.diff(before, loaded, r.mask(loaded), 8)
    box2 = d2.get('box')
    r.L('saved', saved, 'load screen', bool(opened), 'loaded stop', st2 and st2['id'], 'want', hit['id'], 'diff', d2)
    check('saved at the subtitle line and loaded it back', saved and st2 and st2['id'] == hit['id'])
    check('screen after LOAD equals the screen before (subtitle kept)', d2['n'] == 0, 'diff pixels %s box %s' % (d2['n'], box2))
    check('after LOAD the difference is in the subtitle area (logical y < 210)', bool(box2) and box2[1] < 210 and box2[3] < 260, box2)
    ok = True
finally:
    try:
        r.summary(ok, dict(checks=checks))
    finally:
        r.finish(ok)

# -*- coding: utf-8 -*-
"""대화창을 숨긴 채(Shift) Backspace 를 누르면.

원작: Shift = 대화창 숨기기/되돌리기([0x466420], 숨기기 0x416570, 되돌리기 0x4165b0). 숨긴 동안의 클릭·Enter 는 대화창만 되돌리고 넘기지 않는다.
바라는 것: 숨긴 채 Backspace → 대화창이 돌아오고 앞 대사가 보인다(처음 지날 때와 같은 화면), 숨김 깃발은 내려가 있고, 그 뒤 Enter 한 번에 다음 대사로 간다.
큰 창(4K 글자·그림)에서는 T18_SETTLE=1.6 T18_TOL=2000 으로(뒤 스레드 합성을 기다리고, 글자 가장자리 몇 화소는 봐준다).
사용: python -I t18_hidden.py <이름>"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv, rw

NAME = sys.argv[1] if len(sys.argv) > 1 else 't18'
TOL = int(os.environ.get('T18_TOL', '0'))
r = drv.Run(NAME, settle=float(os.environ.get('T18_SETTLE', '0.45'))); g = r.g
checks = []
HID = 0x466420


def check(name, cond, extra=''):
    checks.append(dict(name=name, ok=bool(cond), extra=str(extra)))
    r.L(('PASS ' if cond else 'FAIL ') + name, extra)


ok = False
try:
    r.start_new_game()
    r.first_pass(6)
    lines = [s for s in r.stops if s['op'] == 0x51]
    cur, prev = lines[-1], lines[-2]
    assert r.stops[-1]['id'] == cur['id'] and r.stops[-2]['id'] == prev['id'], 'the last two stops are not both lines: %s' % [s['id'] for s in r.stops[-3:]]
    r.L('at', cur['id'], 'the line before it is', prev['id'])
    # 숨기기
    g.key(0x10); hid = g.wait(lambda z: g.u32(HID) == 1, 3, 0.05)
    img = r.shot(); d = rw.diff(r.first_img(cur['id']), img, r.mask(img), 8)
    check('Shift hides the message window', bool(hid) and d['n'] > 5000 + TOL, 'flag %d, pixels changed %d %s' % (g.u32(HID), d['n'], d.get('box')))
    img.save(os.path.join(r.out, 'hidden.png'))
    # 숨긴 채 Backspace
    b = r.press(1, key=True)
    check('Backspace while hidden goes one step back', b and b['id'] == prev['id'], r.desc(b))
    s, st = r.at_stop(20, need_new=False)
    time.sleep(0.3)
    flag = g.u32(HID)
    img = r.shot(); d = rw.diff(r.first_img(prev['id']), img, r.mask(img), 8)
    img.save(os.path.join(r.out, 'after_backspace.png'))
    check('the message window is back and shows the earlier line as in the first pass', d['n'] <= TOL, 'diff pixels %d %s' % (d['n'], d.get('box')))
    check('the hidden flag is down', flag == 0, 'flag %d' % flag)
    # Enter 한 번에 다음 대사로
    n0 = len(r.stops); g.key(0x0D)
    s, st = r.at_stop(8, n0)
    check('one Enter goes on to the next line', bool(s) and st and st['id'] == cur['id'], 'stop %s, flag %d' % (st and st['id'], g.u32(HID)))
    if not s:
        g.key(0x0D); s, st = r.at_stop(8, n0)
        r.L('a second Enter:', st and st['id'])
    img = r.shot(); d = rw.diff(r.first_img(cur['id']), img, r.mask(img), 8)
    check('that line looks as in the first pass', d['n'] <= TOL, 'diff pixels %d %s' % (d['n'], d.get('box')))
    # 견줄 것: 숨기고 되돌리기(Shift 두 번)는 원래대로
    g.key(0x10); g.wait(lambda z: g.u32(HID) == 1, 3, 0.05); time.sleep(0.3)
    g.key(0x10); g.wait(lambda z: g.u32(HID) == 0, 3, 0.05)
    img = r.shot(); d = rw.diff(r.first_img(cur['id']), img, r.mask(img), 8)
    check('Shift twice still hides and shows as before', g.u32(HID) == 0 and d['n'] <= TOL, 'flag %d, diff pixels %d' % (g.u32(HID), d['n']))
    bad = [v for v in r.verifies if not v['same']]
    check('engine state the same whenever a step was passed again', not bad, '%d same, %d different' % (sum(1 for v in r.verifies if v['same']), len(bad)))
    ok = all(c['ok'] for c in checks)
finally:
    try:
        r.summary(ok, dict(checks=checks, checks_passed='%d/%d' % (sum(c['ok'] for c in checks), len(checks))))
    finally:
        q = r.finish(ok)
        print('RESULT checks %d/%d, normal quit %s' % (sum(c['ok'] for c in checks), len(checks), q))

# -*- coding: utf-8 -*-
"""합본 교차 시험: 여섯 모듈(화면·진행·아이콘 줄·4K 글자·4K 그림·되감기)을 한 DLL 로 합친 판을 숨은 데스크톱에서 큰 창으로 띄워
서로 맞물리는 곳을 본다. 11-21 통합 시험(P:\\AI\\forest-qol\\tools\\cross.py, 24가지)을 이 몰이로 옮기고 되감기 항목을 더했다.
(옛 시험은 사용자 화면의 바깥 자리에 창을 띄웠다. 이 몰이는 숨은 데스크톱이라 초점을 뺏지 않고, 놀이 사본과 동시에 떠도 된다.)

먼저: prep_copy.py present=1 hitext=1 hiart=1. 불러오기 화면 1쪽 첫 칸(0번)에 대사 자리의 저장이 있어야 한다(t3 가 만든다).
창 기억 파일은 끝나고 시험 전으로 되돌린다.
사용: python -I t20_cross.py <이름>"""
import os, re, shutil, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv, rw

NAME = sys.argv[1] if len(sys.argv) > 1 else 't20'
WINMEM = os.path.join(rw.GAME, 'forest-qol-window.ini')
KEEP = WINMEM + '.t20keep'
if os.path.exists(WINMEM): shutil.copyfile(WINMEM, KEEP)
r = drv.Run(NAME, settle=1.6); g = r.g
checks = []


def check(name, cond, extra=''):
    checks.append(dict(name=name, ok=bool(cond), extra=str(extra)))
    r.L(('PASS ' if cond else 'FAIL ') + name, extra)


def other_since(n, pat):
    r.pump()
    return [l for l in r.other[n:] if re.search(pat, l)]


def wait(fn, sec=10, step=0.1):
    t0 = time.time()
    while time.time() - t0 < sec:
        g.poke(); r.pump()
        if fn(): return True
        time.sleep(step)
    return False


def pc_now():
    sc = g.u32(0x46639c)
    return g.u32(sc + 0x44) if sc else 0


ok = False
try:
    g.skip_events()
    check('title reached', bool(g.wait_title()), g.state()['sid'])
    time.sleep(1.5)
    w, hh = g.client()
    check('enlarged window by default', w > 800 and hh > 600, '%dx%d' % (w, hh))
    ev = open(g.events_path(), encoding='utf-8', errors='replace').read()[-20000:]
    for mod in ('present', 'play', 'buttons', 'hitext', 'hiart', 'rewind'):
        check('module %s ok' % mod, ('qol: %s ok' % mod) in ev)
    g.shot('a_title')

    # Home 안내(타이틀)
    g.key(0x24); time.sleep(0.9); g.shot('b_guide_title'); g.key(0x24); time.sleep(0.6)
    # 타이틀에서 S = 거절
    n = len(r.other); g.key(ord('S')); time.sleep(0.6); g.shot('c_S_title')
    check('S refused at title', not other_since(n, r'S -> slot \d+ saved'))

    # L = 불러오기 화면 → 0번 칸 → 확인 「예」
    g.w16(0x466468, 0)             # 불러오기 화면이 1쪽에서 열리게
    g.key(ord('L'))
    check('L opens load screen at title', wait(lambda: g.u32(0x466414) == 1, 8))
    time.sleep(0.8); g.shot('d_load_screen')
    g.click(235, 168); g.answer_yes()
    okl = wait(lambda: g.state()['sid'] >= 2000 and g.state()['click'] == 1, 40)
    check('loaded slot 0 into a story line', okl, g.state())
    time.sleep(r.settle); g.shot('e_line_hitext')

    # 아이콘 줄: 자동 단추(늘린 창 좌표)
    n = len(r.other)
    g.click(678, 593)
    on = wait(lambda: g.state()['auto'] == 1, 5)
    check('auto button (scaled) -> auto on', on)
    check('auto button went through play module', bool(other_since(n, 'auto button')), other_since(n, 'auto')[-3:])
    time.sleep(1.5); g.shot('f_auto_x1')
    g.key(ord('A')); time.sleep(0.6); g.shot('f_auto_x2')
    pc0 = pc_now()
    check('auto advances by itself (x2)', wait(lambda: pc_now() != pc0, 20))
    # 자동 중 Backspace = 자동 끄고 한 걸음 뒤로
    wait(lambda: len(r.stops) >= 3, 30)                    # 되감을 걸음이 쌓일 때까지
    nb = len(r.backs)
    g.key(0x08)
    off = wait(lambda: g.state()['auto'] == 0, 5)
    went = wait(lambda: len(r.backs) > nb, 3)
    check('Backspace during auto: auto off and one step back', off and went, 'auto off %s, went back %s %s' % (off, went, r.backs[-1]['id'] if r.backs else ''))
    wait(lambda: g.state()['click'] == 1, 20)
    time.sleep(r.settle); g.shot('g_auto_off')

    # 되감기(큰 창): 한 줄 넘겼다가 Backspace → 같은 화면
    time.sleep(4.0)                                        # 바로 앞에서 소리 자막이 처음 붙잡혔으면 알림 한 줄(3.5초)이 떠 있다 → 사라진 뒤에 뜬다(j20 에서 그 알림 자리만큼 달랐다)
    a = g.shot()
    aid = r.stops[-1]['id']
    n0 = len(r.stops); g.key(0x0D)
    r.watch(n0, 60)
    nb = len(r.backs); n0 = len(r.stops)
    for k in range(4):                                     # 사이에 소리 자막 걸음이 있으면 더 누른다
        g.key(0x08)
        wait(lambda: len(r.backs) > nb + k, 4)
        if r.backs and r.backs[-1]['id'] == aid: break
        time.sleep(0.4)
    wait(lambda: g.state()['click'] == 1, 30)
    time.sleep(r.settle); b = g.shot(); b.save(os.path.join(r.out, 'g_rewound.png'))
    d = rw.diff(a, b, r.mask(b), 8)
    check('rewind in the big window returns to the same picture (4K text and art)', r.backs and r.backs[-1]['id'] == aid and d['n'] < 2000,
          'at %s (want %s), diff pixels %d of %d %s' % (r.backs[-1]['id'] if r.backs else None, aid, d['n'], a.size[0] * a.size[1], d.get('box') or ''))

    # 지도 단추
    n = len(r.other); g.click(661, 593)
    check('map button (scaled) opens chart', wait(lambda: bool(other_since(n, 'ui opened')), 8))
    time.sleep(1.0); g.shot('h_chart')
    g.key(0x1B)
    check('chart closed with AUDIT PASS', wait(lambda: bool(other_since(n, 'AUDIT PASS')), 8))
    time.sleep(0.8)

    # 오른쪽 클릭 = 설정 화면
    g.click(400, 300, button='r')
    check('right click still opens settings', wait(lambda: g.state()['settings'] == 1, 6))
    time.sleep(0.8); g.shot('i_settings')
    g.click(400, 300, button='r')
    wait(lambda: g.state()['settings'] == 0, 6); wait(lambda: g.state()['click'] == 1, 10)

    # S = 바로 저장(알림)
    n = len(r.other); g.key(ord('S')); time.sleep(0.5); g.shot('j_S_toast')
    sv = other_since(n, r'S -> slot \d+ saved')
    check('S saves to a slot in story', bool(sv), other_since(n, 'play: S')[-2:])

    # 3배 창(창 메뉴)
    g.post(0x112, 0xEEF0, 0); time.sleep(1.2)
    w3, h3 = g.client()
    check('x3 window via system menu', w3 >= 2300, '%dx%d' % (w3, h3))
    g.key(ord('A')); time.sleep(1.2); g.shot('k_x3_auto')
    g.key(0x08); wait(lambda: g.state()['auto'] == 0, 5)
    wait(lambda: g.state()['click'] == 1, 20); time.sleep(0.8); g.shot('k_x3_line')
    check('auto on by A and off by Backspace in the x3 window', g.state()['auto'] == 0 and g.state()['click'] == 1)

    # 전체 화면(Alt+Enter) 왕복
    g.post(0x104, 0x0D, 0x20000001); g.post(0x105, 0x0D, 0xE0000001)
    time.sleep(1.5); wf, hf = g.client()
    check('Alt+Enter fullscreen (no mode change)', (wf, hf) in ((4096, 2160), (3840, 2160), (1440, 2560)), '%dx%d' % (wf, hf))
    g.shot('l_full')
    g.post(0x104, 0x0D, 0x20000001); g.post(0x105, 0x0D, 0xE0000001)
    time.sleep(1.5); wb, hb = g.client()
    check('Alt+Enter back to window', (wb, hb) == (w3, h3), '%dx%d' % (wb, hb))

    # 아이콘 줄 자동 단추로 켜고 클릭으로 끄기(엔진 원래 길)
    wait(lambda: g.state()['click'] == 1, 20)
    g.click(678, 593); ok1 = wait(lambda: g.state()['auto'] == 1, 5)
    time.sleep(0.8); g.click(400, 300); ok2 = wait(lambda: g.state()['auto'] == 0, 5)
    check('auto via button then click off', ok1 and ok2)
    wait(lambda: g.state()['click'] == 1, 20)

    r.pump()
    errs = [l for l in r.other + r.events if re.search(r'(?i)exception|AUDIT FAIL|failed|error', l)]
    check('no error lines in events.log', not errs, errs[-5:])
    bad = [v for v in r.verifies if not v['same']]
    check('engine state and run journal equal whenever a step was passed again', not bad, '%d same, %d different' % (sum(1 for v in r.verifies if v['same']), len(bad)))
    ok = all(c['ok'] for c in checks)
finally:
    try:
        r.summary(ok, dict(checks=checks, checks_passed='%d/%d' % (sum(c['ok'] for c in checks), len(checks))))
    finally:
        r.release_audio()
        q = r.finish(ok)
        checks.append(dict(name='normal quit', ok=bool(q), extra=''))
        if os.path.exists(KEEP): shutil.copyfile(KEEP, WINMEM); os.remove(KEEP)
        print('RESULT checks %d/%d, normal quit %s' % (sum(c['ok'] for c in checks), len(checks), q))

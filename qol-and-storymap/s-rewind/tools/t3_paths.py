# -*- coding: utf-8 -*-
"""되감기 갈래 시험: 글이 찍히는 중·선택지에서·선택지로 되감기, 그리고 「다녀온 뒤 다른 부분이 안 깨지나」
(설정 화면 열고 닫기, 이야기의 지도, 저장 → 불러오기, 엔진의 「직전 선택지로」 단추, 정상 종료)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv

NAME = sys.argv[1] if len(sys.argv) > 1 else 't3'
r = drv.Run(NAME); g = r.g
checks = []


def check(name, cond, extra=''):
    checks.append(dict(name=name, ok=bool(cond), extra=str(extra)))
    r.L(('PASS ' if cond else 'FAIL ') + name, extra)


def other_has(text, since):
    r.pump()
    return any(text in l for l in r.other[since:])


ok = False
try:
    r.start_new_game()
    r.first_pass(14)

    # ---- 1) 글이 찍히는 중에
    r.fasttype = False
    caught = False
    for attempt in range(4):
        n0 = len(r.stops); cur = r.stops[-1]['id']
        g.key(0x0D)
        t0 = time.time(); z = None
        while time.time() - t0 < 12:
            r.pump(); z = g.state()
            if len(r.stops) > n0 and (z['typing'] or z['click']): break
            time.sleep(0.004)
        typing = bool(z and z['typing'] and not z['click'])
        b = r.back(1, 'while-typing%d' % attempt)
        check('rewind requested %s -> previous stop' % ('while text is typing' if typing else 'at click wait (text already done)'), b and b['id'] == cur,
              'target %s got %s key-to-start %.1f ms' % (cur, b and b['id'], b['wake'] if b else -1))
        if typing: caught = True; break
        r.fwd_lines(1, 'retry-typing')
    check('caught a line while typing', caught)
    r.fasttype = True

    # ---- 2) 선택지
    b = r.back(1000, 'to-first-choice')
    s = g.state()
    check('all the way back lands on the first choice', b and b['id'] == '1000:162' and s['choice'] == 1, s)
    r.fwd_lines(1, 'answer-leaf')              # 사이의 소리 자막(2100:100)은 다시 보는 것이라 붙잡힌다 → Enter 로 넘긴다
    s = g.state()
    check('next line or choice is the choice 2100:300', s['choice'] == 1 and r.stops[-1]['id'] == '2100:300', r.stops[-1])
    b = r.back(1, 'choice-to-subtitle', compare=False)
    s = g.state()
    check('one step back from a choice is the sound subtitle before it, held', b and b['id'] == '2100:100' and s['click'] == 1 and s['choice'] == 0, s)
    b = r.back(1, 'subtitle-to-choice')
    s = g.state()
    check('one more step lands on the previous choice', b and b['id'] == '1000:162' and s['choice'] == 1, s)
    r.fwd_lines(3, 'answer-again')
    check('answered both choices again and reached a line', r.stops[-1]['id'] == '2100:1234' and g.state()['click'] == 1, r.stops[-1])
    b = r.back_to_line(1, 'line-to-choice')
    s = g.state()
    check('going back past the sound subtitle lands on the choice before the line', b and b['id'] == '2100:584' and s['choice'] == 1, s)
    r.fwd_lines(8, 'reread')

    # ---- 3) 설정 화면 열고 닫기(엔진 자신의 화면 다시 세우기와 맞는지)
    cur = r.stops[-1]['id']
    g.click(400, 300, button='r')
    opened = g.wait(lambda z: z['settings'] == 1, 6)
    time.sleep(0.7)
    g.click(400, 300, button='r')
    closed = g.wait(lambda z: z['settings'] == 0, 6)
    back_at = g.wait(lambda z: z['click'] == 1, 10)
    check('settings screen opens and closes after rewinds', opened and closed and back_at)
    d = r.compare('after-settings', cur, r.shot())
    check('screen after settings equals first pass', d and d['n'] == 0, d)

    # ---- 4) 이야기의 지도
    n = len(r.other)
    g.key(0x77)   # F8
    t0 = time.time()
    while time.time() - t0 < 8 and not other_has('ui opened', n): g.poke(); time.sleep(0.1)
    opened = other_has('ui opened', n)
    time.sleep(0.6); g.key(0x1B)
    t0 = time.time()
    while time.time() - t0 < 8 and not other_has('AUDIT', n): g.poke(); time.sleep(0.1)
    check('story map opens and closes with AUDIT PASS', opened and other_has('AUDIT PASS', n), [l for l in r.other[n:] if 'AUDIT' in l][-1:])
    g.wait(lambda z: z['click'] == 1, 10)
    d = r.compare('after-map', cur, r.shot())
    check('screen after map equals first pass', d and d['n'] == 0, d)

    # ---- 5) 되감은 자리에서 저장 → 몇 줄 읽고 → 불러오기
    b = r.back_to_line(2, 'before-save')      # 대사 자리에서 저장한다(소리 자막 걸음에서 저장하면 그 앞 대사가 저장된다 — t13)
    saved_at = b['id'] if b else None
    n = len(r.other)
    g.post(0x104, 0x30, 0x20000001); g.post(0x105, 0x30, 0xE0000001)     # Alt+0 = 0번 칸에 저장(원작 키)
    t0 = time.time()
    while time.time() - t0 < 6 and not (other_has('save 0 fingerprint', n) or other_has('save not verified', n)): g.poke(); time.sleep(0.1)
    check('save after rewind verified by the map module', other_has('save 0 fingerprint', n), [l for l in r.other[n:] if 'save' in l][-1:])
    r.fwd_lines(3, 'after-save')
    g.w16(0x466468, 0)          # 불러오기 화면이 1쪽에서 열리게(0번 칸이 왼쪽 맨 위)
    g.key(ord('L'))
    opened = g.wait(lambda z: g.u32(0x466414) == 1, 8)
    time.sleep(0.8)
    nst = len(r.stops)
    g.click(235, 168)
    t = g.answer_yes()
    tl0 = time.time()
    s, st = r.at_stop(40, nst)
    load_ms = (time.time() - tl0) * 1000
    r.pump()
    check('load screen -> slot 0 -> loaded', opened and s and st and st['id'] == saved_at, 'dialog %s stop %s want %s; from confirm to line ready about %.0f ms (text typed at once)' % (t, st, saved_at, load_ms))
    check('history cleared on load', 'load' in r.cleared, r.cleared)
    if st:
        d = r.compare('after-load', st['id'], r.shot())
        check('screen after load equals first pass', d and d['n'] == 0, d)
    nb = len(r.backs)
    r.back(1, 'right-after-load', compare=False)
    check('rewind right after load is refused', len(r.backs) == nb and r.refused and r.refused[-1] == 'no earlier stop', r.refused[-1:])
    r.fwd_lines(2, 'post-load')
    b = r.back(1, 'post-load-back')
    check('rewind works again after reading on', b is not None)

    # ---- 6) 엔진의 「직전 선택지로」 단추(아이콘 줄 rev)
    nst = len(r.stops); ncl = len(r.cleared)
    tr0 = time.time()
    g.click(694, 592)          # 아이콘 줄 rev(11-21 아이콘 줄 그림 기준 x 688~701)
    s, st = r.at_stop(40, nst)
    rev_ms = (time.time() - tr0) * 1000
    r.pump()
    check('engine previous-choice button lands on a choice', s and s['choice'] == 1, '%s %s; click to choice ready about %.0f ms (includes 230 ms of posted click)' % (s, st, rev_ms))
    check('history cleared on engine rollback', any('engine rollback' in c for c in r.cleared[ncl:]), r.cleared[ncl:])
    r.fwd_lines(3, 'after-engine-rollback')
    b = r.back(1, 'after-engine-rollback-back')
    check('rewind works after engine rollback', b is not None)
    errs = [l for l in r.other if any(k in l.lower() for k in ('exception', 'audit fail', 'error', 'disabled after'))]
    check('no error lines', not errs, errs[-3:])
    ok = all(c['ok'] for c in checks)
finally:
    try:
        r.summary(ok, dict(checks=checks, checks_passed='%d/%d' % (sum(c['ok'] for c in checks), len(checks))))
    finally:
        q = r.finish(ok)
        print('RESULT checks %d/%d, normal quit %s' % (sum(c['ok'] for c in checks), len(checks), q))

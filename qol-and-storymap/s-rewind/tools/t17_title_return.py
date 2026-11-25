# -*- coding: utf-8 -*-
"""타이틀로 돌아갔다가 새로 시작하면 걸음이 새로 쌓이는가.

엔진은 판을 새로 시작할 때 VM 스레드를 끝내고 새로 만든다(멈추기 0x420600 → 깃발 지우기 → 시작 0x4205b0, 스레드 번호는 [0x4663bc]).
되감기 모듈은 「VM 스레드가 바뀌었다」로 옛 걸음을 버린다 — 새 스레드가 옛 번호를 다시 받으면 못 알아챈다. 실제로 어떤지 본다:
 1) 몇 대사 읽는다 → 타이틀로(Alt+E, 확인 창이 뜨면 「예」) → 타이틀에서 Backspace 는 거절
 2) 처음부터 → 첫 자리에서 Backspace: 「더 앞이 없다」여야 한다(옛 판의 대사로 가면 안 된다)
 3) 여러 번 되풀이하며 스레드 번호가 어떻게 바뀌는지 적는다
타이틀로 가는 길은 둘이다:
 - alte: Alt+E(엔진이 VM 스레드를 새로 만든다. 이야기의 끝 = 명령 0x08 도 VM 을 끝내고 새로 만든다)
 - goto: 대본이 타이틀 대본으로 갈아탄다(명령 0x0c 1 — 같은 VM 스레드 그대로. 타이틀 대본 0001 의 끝, 지도에서 연 다시보기가 끝난 뒤가 이 길이다).
         시험에서는 대사가 클릭을 기다리는 동안 다음 명령 자리에 `0c 00 01 00 00 00` 을 써 넣고 Enter 를 누른다(시험 사본의 메모리에만, 대본을 다시 읽으면 사라진다).
사용: python -I t17_title_return.py <이름> [되풀이=4] [alte|goto]"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv, rw

NAME = sys.argv[1] if len(sys.argv) > 1 else 't17'
LOOPS = int(sys.argv[2]) if len(sys.argv) > 2 else 4
HOW = sys.argv[3] if len(sys.argv) > 3 else 'alte'
r = drv.Run(NAME); g = r.g
checks = []


def check(name, cond, extra=''):
    checks.append(dict(name=name, ok=bool(cond), extra=str(extra)))
    r.L(('PASS ' if cond else 'FAIL ') + name, extra)


def vm_tid(): return g.u32(0x4663bc)


def at_title(timeout=40):
    return g.wait(lambda z: z['sid'] == 1 and z['select'] == 1, timeout, 0.1)


tids = []
ok = False
try:
    r.start_new_game()
    n0 = len(r.stops)
    s, st = r.at_stop(150, n0)
    assert s, 'no first stop'
    first_id = st['id']
    for k in range(LOOPS):
        for i in range(4 + k): st = r.fwd_lines(1)
        h = r.hist(); t_old = vm_tid(); tids.append(t_old)
        r.L('round %d: read to %s, history %d, VM thread %d' % (k, st['id'], h, t_old))
        # 타이틀로
        nc = len(r.cleared)
        if HOW == 'goto':
            z = g.state(); assert z['click'], z
            sc = g.u32(0x46639c); cur = g.u32(sc + 0x44)
            r.L('round %d: writing "goto script 1" at the next command of %04d (+0x%x)' % (k, z['sid'], cur - g.u32(sc)))
            wr = rw.ctypes.c_size_t()
            rw.kernel32.WriteProcessMemory(g.hp, rw.ctypes.c_void_p(cur), bytes([0x0c, 0, 1, 0, 0, 0]), 6, rw.ctypes.byref(wr))
            g.key(0x0D); dlg = None
        else:
            g.post(0x104, ord('E'), 0x20000001); time.sleep(0.05); g.post(0x105, ord('E'), 0xE0000001)
            dlg = g.answer_yes(5)
        s = at_title()
        check('round %d: back at the title (%s)' % (k, HOW), bool(s), 'dialog %r, state %s' % (dlg, g.state()))
        if not s: break
        time.sleep(1.0); r.pump()
        t_new = vm_tid()
        r.L('round %d: at the title, VM thread %d (%s), history cleared so far: %s' % (k, t_new, 'same number as before' if t_new == t_old else 'new number', r.cleared[nc:]))
        nr = len(r.refused); nb = len(r.backs)
        g.key(0x08); time.sleep(0.5); r.pump()
        check('round %d: Backspace at the title does nothing' % k, len(r.backs) == nb, 'refused %s' % r.refused[nr:])
        # 처음부터
        g.w16(0x466450, 1); time.sleep(0.5)
        n0 = len(r.stops)
        g.click(607, 286)
        if HOW == 'goto':
            check('round %d: the earlier steps were thrown away at the title' % k, 'back at the title' in r.cleared[nc:], 'cleared %s' % r.cleared[nc:])
        s, st = r.at_stop(25 if HOW == 'goto' else 150, n0)
        if not s and HOW == 'goto':
            # 이 길은 시험이 지어낸 것이다(대본 깊이 2 에서 타이틀 대본으로 갈아탐). 타이틀 단추가 안 먹으면 여기서 그만둔다.
            r.L('round %d: the made-up title (script depth %d) did not start a new game: state %s' % (k, g.state()['depth'], g.state())); break
        assert s, 'no first stop after starting again'
        r.pump()
        check('round %d: the new game starts at the same first stop' % k, st['id'] == first_id, '%s (first time %s), its history number %d' % (st['id'], first_id, st['hist']))
        check('round %d: the earlier steps were thrown away' % k, st['hist'] == 1, 'history %d, cleared %s' % (st['hist'], r.cleared[nc:]))
        nr = len(r.refused); nb = len(r.backs)
        g.key(0x08); time.sleep(0.6); r.pump()
        check('round %d: Backspace at the first stop of the new game has nowhere to go' % k, len(r.backs) == nb and 'no earlier stop' in r.refused[nr:],
              'went back %d time(s)%s, refused %s' % (len(r.backs) - nb, (' to ' + r.backs[-1]['id']) if len(r.backs) > nb else '', r.refused[nr:]))
    tids.append(vm_tid())
    r.L('VM thread numbers over the rounds:', tids, '- repeated:', len(tids) - len(set(tids)))
    ok = all(c['ok'] for c in checks)
finally:
    try:
        r.summary(ok, dict(checks=checks, checks_passed='%d/%d' % (sum(c['ok'] for c in checks), len(checks)), vm_threads=tids))
    finally:
        q = r.finish(ok)
        print('RESULT checks %d/%d, normal quit %s' % (sum(c['ok'] for c in checks), len(checks), q))

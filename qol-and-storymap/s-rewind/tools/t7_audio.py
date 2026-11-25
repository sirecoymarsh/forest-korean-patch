# -*- coding: utf-8 -*-
"""되감은 자리에서 소리가 다시 나오는지: 음소거한 채로 프로세스 소리 세션의 크기(peak)를 읽는다.
배경음은 설정 깃발([0x466450])로 꺼 두고(음성·효과음만 남게) 본다.
 ① 처음 지날 때 소리가 났던 자리로 되감으면 다시 소리가 나는가(대사 음성, 자막 음성)
 ② 처음 지날 때 조용했던 자리로 되감으면 조용한가(뒤 대사의 음성이 남아 울리지 않는가)"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv, audio

NAME = sys.argv[1] if len(sys.argv) > 1 else 't7'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 90
r = drv.Run(NAME, settle=0.05); g = r.g
found = []


def listen(sec):
    global found
    best = 0.0; t0 = time.time(); mutedall = True
    while time.time() - t0 < sec:
        g.poke()
        if not found: found = audio.sessions(g.pid)
        try:
            p, m = audio.peak(found)
        except OSError:
            audio.release(found); found = []; p, m = 0.0, True
        best = max(best, p)
        if m is False: mutedall = False; g.mute()
        time.sleep(0.015)
    return best, mutedall


checks = []


def check(name, cond, extra=''):
    checks.append(dict(name=name, ok=bool(cond), extra=str(extra)))
    r.L(('PASS ' if cond else 'FAIL ') + name, extra)


ok = False
try:
    g.skip_events()
    assert g.wait_title()
    time.sleep(1.0)
    pk, m = listen(2.0)
    check('meter works while muted (title music is heard by the meter)', pk > 0.005 and m, 'peak %.4f muted %s' % (pk, m))
    g.w16(0x466450, 0)             # 배경음 끔(설정 화면의 「배경음」과 같은 깃발) → 뒤로는 음성·효과음만
    time.sleep(0.3)
    g.click(607, 286)              # 처음부터
    rec = []                       # (id, peak, sub, voice)
    n0 = len(r.stops)
    for i in range(N):
        s, st = r.at_stop(60, n0)
        assert s, 'no stop'
        n0 = len(r.stops)
        pk, m = listen(0.7)
        rec.append(dict(id=st['id'], peak=pk, sub=st['sub'], voice=st['voice'], op=st['op'], hist=st['hist']))
        if not m: r.L('WARNING: session was not muted at', st['id'])
        r.go(s)
    s, st = r.at_stop(60, n0)
    loud = [i for i, x in enumerate(rec) if x['peak'] > 0.02 and x['op'] == 0x51]
    quiet = [i for i, x in enumerate(rec) if x['peak'] < 0.002 and x['op'] == 0x51 and i > 3]
    subs = [i for i, x in enumerate(rec) if x['sub'] and x['voice']]
    r.L('first pass: %d stops, loud %d, quiet %d, subtitle+voice %d' % (len(rec), len(loud), len(quiet), len(subs)))

    def onto(i, tag):
        """rec[i] 자리로 되감기(뒤에서 한 번에). 걸음 수 = 줄의 길이 차이(사이의 소리 자막 걸음 포함)."""
        k = r.hist() - rec[i]['hist']
        b = r.back(k, tag, compare=False) if k > 0 else None
        assert b is None or b['id'] == rec[i]['id'], (rec[i]['id'], b['id'])
        return b

    # 뒤에서부터 차례로(되감기만으로 닿게): 큰 자리 4곳, 조용한 자리 3곳, 자막 자리 3곳
    targets = sorted(set(loud[-4:] + quiet[-3:] + subs[-3:]), reverse=True)
    # 대조(되감기 없이): 음성이 긴 대사에서 음성이 울리는 동안 그냥 넘기면(Enter) 다음 자리에서 음성 꼬리가 얼마나 남는가
    ctl = [i for i in loud if i + 1 < len(rec) and rec[i + 1]['op'] == 0x51 and not rec[i + 1]['voice'] and not rec[i + 1]['sub'] and i + 1 not in loud]
    if ctl and rec[ctl[-1]]['hist'] < r.hist():
        i = ctl[-1]
        b = onto(i, 'control%d' % i)          # 그 대사로 가면 음성이 처음부터 다시 나온다
        if b:
            time.sleep(0.5)
            s0 = g.state(); n0 = len(r.stops)
            r.go(s0)                           # 음성이 울리는 동안 그냥 넘김(원작 동작)
            s1, st1 = r.at_stop(40, n0)
            e1, _ = listen(0.4); l1, _ = listen(1.3)
            r.L('CONTROL plain advance during the voice of %s -> %s: first 0.4 s %.4f, then 1.3 s %.4f (first pass at that stop %.4f)' % (rec[i]['id'], st1 and st1['id'], e1, l1, rec[i + 1]['peak']))
            checks.append(dict(name='control: plain advance during a long voice', ok=True, extra='next stop %s: first 0.4 s %.4f, then 1.3 s %.4f' % (st1 and st1['id'], e1, l1)))
    for i in targets:
        if rec[i]['hist'] >= r.hist(): continue
        b = onto(i, 'audio%d' % i)
        if not b: continue
        x = rec[i]
        early = 0.0
        if x['peak'] < 0.002: early, _ = listen(0.4)     # 떠나온 대사의 음성은 엔진이 끊는다 — 끊기는 꼬리(짧게 잦아듦)는 따로 적는다
        pk, m = listen(1.3)
        kind = 'subtitle voice' if (x['sub'] and x['voice']) else ('line with sound' if x['peak'] > 0.02 else 'quiet line')
        if x['peak'] > 0.02:
            check('%s sounds again after rewind (%s)' % (kind, x['id']), pk > 0.01, 'first %.4f again %.4f %s' % (x['peak'], pk, b['note']))
        elif x['sub'] and x['voice']:
            # 자막 음성이 대사보다 먼저 흘러 끝난 자리(음성 → 자막 → 화면 전환 → 대사): 처음 지날 때 그 대사에서는 조용했다.
            # 그 대사로 되감으면 자막과 함께 그 음성이 처음부터 다시 나온다(자막의 음성을 다시 듣게 하는 것이 목적).
            check('%s plays again at its line, where it had already ended in the first pass (%s)' % (kind, x['id']), pk > 0.01, 'first pass at the line %.4f; after rewind %.4f %s' % (x['peak'], pk, b['note']))
        elif x['peak'] < 0.002:
            check('%s stays quiet after rewind (%s)' % (kind, x['id']), pk < 0.004, 'first %.4f; after rewind: first 0.4 s %.4f, then 1.3 s %.4f' % (x['peak'], early, pk))
    ok = all(c['ok'] for c in checks)
finally:
    g.w16(0x466450, 1)             # 배경음 설정을 되돌린다(엔진이 끌 때 설정을 저장한다)
    try:
        r.summary(ok, dict(checks=checks, checks_passed='%d/%d' % (sum(c['ok'] for c in checks), len(checks))))
    finally:
        audio.release(found)
        q = r.finish(ok)
        print('RESULT checks %d/%d, normal quit %s' % (sum(c['ok'] for c in checks), len(checks), q))

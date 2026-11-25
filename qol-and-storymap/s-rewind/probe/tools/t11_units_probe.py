# -*- coding: utf-8 -*-
"""대사 없이 흐르는 소리 자막(음성 → 노란 자막 → 음성이 끝나면 숨김, 또는 쪽을 넘기며 흐름)이 되감기로 다시 나오는지.
처음 지날 때 그 자막이 흐르는 동안의 화면과 소리(크기의 흐름)를 적어 두고, 되감은 뒤의 것과 견준다.
 A) 다음 대사에서 되감기 한 번 → 바로 앞의 소리 자막이 처음부터 다시 흐르는가(화면, 음성 길이, 엔진이 들고 있는 저장 자리)
 B) 그 자막이 0.8초 넘게 흐른 뒤에 되감기 → 그 자막이 처음부터 (쪽이 바뀌는 틈에 눌러도)
 C) 그 자막이 막 시작했을 때 되감기 → 그 앞 자리로
 F) 앞 대사를 넘긴 직후(자막이 뜨기 전)에 되감기 → 방금 떠난 그 대사로
 D) 앞 자리에서 넘기면(Enter) 그 자막이 다시 흐르는가
 E) 그 뒤 대사에 자막이 남아 있으면: 다음 대사에서 되감아 그 대사로 돌아오는가
 H) 자막이 먼저 뜨고 1초 뒤에 글이 나오는 대사: 그 1초 사이에 되감기 → 방금 떠난 대사로
배경음은 설정 깃발로 꺼 둔다(소리 크기에 음성만 남게). 끝날 때 되돌린다.

사용: python -I t11_units.py <이름> [대사 수=40] [시험할 묶음 수=3] [시험할 자막 자리 id,…] [둘째 쪽 찍을 때 id=초,…] [1초 먼저 뜨는 대사 id,…]"""
import os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv, audio, rw

NAME = sys.argv[1] if len(sys.argv) > 1 else 't11'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 40
GROUPS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
IDS = set(sys.argv[4].split(',')) if len(sys.argv) > 4 and sys.argv[4] else None      # 주면 이 자리가 든 묶음만 시험한다
PAGE2 = dict((k, float(v)) for k, v in (x.split('=') for x in sys.argv[5].split(','))) if len(sys.argv) > 5 and sys.argv[5] else {}   # 둘째 쪽을 찍을 때(뜬 뒤 몇 초)
PREROLL = set(sys.argv[6].split(',')) if len(sys.argv) > 6 and sys.argv[6] else set()
SHOT_AT = float(os.environ.get('T11_SHOT_AT', '0.30'))      # 소리 자막이 뜬 뒤 이만큼 지나 화면을 찍는다
SETTLE = float(os.environ.get('T11_SETTLE', '0.35'))
r = drv.Run(NAME, settle=SETTLE); g = r.g
found = []
checks = []
first_unit = {}         # id -> dict(img, env, …)
first_stop = {}         # id -> img
UP = re.compile(r'rewind: sound subtitle up again ([\d.]+) ms')
PRESSED = re.compile(r'rewind: pressed (.*)')
PRI = 0x4690a8          # 엔진이 들고 있는 「지금 상태」 한 벌(저장하면 파일에 들어간다)


def peak_now():
    global found
    if not found: found = audio.sessions(g.pid)
    try:
        p, m = audio.peak(found)
    except OSError:
        audio.release(found); found = []; return 0.0
    if m is False: g.mute()
    return p


def listen(sec):
    best = 0.0; t0 = time.time()
    while time.time() - t0 < sec:
        g.poke(); best = max(best, peak_now()); time.sleep(0.012)
    return best


def check(name, cond, extra=''):
    checks.append(dict(name=name, ok=bool(cond), extra=str(extra)))
    r.L(('PASS ' if cond else 'FAIL ') + name, extra)


def pri_pos():
    d = g.u16(PRI + 0x50) & 15
    return '%04d:%d' % (g.u16(PRI + 0x12 + 2 * d), g.u32(PRI + 0x28 + 4 * d))


def loud_span(env, th=0.03):
    """소리 크기 흐름에서 처음·마지막으로 th 를 넘은 때(뜬 뒤 몇 초)."""
    on = [t for t, p in env if p > th]
    return (on[0], on[-1]) if on else (None, None)


def buckets(env, dur, step=0.25, tail=0.5):
    """0.25초 칸마다 가장 큰 소리 크기. 끝의 0.5초는 뺀다 — 그 자막의 창 끝에는 다음 음성의 첫머리가 걸린다(다음 음성 명령이 다음 자막이 「뜨기」 0.3초 전에 실행된다)."""
    out = []; a = 0.0
    while a + step <= max(0.0, dur - tail):
        v = [p for t, p in env if a <= t < a + step]
        out.append(max(v) if v else 0.0); a += step
    return out


def same_sound(f, u):
    """두 흐름이 같은 음성인가: 칸마다 큰소리/조용함이 같은 칸의 비율과, 큰소리 칸 수."""
    a = buckets(f['env'], min(f.get('dur', 0), u.get('dur', 0))); b = buckets(u['env'], min(f.get('dur', 0), u.get('dur', 0)))
    n = min(len(a), len(b))
    if n == 0: return False, 'no buckets'
    agree = sum(1 for i in range(n) if (a[i] > 0.10) == (b[i] > 0.10))
    la = sum(1 for x in a[:n] if x > 0.10); lb = sum(1 for x in b[:n] if x > 0.10)
    txt = 'first %s | again %s' % (' '.join('%2d' % min(99, round(x * 100)) for x in a[:n]), ' '.join('%2d' % min(99, round(x * 100)) for x in b[:n]))
    return (agree >= n - 1 and abs(la - lb) <= 1 and lb >= 1), txt


def watch(n0, timeout=120, on_unit=None):
    """다음에 클릭을 기다리며 멈출 때까지 본다. 그 사이에 흐른 소리 자막마다: 뜬 지 SHOT_AT 초 뒤의 화면, (있으면) 둘째 쪽 화면, 소리 크기의 흐름.
    on_unit(u) 가 True 를 돌려주면 거기서 그만 본다(그 자막이 흐르는 중에 되감기를 시험하려고)."""
    seen = n0; units = []; t0 = time.time(); cur = None
    while time.time() - t0 < timeout:
        g.poke(); r.pump()
        now = time.time()
        while seen < len(r.stops):
            st = r.stops[seen]; seen += 1
            if cur: cur['dur'] = now - cur['t']; cur = None
            if not st['unit']: continue
            cur = dict(id=st['id'], t=now, sub=st['sub'], env=[], img=None, pri=pri_pos())
            units.append(cur)
            if on_unit and on_unit(cur): return units, None
        if cur:
            dt = now - cur['t']
            cur['env'].append((dt, peak_now()))
            if cur['img'] is None and dt >= SHOT_AT: cur['img'] = g.shot(); cur['img_at'] = dt
            if cur['id'] in PAGE2 and 'img2' not in cur and dt >= PAGE2[cur['id']]: cur['img2'] = g.shot()
        z = g.state()
        if (z['click'] or z['choice']) and len(r.stops) > n0 and not r.stops[-1]['unit'] and seen == len(r.stops):
            time.sleep(0.05); r.pump()
            if seen == len(r.stops):
                for u in units:
                    u['peak'] = max([p for _, p in u['env']] or [0.0]); u['span'] = loud_span(u['env'])
                return units, r.stops[-1]
        if z['typing'] and not z['click']: g.w32(0x4663d4, 1)
        if not g.alive(): raise RuntimeError('game exited')
        time.sleep(0.008)
    raise RuntimeError('no stop within %d s (state %s)' % (timeout, g.state()))


def rewind(k=1):
    """되감기 요청 → 되돌린 기록 줄이 나올 때까지. 돌려주는 것에 「어디서 눌렀나」도 붙인다."""
    nb = len(r.backs); nr = len(r.refused); ne = len(r.events)
    g.rewind(k); t0 = time.time()
    while len(r.backs) == nb and time.time() - t0 < 4:
        g.poke(); r.pump(); time.sleep(0.004)
        if len(r.refused) > nr: return None
    if len(r.backs) == nb: return None
    b = r.backs[-1]
    w = [m.group(1) for l in r.events[ne:] for m in [PRESSED.search(l)] if m]
    b['where'] = w[-1] if w else ''
    return b


def desc(b):
    return b and ('went to %s (%s), key-to-start %.1f ms, screen %.1f ms%s' % (b['id'], b['where'], b['wake'], b['visual'], (' ' + b['note']) if b['note'] else ''))


def cmp_img(tag, a, b):
    d = rw.diff(a, b, r.mask(b), 8)
    r.L('  compare', tag, 'diff pixels', d['n'], d.get('box') or '')
    return d


def cmp_units(tag, units, save=False):
    """다시 흐른 소리 자막들을 처음 지날 때와 견준다(화면, 음성 길이)."""
    for u in units:
        f = first_unit.get(u['id'])
        if not f or f.get('img') is None or u.get('img') is None:
            check('%s: %s has a first-pass picture and a new one' % (tag, u['id']), False, 'first %s again %s' % (bool(f), u.get('img') is not None)); continue
        d = cmp_img('%s unit %s' % (tag, u['id']), f['img'], u['img'])
        check('%s: sound subtitle %s is on screen again as in the first pass' % (tag, u['id']), d['n'] == 0, 'diff pixels %d %s' % (d['n'], d.get('box') or ''))
        same, txt = same_sound(f, u)
        check('%s: its voice plays again with the same loud and quiet parts, quarter second by quarter second (%s)' % (tag, u['id']), u['peak'] > 0.05 and same and abs(f.get('dur', 0) - u.get('dur', 0)) < 0.35,
              'whole %.2f s / %.2f s; x100: %s' % (f.get('dur', 0), u.get('dur', 0), txt))
        if 'img2' in f:
            if 'img2' in u:
                d2 = cmp_img('%s unit %s second page' % (tag, u['id']), f['img2'], u['img2'])
                check('%s: its second page is on screen again as in the first pass (%s)' % (tag, u['id']), d2['n'] == 0, 'diff pixels %d %s' % (d2['n'], d2.get('box') or ''))
                dp = cmp_img('%s unit %s page 1 against page 2 (must differ)' % (tag, u['id']), u['img'], u['img2'])
                check('%s: the two pages are different pictures (%s)' % (tag, u['id']), dp['n'] > 0, 'diff pixels %d' % dp['n'])
                if save:
                    f['img2'].save(os.path.join(r.out, 'page2_%s_first.png' % u['id'].replace(':', '_')))
                    u['img2'].save(os.path.join(r.out, 'page2_%s_%s.png' % (u['id'].replace(':', '_'), tag)))
            else:
                check('%s: second page of %s was captured' % (tag, u['id']), False)
        if d['n'] or save:
            k = len([n for n in os.listdir(r.out) if n.startswith('unit_')]) // 2
            if k < 8:
                f['img'].save(os.path.join(r.out, 'unit_%02d_%s_first.png' % (k, u['id'].replace(':', '_'))))
                u['img'].save(os.path.join(r.out, 'unit_%02d_%s_%s.png' % (k, u['id'].replace(':', '_'), tag)))


def keep_units(units):
    for u in units:
        if u.get('img') is not None: first_unit.setdefault(u['id'], u)


ok = False
try:
    g.skip_events()
    assert g.wait_title()
    time.sleep(1.0)
    g.w16(0x466450, 0)             # 배경음 끔 → 소리 크기에는 음성(과 효과음)만
    time.sleep(0.3)
    g.click(607, 286)              # 처음부터
    units, st = watch(len(r.stops), 150)
    keep_units(units)
    r.L('before the first line: %d sound subtitles %s; first stop %s; client %s' % (len(units), [u['id'] for u in units], st and st['id'], g.client()))
    time.sleep(r.settle); first_stop[st['id']] = g.shot()
    order = [st['id']]             # 클릭을 기다린 자리들
    done = 0
    for i in range(N):
        prev = order[-1]
        n0 = len(r.stops); r.go(g.state())
        units, st = watch(n0)
        keep_units(units)
        time.sleep(r.settle); first_stop.setdefault(st['id'], g.shot()); order.append(st['id'])
        M = st['id']
        # H) 자막이 먼저 뜨고 1초 뒤에 글이 나오는 대사
        if M in PREROLL and not units:
            nH0 = len(r.stops)
            b = rewind(1)
            check('H: setup, back to the line before (%s)' % prev, b and b['id'] == prev, desc(b))
            s0, _ = r.at_stop(40, nH0)
            nH = len(r.stops); r.go(g.state()); time.sleep(0.55)          # 넘긴 뒤 0.55초: 자막·음성은 나왔고 글은 아직
            mid_state = g.state()
            b = rewind(1)
            check('H: rewind during the one second before the text of %s comes up returns to the line just left (%s)' % (M, prev), b and b['id'] == prev and 'between stops' in b['where'],
                  '%s; pressed when click-wait %d typing %d' % (desc(b), mid_state['click'], mid_state['typing']))
            sH, stH = r.at_stop(40, nH)
            d = cmp_img('H line ' + prev, first_stop[prev], r.shot())
            check('H: that line looks as in the first pass', d['n'] == 0, 'diff pixels %d %s' % (d['n'], d.get('box') or ''))
            nH = len(r.stops); r.go(g.state())
            _, stH2 = watch(nH)
            time.sleep(r.settle); d = cmp_img('H line ' + M, first_stop[M], g.shot())
            check('H: going on, the line with the subtitle comes up as in the first pass (%s)' % M, stH2 and stH2['id'] == M and d['n'] == 0, 'at %s, diff pixels %d %s' % (stH2 and stH2['id'], d['n'], d.get('box') or ''))
        if not units: continue
        r.L('--- %d sound subtitle(s) flowed between %s and %s: %s (peaks %s, heard until %s s, whole %s s)' % (
            len(units), prev, M, [u['id'] for u in units], ['%.3f' % u['peak'] for u in units], ['%.2f' % (u['span'][1] or 0) for u in units], ['%.2f' % u.get('dur', 0) for u in units]))
        if IDS is not None:
            if not (IDS & set(u['id'] for u in units)): continue
        elif done >= GROUPS: continue
        done += 1
        last = units[-1]['id']
        paged = last in PAGE2

        def mid(u):
            return u['id'] == last

        # A) 다음 대사에서 되감기 한 번
        n0 = len(r.stops)
        b = rewind(1)
        check('A: one rewind at the next line (%s) goes to the sound subtitle just before it (%s)' % (M, last), b and b['id'] == last and 'at a line' in b['where'], desc(b))
        again, st2 = watch(n0)
        cmp_units('A', again, save=True)
        check('A: while it plays again, the state the engine would save is the line before it, as in the first pass', again and again[-1]['pri'] == units[-1]['pri'],
              'first pass %s, again %s' % (units[-1]['pri'], again and again[-1]['pri']))
        check('A: then it flows on to the same line (%s)' % M, st2 and st2['id'] == M, st2 and st2['id'])
        time.sleep(r.settle); d = cmp_img('A line ' + M, first_stop[M], g.shot())
        check('A: the line after it looks as in the first pass (%s)' % M, d['n'] == 0, 'diff pixels %d %s' % (d['n'], d.get('box') or ''))
        # B) 흐르는 중(0.8초 넘게)에 되감기 → 그 자막이 처음부터
        n0 = len(r.stops)
        b = rewind(1)
        if not b: check('B: setup rewind', False); continue
        watch(n0, 20, on_unit=mid)                    # 그 자막이 다시 뜬 순간
        time.sleep(1.2)
        n1 = len(r.stops)
        b2 = rewind(1)
        check('B: rewind after it has played for 1.2 s restarts that sound subtitle (%s)' % last, b2 and b2['id'] == last and 'restart' in b2['where'], desc(b2))
        if paged:
            # 쪽이 바뀌는 틈(첫 쪽 기다림이 끝난 직후, 둘째 쪽 글을 넣는 중)에 눌러도
            watch(n1, 20, on_unit=mid)
            time.sleep(4.2)
            n1 = len(r.stops)
            b2 = rewind(1)
            check('B2: rewind while the page is changing restarts that sound subtitle from its first page (%s)' % last, b2 and b2['id'] == last and 'restart' in b2['where'], desc(b2))
            watch(n1, 20, on_unit=mid)
            time.sleep(PAGE2[last])
            n1 = len(r.stops)
            b2 = rewind(1)
            check('B3: rewind on its second page restarts it from its first page (%s)' % last, b2 and b2['id'] == last and 'restart' in b2['where'], desc(b2))
        # C) 막 시작했을 때 되감기 → 그 앞 자리로
        watch(n1, 20, on_unit=mid)
        time.sleep(0.15)
        n2 = len(r.stops)
        b3 = rewind(1)
        want = units[-2]['id'] if len(units) > 1 else prev
        check('C: rewind right after it started goes to the stop before it (%s)' % want, b3 and b3['id'] == want and 'just after' in b3['where'], desc(b3))
        if b3 and b3['id'] == prev:
            s3, st3 = r.at_stop(40, n2)
            d = cmp_img('C line ' + prev, first_stop[prev], r.shot())
            check('C: the earlier line looks as in the first pass (%s)' % prev, d['n'] == 0, 'diff pixels %d %s' % (d['n'], d.get('box') or ''))
            # F) 그 대사를 넘긴 직후(자막이 뜨기 전)에 되감기 → 방금 떠난 그 대사로
            nF = len(r.stops); r.go(g.state()); time.sleep(0.12)
            bF = rewind(1)
            check('F: rewind right after leaving %s (before the subtitle is up) returns to it' % prev, bF and bF['id'] == prev and 'between stops' in bF['where'], desc(bF))
            sF, stF = r.at_stop(40, nF)
            d = cmp_img('F line ' + prev, first_stop[prev], r.shot())
            check('F: that line looks as in the first pass (%s)' % prev, d['n'] == 0, 'diff pixels %d %s' % (d['n'], d.get('box') or ''))
            # D) 그 대사에서 넘기면 다시 흐르는가
            n3 = len(r.stops); r.go(g.state())
            again, st4 = watch(n3)
            want_units = [u['id'] for u in units]
        else:
            again, st4 = watch(n2)
            want_units = [u['id'] for u in units[-2:]]
        check('D: going on from there, the sound subtitles flow again in order', [u['id'] for u in again] == want_units, '%s (expected %s)' % ([u['id'] for u in again], want_units))
        cmp_units('D', again)
        check('D: and it arrives at the same line (%s)' % M, st4 and st4['id'] == M, st4 and st4['id'])
        time.sleep(r.settle); d = cmp_img('D line ' + M, first_stop[M], g.shot())
        check('D: that line looks as in the first pass', d['n'] == 0, 'diff pixels %d %s' % (d['n'], d.get('box') or ''))
        # E) 이 대사에 자막이 남아 있으면: 다음 대사에서 되감아 이 대사로
        if st['sub']:
            nE = len(r.stops); r.go(g.state())
            unitsE, stE = watch(nE)
            keep_units(unitsE)
            time.sleep(r.settle); first_stop.setdefault(stE['id'], g.shot())
            if not unitsE:
                nE2 = len(r.stops)
                bE = rewind(1)
                check('E: from the following line (%s), one rewind returns to the line that carries a subtitle (%s)' % (stE['id'], M), bE and bE['id'] == M, desc(bE))
                sE, stE2 = r.at_stop(40, nE2)
                d = cmp_img('E line ' + M, first_stop[M], r.shot())
                check('E: that line shows its subtitle and text as in the first pass (%s)' % M, d['n'] == 0, 'diff pixels %d %s' % (d['n'], d.get('box') or ''))
                if paged:
                    check('E: the voice is not started over there (it belongs to the sound subtitle before it)', bE and 'subtitle-voice-replayed' not in bE['note'], bE and bE['note'])
    r.pump()
    ups = [float(m.group(1)) for l in r.events for m in [UP.search(l)] if m]
    r.L('sound subtitle up again after the screen came back (ms):', ['%.0f' % x for x in ups])
    bad_verify = [v for v in r.verifies if not v['same']]
    check('engine state bytes are the same whenever a stop is passed again', not bad_verify, '%d same, %d different %s' % (sum(1 for v in r.verifies if v['same']), len(bad_verify), bad_verify[:3]))
    check('no rewind request was refused or dropped', not r.refused and not [l for l in r.events if 'request dropped' in l], r.refused)
    ok = all(c['ok'] for c in checks)
finally:
    g.w16(0x466450, 1)             # 배경음 설정을 되돌린다(엔진이 끌 때 설정을 저장한다)
    try:
        r.summary(ok, dict(checks=checks, checks_passed='%d/%d' % (sum(c['ok'] for c in checks), len(checks)),
                           units_first=[dict(id=k, peak=v.get('peak'), span=v.get('span'), dur=v.get('dur')) for k, v in first_unit.items()]))
    finally:
        audio.release(found)
        q = r.finish(ok)
        print('RESULT checks %d/%d, normal quit %s' % (sum(c['ok'] for c in checks), len(checks), q))

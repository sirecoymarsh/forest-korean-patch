# -*- coding: utf-8 -*-
"""대사 없이 흐르는 소리 자막(음성 → 노란 자막 → 음성이 끝나면 숨김, 또는 쪽을 넘기며 흐름)으로 되감기.
처음 지날 때 그 자막이 흐르는 동안의 화면과 소리(크기의 흐름)를 적어 두고, 되감은 뒤의 것과 견준다.
되감아서 다시 보는 구간의 소리 자막은 음성이 끝나도 남아 있고 클릭·Enter 로 넘긴다(붙잡아 두기).
 A) 다음 대사에서 되감기 한 번 → 바로 앞의 소리 자막이 처음부터 다시 흐르고(화면·음성), 음성이 끝나면 붙잡힌다
    (자막이 그대로 남음, 엔진의 클릭 대기, 저장 자리는 그 앞 대사). Enter → 같은 대사로.
 U) 다시 흐르는 음성 중에 Enter → 붙잡지 않고 넘어간다(원작의 클릭과 같다)
 B) 흐르는 중(1.2초 뒤)에 되감기 → 그 자막을 처음부터
 C) 막 시작했을 때(0.15초) 되감기 → 그 앞 자리로
 F) 앞 대사를 넘긴 직후(자막이 뜨기 전)에 되감기 → 방금 떠난 그 대사로
 D) 앞 대사에서 넘기면(Enter) 그 자막이 다시 흐르고 붙잡힌다(다시 보는 구간) → Enter → 같은 대사
 G) 붙잡힌 자막에서 되감기 → 그 앞 자리로
 E) 그 뒤 대사에 자막이 남아 있으면: 다음 대사에서 되감아 그 대사로 돌아오는가
 H) 자막이 먼저 뜨고 1초 뒤에 글이 나오는 대사: 그 1초 사이에 되감기 → 방금 떠난 대사로
 Z) 처음 보는 곳의 소리 자막은 원작대로 저절로 흐른다(붙잡지 않는다)
배경음은 설정 깃발로 꺼 둔다(소리 크기에 음성만 남게). 끝날 때 되돌린다.

사용: python -I t11_units.py <이름> [대사 수=40] [시험할 묶음 수=3] [시험할 자막 자리 id,…] [쪽 넘기는 자막 id,…] [1초 먼저 뜨는 대사 id,…]"""
import os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv, rw

NAME = sys.argv[1] if len(sys.argv) > 1 else 't11'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 40
GROUPS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
IDS = set(sys.argv[4].split(',')) if len(sys.argv) > 4 and sys.argv[4] else None      # 주면 이 자리가 든 묶음만 시험한다
PAGED = set(sys.argv[5].split(',')) if len(sys.argv) > 5 and sys.argv[5] else set()   # 쪽을 넘기는 자막(첫 쪽 4초쯤 → 둘째 쪽 → 대사)
PREROLL = set(sys.argv[6].split(',')) if len(sys.argv) > 6 and sys.argv[6] else set()
SHOT_AT = float(os.environ.get('T11_SHOT_AT', '0.30'))      # 소리 자막이 뜬 뒤 이만큼 지나 화면을 찍는다
PAGE2_AT = float(os.environ.get('T11_PAGE2_AT', '4.75'))    # 처음 지날 때 둘째 쪽을 찍는 때(뜬 뒤 몇 초)
SETTLE = float(os.environ.get('T11_SETTLE', '0.35'))
TOL = int(os.environ.get('T11_TOL', '0'))                   # 그림이 같다고 볼 화소 수. 큰 창(4K 글자·그림)에서는 가장자리 몇 화소가 달라진다(조사.md 5-2) → 500 쯤
r = drv.Run(NAME, settle=SETTLE); g = r.g
r.paged = frozenset(PAGED); r.shot_at = SHOT_AT
r.notice_wait = 3.8 if drv.ini_on('present') else 0.0       # 화면 모듈이 켜져 있으면 처음 붙잡을 때의 알림(3.5초)이 그림에 나온다 → 사라진 뒤에 붙잡힌 화면을 찍는다
watch, rewind, listen, desc = r.watch, r.press, r.listen, r.desc
checks = []
first_unit = {}         # id -> dict(img, env, …)
first_stop = {}         # id -> img
UP = re.compile(r'rewind: sound subtitle up again ([\d.]+) ms')


def check(name, cond, extra=''):
    checks.append(dict(name=name, ok=bool(cond), extra=str(extra)))
    r.L(('PASS ' if cond else 'FAIL ') + name, extra)


def buckets(env, dur, step=0.25, tail=0.5):
    """0.25초 칸마다 가장 큰 소리 크기. 끝의 0.5초는 뺀다 — 그 자막의 창 끝에는 다음 음성의 첫머리가 걸린다."""
    out = []; a = 0.0
    while a + step <= max(0.0, dur - tail):
        v = [p for t, p in env if a <= t < a + step]
        out.append(max(v) if v else 0.0); a += step
    return out


def same_sound(f, u):
    """두 흐름이 같은 음성인가: 칸마다 큰소리/조용함이 같은가(둘 가운데 짧은 쪽 길이까지)."""
    d = min(f.get('dur', 0), u.get('dur', 0))
    a = buckets(f['env'], d); b = buckets(u['env'], d)
    n = min(len(a), len(b))
    if n == 0: return False, 'no buckets (%.2f s)' % d
    agree = sum(1 for i in range(n) if (a[i] > 0.10) == (b[i] > 0.10))
    la = sum(1 for x in a[:n] if x > 0.10); lb = sum(1 for x in b[:n] if x > 0.10)
    txt = 'first %s | again %s' % (' '.join('%2d' % min(99, round(x * 100)) for x in a[:n]), ' '.join('%2d' % min(99, round(x * 100)) for x in b[:n]))
    return (agree >= n - 1 and abs(la - lb) <= 1 and lb >= 1), txt


def cmp_img(tag, a, b):
    d = rw.diff(a, b, r.mask(b), 8)
    r.L('  compare', tag, 'diff pixels', d['n'], d.get('box') or '')
    return d


def cmp_units(tag, units, save=False, want_held=None):
    """다시 흐른 소리 자막들을 처음 지날 때와 견준다(화면, 음성). want_held: 붙잡혔어야 하는가."""
    for u in units:
        f = first_unit.get(u['id'])
        if not f or f.get('img') is None or u.get('img') is None:
            check('%s: %s has a first-pass picture and a new one' % (tag, u['id']), False, 'first %s again %s' % (bool(f), u.get('img') is not None)); continue
        d = cmp_img('%s unit %s' % (tag, u['id']), f['img'], u['img'])
        check('%s: sound subtitle %s is on screen again as in the first pass' % (tag, u['id']), d['n'] <= TOL, 'diff pixels %d %s' % (d['n'], d.get('box') or ''))
        if u['id'] in PAGED:
            check('%s: its voice plays again (%s)' % (tag, u['id']), u['peak'] > 0.05 or (u.get('peak_hold') or 0) > 0.05 or listen(0.4) > 0.05, 'peak %.3f' % u['peak'])
        else:
            same, txt = same_sound(f, u)
            check('%s: its voice plays again with the same loud and quiet parts, quarter second by quarter second (%s)' % (tag, u['id']), u['peak'] > 0.05 and same,
                  'whole %.2f s / %.2f s%s; x100: %s' % (f.get('dur', 0), u.get('dur', 0), ' (until held)' if u['held'] else '', txt))
        if want_held is not None:
            check('%s: %s (%s)' % (tag, 'it is held when its voice ends' if want_held else 'it flows on by itself', u['id']), u['held'] == want_held,
                  'held %s%s' % (u['held'], (' %.2f s after it came up' % u['hold_at']) if u['held'] else ''))
        if u['held']:
            dh = cmp_img('%s unit %s while held' % (tag, u['id']), f['img'], u['img_hold'])
            z = u['state_hold']
            check('%s: while held, the subtitle is still on screen and the engine waits for a click (%s)' % (tag, u['id']), dh['n'] <= TOL and z['click'] == 1,
                  'diff pixels %d %s; click-wait %d' % (dh['n'], dh.get('box') or '', z['click']))
            check('%s: while held, the state the engine would save is the line before it, as in the first pass (%s)' % (tag, u['id']), u['pri_hold'] == f['pri'], 'first pass %s, held %s' % (f['pri'], u['pri_hold']))
            if u['peak_hold'] is not None:
                check('%s: while held, the voice has ended (%s)' % (tag, u['id']), u['peak_hold'] < 0.02, 'peak %.4f' % u['peak_hold'])
        if save:
            k = len([n for n in os.listdir(r.out) if n.startswith('unit_')]) // 2
            if k < 8:
                f['img'].save(os.path.join(r.out, 'unit_%02d_%s_first.png' % (k, u['id'].replace(':', '_'))))
                (u.get('img_hold') or u['img']).save(os.path.join(r.out, 'unit_%02d_%s_%s.png' % (k, u['id'].replace(':', '_'), tag)))


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
    units, st = watch(len(r.stops), 150, page2_at=PAGE2_AT)
    keep_units(units)
    r.L('before the first line: %d sound subtitles %s; first stop %s; client %s' % (len(units), [u['id'] for u in units], st and st['id'], g.client()))
    time.sleep(r.settle); first_stop[st['id']] = g.shot()
    order = [st['id']]             # 클릭을 기다린 자리들
    done = 0; flowed_first = 0; held_first = 0
    for i in range(N):
        prev = order[-1]
        n0 = len(r.stops); r.go(g.state())
        units, st = watch(n0, page2_at=PAGE2_AT)
        keep_units(units)
        flowed_first += len([u for u in units if not u['held']]); held_first += len([u for u in units if u['held']])
        time.sleep(r.settle); first_stop.setdefault(st['id'], g.shot()); order.append(st['id'])
        M = st['id']
        # H) 자막이 먼저 뜨고 1초 뒤에 글이 나오는 대사
        if M in PREROLL and not units:
            nH0 = len(r.stops)
            b = rewind(1)
            check('H: setup, back to the line before (%s)' % prev, b and b['id'] == prev, desc(b))
            r.at_stop(40, nH0)
            nH = len(r.stops); r.go(g.state()); time.sleep(0.55)          # 넘긴 뒤 0.55초: 자막·음성은 나왔고 글은 아직
            mid_state = g.state()
            b = rewind(1)
            check('H: rewind during the one second before the text of %s comes up returns to the line just left (%s)' % (M, prev), b and b['id'] == prev and 'between stops' in b['where'],
                  '%s; pressed when click-wait %d typing %d' % (desc(b), mid_state['click'], mid_state['typing']))
            r.at_stop(40, nH)
            d = cmp_img('H line ' + prev, first_stop[prev], r.shot())
            check('H: that line looks as in the first pass', d['n'] <= TOL, 'diff pixels %d %s' % (d['n'], d.get('box') or ''))
            nH = len(r.stops); r.go(g.state())
            _, stH2 = watch(nH)
            time.sleep(r.settle); d = cmp_img('H line ' + M, first_stop[M], g.shot())
            check('H: going on, the line with the subtitle comes up as in the first pass (%s)' % M, stH2 and stH2['id'] == M and d['n'] <= TOL, 'at %s, diff pixels %d %s' % (stH2 and stH2['id'], d['n'], d.get('box') or ''))
        if not units: continue
        r.L('--- %d sound subtitle(s) flowed between %s and %s: %s (peaks %s, whole %s s)' % (
            len(units), prev, M, [u['id'] for u in units], ['%.3f' % u['peak'] for u in units], ['%.2f' % u.get('dur', 0) for u in units]))
        if IDS is not None:
            if not (IDS & set(u['id'] for u in units)): continue
        elif done >= GROUPS: continue
        done += 1
        last = units[-1]['id']
        paged = last in PAGED
        before_last = units[-2]['id'] if len(units) > 1 else prev

        def mid(u):
            return u['id'] == last

        # A) 다음 대사에서 되감기 한 번 → 바로 앞 소리 자막, 음성이 끝나면 붙잡힌다
        n0 = len(r.stops)
        b = rewind(1)
        check('A: one rewind at the next line (%s) goes to the sound subtitle just before it (%s)' % (M, last), b and b['id'] == last and 'at a line' in b['where'], desc(b))
        again, _ = watch(n0, 60, on_hold='stop')
        cmp_units('A', again, save=True, want_held=True)
        time.sleep(1.5); r.pump()
        z = g.state()
        check('A: it stays held (no new stop after 1.5 s more)', again and again[-1]['held'] and r.stops[-1]['id'] == last and z['click'] == 1, 'last stop %s click-wait %d' % (r.stops[-1]['id'], z['click']))
        n1 = len(r.stops); g.key(0x0D)
        tE = time.time()
        if paged:
            time.sleep(0.9); img2 = g.shot()
            f = first_unit[last]
            if 'img2' in f:
                d2 = cmp_img('A unit %s second page after Enter' % last, f['img2'], img2)
                check('A: Enter turns to its second page, as in the first pass (%s)' % last, d2['n'] <= TOL, 'diff pixels %d %s' % (d2['n'], d2.get('box') or ''))
                dp = cmp_img('A unit %s page 1 against page 2 (must differ)' % last, again[-1]['img'], img2)
                check('A: the two pages are different pictures (%s)' % last, dp['n'] > 0, 'diff pixels %d' % dp['n'])
            else:
                check('A: second page of %s was captured in the first pass' % last, False)
        more, st2 = watch(n1, 60)
        check('A: Enter goes on to the same line (%s)' % M, st2 and st2['id'] == M and not more, 'at %s after %.2f s, more subtitles %s' % (st2 and st2['id'], time.time() - tE, [u['id'] for u in more]))
        time.sleep(r.settle); d = cmp_img('A line ' + M, first_stop[M], g.shot())
        check('A: the line after it looks as in the first pass (%s)' % M, d['n'] <= TOL, 'diff pixels %d %s' % (d['n'], d.get('box') or ''))

        # U) 다시 흐르는 음성 중에 Enter → 붙잡지 않고 넘어간다 (쪽 넘기는 자막은 뜨자마자 붙잡히므로 뺀다)
        if not paged:
            n0 = len(r.stops)
            b = rewind(1)
            watch(n0, 20, on_unit=mid)
            time.sleep(0.5); ne = len(r.events); g.key(0x0D)
            more, st2 = watch(len(r.stops), 30, on_hold='stop')
            r.pump()
            held = any('holding the sound subtitle' in l for l in r.events[ne:])
            check('U: Enter while its voice plays again goes on without holding (%s)' % last, b and st2 and st2['id'] == M and not held, 'at %s, held %s' % (st2 and st2['id'], held))

        # B) 흐르는 중(1.2초 뒤)에 되감기 → 그 자막을 처음부터 (쪽 넘기는 자막은 뜨자마자 붙잡히므로 C·G 로 본다)
        n0 = len(r.stops)
        b = rewind(1)
        if not b: check('B: setup rewind', False); continue
        if not paged:
            watch(n0, 20, on_unit=mid)
            time.sleep(1.2)
            n0 = len(r.stops)
            b2 = rewind(1)
            check('B: rewind after it has played for 1.2 s restarts that sound subtitle (%s)' % last, b2 and b2['id'] == last and 'restart' in b2['where'], desc(b2))
        # C) 막 시작했을 때(0.15초) 되감기 → 그 앞 자리로
        watch(n0, 20, on_unit=mid)
        time.sleep(0.15)
        n2 = len(r.stops)
        b3 = rewind(1)
        if paged:
            check('C: rewind right after it came up (it is already held) goes to the stop before it (%s)' % before_last, b3 and b3['id'] == before_last, desc(b3))
        else:
            check('C: rewind right after it started goes to the stop before it (%s)' % before_last, b3 and b3['id'] == before_last and 'just after' in b3['where'], desc(b3))
        if b3 and b3['id'] == prev:
            r.at_stop(40, n2)
            d = cmp_img('C line ' + prev, first_stop[prev], r.shot())
            check('C: the earlier line looks as in the first pass (%s)' % prev, d['n'] <= TOL, 'diff pixels %d %s' % (d['n'], d.get('box') or ''))
            # F) 그 대사를 넘긴 직후(자막이 뜨기 전)에 되감기 → 방금 떠난 그 대사로
            nF = len(r.stops); r.go(g.state()); time.sleep(0.12)
            bF = rewind(1)
            check('F: rewind right after leaving %s (before the subtitle is up) returns to it' % prev, bF and bF['id'] == prev and 'between stops' in bF['where'], desc(bF))
            r.at_stop(40, nF)
            d = cmp_img('F line ' + prev, first_stop[prev], r.shot())
            check('F: that line looks as in the first pass (%s)' % prev, d['n'] <= TOL, 'diff pixels %d %s' % (d['n'], d.get('box') or ''))
            # D) 그 대사에서 넘기면 다시 흐르고 붙잡힌다(다시 보는 구간) → Enter 로 하나씩 넘겨 같은 대사까지
            n3 = len(r.stops); r.go(g.state())
            again, st4 = watch(n3, 90)
            want_units = [u['id'] for u in units]
        else:
            again, st4 = watch(n2, 90)
            want_units = [u['id'] for u in units[-2:]]
        check('D: going on from there, the sound subtitles come again in order', [u['id'] for u in again] == want_units, '%s (expected %s)' % ([u['id'] for u in again], want_units))
        cmp_units('D', again, want_held=True)
        check('D: and after Enter on each it arrives at the same line (%s)' % M, st4 and st4['id'] == M, st4 and st4['id'])
        time.sleep(r.settle); d = cmp_img('D line ' + M, first_stop[M], g.shot())
        check('D: that line looks as in the first pass', d['n'] <= TOL, 'diff pixels %d %s' % (d['n'], d.get('box') or ''))

        # G) 붙잡힌 자막에서 되감기 → 그 앞 자리로
        n0 = len(r.stops)
        b = rewind(1)
        got, _ = watch(n0, 60, on_hold='stop')
        if got and got[-1]['held']:
            n1 = len(r.stops)
            bG = rewind(1)
            check('G: rewind on the held sound subtitle goes to the stop before it (%s)' % before_last, bG and bG['id'] == before_last and 'at a line' in bG['where'], desc(bG))
            # 그 앞 자리가 대사면 거기서 멈춘다. 다시 M 까지 간다(붙잡히는 자막은 Enter 로)
            if bG and bG['id'] == prev:
                r.at_stop(60, n1)
                nG = len(r.stops); r.go(g.state())
                _, stG2 = watch(nG, 90)
            else:
                _, stG2 = watch(n1, 90)
            check('G: reading on from there arrives at the same line (%s)' % M, stG2 and stG2['id'] == M, stG2 and stG2['id'])
        else:
            check('G: the sound subtitle was held', False, got and got[-1].get('id'))

        # E) 이 대사에 자막이 남아 있으면: 다음 대사에서 되감아 이 대사로
        if st['sub']:
            nE = len(r.stops); r.go(g.state())
            unitsE, stE = watch(nE, page2_at=PAGE2_AT)
            keep_units(unitsE)
            flowed_first += len([u for u in unitsE if not u['held']]); held_first += len([u for u in unitsE if u['held']])
            time.sleep(r.settle); first_stop.setdefault(stE['id'], g.shot())
            if not unitsE:
                nE2 = len(r.stops)
                bE = rewind(1)
                check('E: from the following line (%s), one rewind returns to the line that carries a subtitle (%s)' % (stE['id'], M), bE and bE['id'] == M, desc(bE))
                r.at_stop(40, nE2)
                d = cmp_img('E line ' + M, first_stop[M], r.shot())
                check('E: that line shows its subtitle and text as in the first pass (%s)' % M, d['n'] <= TOL, 'diff pixels %d %s' % (d['n'], d.get('box') or ''))
                if paged:
                    check('E: the voice is not started over there (it belongs to the sound subtitle before it)', bE and 'subtitle-voice-replayed' not in bE['note'], bE and bE['note'])
    r.pump()
    ups = [float(m.group(1)) for l in r.events for m in [UP.search(l)] if m]
    r.L('sound subtitle up again after the screen came back (ms):', ['%.0f' % x for x in ups])
    check('Z: sound subtitles met for the first time flowed on by themselves (none was held)', held_first == 0 and flowed_first > 0, 'flowed %d, held %d' % (flowed_first, held_first))
    bad_verify = [v for v in r.verifies if not v['same']]
    check('engine state bytes are the same whenever a stop is passed again', not bad_verify, '%d same, %d different %s' % (sum(1 for v in r.verifies if v['same']), len(bad_verify), bad_verify[:3]))
    check('no rewind request was refused or dropped', not r.refused and not [l for l in r.events if 'request dropped' in l], r.refused)
    errs = [l for l in r.other if any(k in l.lower() for k in ('exception', 'audit fail', 'error', 'disabled after'))] + [l for l in r.events if 'ERROR' in l]
    check('no error lines', not errs, errs[-3:])
    ok = all(c['ok'] for c in checks)
finally:
    g.w16(0x466450, 1)             # 배경음 설정을 되돌린다(엔진이 끌 때 설정을 저장한다)
    try:
        r.summary(ok, dict(checks=checks, checks_passed='%d/%d' % (sum(c['ok'] for c in checks), len(checks)),
                           units_first=[dict(id=k, peak=v.get('peak'), dur=v.get('dur')) for k, v in first_unit.items()]))
    finally:
        r.release_audio()
        q = r.finish(ok)
        print('RESULT checks %d/%d, normal quit %s' % (sum(c['ok'] for c in checks), len(checks), q))

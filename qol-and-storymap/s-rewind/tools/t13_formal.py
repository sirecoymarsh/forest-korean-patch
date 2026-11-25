# -*- coding: utf-8 -*-
"""정식 되감기 모듈의 나머지 약속(소리 자막 걸음은 t11).
 K) 진짜 Backspace 키 한 번 = 한 걸음 뒤로
 R) 누르고 있기: 키 반복(약 30번/초)을 1.2초 보내면 초당 10걸음쯤으로 한 걸음씩 뒤로 간다
 N) 더 앞이 없을 때: 아무것도 안 하고 알림 한 줄
 M) 선택지를 넘어 되감았다가 다시 고르면: 걸음마다 엔진 상태와 이야기의 지도 회차 기록이 처음과 같고, 지도 그림도 같다
 A) 자동 진행 중에 Backspace: 자동이 꺼지고 한 걸음 뒤로(글 기다림 중, 음성 기다림 중)
 S) 붙잡힌 소리 자막에서 S(바로 저장): 저장 파일에는 그 앞 대사가 들어간다
 T) 붙잡힌 소리 자막에서 A(자동 진행): 붙잡힘이 풀리고 자동으로 넘어간다
 X) Tab 건너뛰기 중에 Backspace: 건너뛰기가 멈추고 방금 지난 자리로
 G) Home 조작 안내에 Backspace 줄(그림을 남긴다)
배경음은 설정 깃발로 꺼 둔다(음성 있는 대사를 소리 크기로 고르려고). 끝날 때 되돌린다.
알림·조작 안내는 화면 모듈(present=1)이 그린다 → 화면 모듈을 켠 채 창 메뉴로 1배 창을 만들어 본다(창 기억 파일은 끝나고 되돌린다).

사용: python -I t13_formal.py <이름> [처음 읽을 대사 수=16]"""
import glob, os, re, shutil, struct, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv, rw

NAME = sys.argv[1] if len(sys.argv) > 1 else 't13'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 16
WINMEM = os.path.join(rw.GAME, 'forest-qol-window.ini')
WINMEM_KEEP = WINMEM + '.t13keep'
if os.path.exists(WINMEM): shutil.copyfile(WINMEM, WINMEM_KEEP)
r = drv.Run(NAME, settle=0.35); g = r.g
checks = []
first_img = {}          # 대사·선택지 자리의 처음 그림
loud = {}               # 대사 자리에서 0.3초 들은 소리 크기(배경음 끔 → 음성)
TOAST = (12, 10, 520, 46)


def check(name, cond, extra=''):
    checks.append(dict(name=name, ok=bool(cond), extra=str(extra)))
    r.L(('PASS ' if cond else 'FAIL ') + name, extra)


def cmp_img(tag, a, b, box=None):
    if box: a = a.crop(box); b = b.crop(box)
    d = rw.diff(a, b, None if box else r.mask(b), 8)
    r.L('  compare', tag, 'diff pixels', d['n'], d.get('box') or '')
    return d


def hist():
    """지금 자리 = 줄의 길이(마지막으로 줄에 들어간 걸음의 번호)."""
    r.pump()
    return r.stops[-1]['hist']


def cur_id():
    r.pump()
    return r.stops[-1]['id']


def step_fwd(timeout=90):
    """Enter 한 번 → 다음에 멈출 때까지(대사·선택지, 또는 붙잡힌 소리 자막). 처음 보는 곳의 소리 자막은 저절로 흐른다."""
    n0 = len(r.stops); r.go(g.state())
    units, st = r.watch(n0, timeout, on_hold='stop')
    return units, st


def settle_line():
    """대사·선택지에 멈춘 뒤 화면이 가라앉기를 기다려 그림을 돌려준다."""
    time.sleep(r.settle)
    return g.shot()


def other_since(n, text):
    r.pump()
    return [l for l in r.other[n:] if text in l]


hint_seen = [False]


def check_hint(units):
    """그 판에서 소리 자막이 처음 붙잡힐 때 한 번: 넘기는 법을 알리는 줄이 뜨는가(화면 모듈이 켜져 있을 때)."""
    if hint_seen[0] or not units or not units[-1].get('held'): return
    hint_seen[0] = True
    u = units[-1]
    u['img_hold'].save(os.path.join(r.out, 'hint_first_hold.png'))
    dh = cmp_img('hint area at the first hold', u['img'], u['img_hold'], TOAST)
    if PRESENT[0]: check('the first time a sound subtitle is held, a notice says how to go on (%s)' % u['id'], dh['n'] > 150, 'notice pixels %d' % dh['n'])
    time.sleep(3.6)                # 그 알림이 사라질 때까지(뒤의 그림 견주기에 섞이지 않게)


PRESENT = [False]


def open_map(tag):
    """F8 → 지도가 열리면 그림을 찍고 Esc. 못 열면 None."""
    n = len(r.other)
    g.key(0x77)
    t0 = time.time()
    while time.time() - t0 < 6 and not other_since(n, 'ui opened'): g.poke(); time.sleep(0.1)
    if not other_since(n, 'ui opened'): return None
    time.sleep(0.8); img = g.shot(); img.save(os.path.join(r.out, 'map_%s.png' % tag))
    g.key(0x1B)
    t0 = time.time()
    while time.time() - t0 < 8 and not other_since(n, 'AUDIT'): g.poke(); time.sleep(0.1)
    audit = other_since(n, 'AUDIT PASS')
    time.sleep(0.5)
    return dict(img=img, audit=bool(audit))


ok = False
try:
    g.skip_events()
    assert g.wait_title()
    time.sleep(1.0)
    present = g.client() != (800, 600) or any('qol: present ok' in l for l in open(g.events_path(), encoding='utf-8', errors='replace').read().splitlines()[-40:])
    if g.client() != (800, 600):
        g.post(0x112, 0xEED0, 0)   # 창 메뉴 「원래 크기」
        t0 = time.time()
        while time.time() - t0 < 5 and g.client() != (800, 600): time.sleep(0.1)
    r.L('client', g.client(), 'screen module', present)
    PRESENT[0] = present
    assert g.client() == (800, 600)
    g.w16(0x466450, 0)             # 배경음 끔
    time.sleep(0.3)
    title0 = g.shot()
    # G) Home 조작 안내(타이틀에서)
    g.key(0x24); time.sleep(0.9); guide = g.shot(); guide.save(os.path.join(r.out, 'guide.png')); g.key(0x24); time.sleep(0.6)
    if present:
        d = cmp_img('G guide against title', title0, guide)
        check('G: Home opens the key guide over the title (picture kept as guide.png)', d['n'] > 100000, 'changed pixels %d' % d['n'])
    g.click(607, 286)              # 처음부터
    units, st = r.watch(len(r.stops), 150)
    first_img[st['id']] = settle_line()
    maps = {}
    # ---------------- 처음 읽기
    for i in range(N):
        units, st = step_fwd()
        assert st, 'first pass: no line reached (held where it should flow?) %s' % [u['id'] for u in units]
        first_img.setdefault(st['id'], settle_line())
        if st['op'] == 0x51: loud[st['id']] = r.listen(0.3)
        if st['id'] in ('2100:300', '2100:1234') and st['id'] not in maps:
            maps[st['id']] = open_map('first_' + st['id'].replace(':', '_'))
            g.wait(lambda z: z['click'] or z['choice'], 10)
    first = list(r.stops)          # 처음 읽을 때의 걸음들(소리 자막 걸음 포함), 차례대로
    ids = [s['id'] for s in first]
    r.L('first pass: %d steps (%d sound subtitles): %s' % (len(first), len([s for s in first if s['unit']]), ' '.join(ids)))
    check('first pass: sound subtitles flowed by themselves', not [l for l in r.events if 'holding the sound subtitle' in l])
    assert hist() == len(first)

    # ---------------- K) 진짜 Backspace 키 한 번
    h = hist(); n0 = len(r.stops)
    b = r.press(key=True)
    check('K: one Backspace key press goes one step back (%s -> %s)' % (ids[h - 1], ids[h - 2]), b and b['id'] == ids[h - 2] and b['steps'] == 1, r.desc(b))
    if first[h - 2]['unit']:
        got, _ = r.watch(n0, 60, on_hold='stop')
        check_hint(got)
    else: r.at_stop(40, n0)
    if not first[h - 2]['unit']:
        d = cmp_img('K line', first_img[ids[h - 2]], settle_line())
        check('K: that line looks as in the first pass', d['n'] == 0, 'diff pixels %d' % d['n'])
    g.wait(lambda z: z['click'] or z['choice'], 30)

    # ---------------- R) 누르고 있기
    h0 = hist(); nb = len(r.backs)
    g.poke(); g.post(0x100, 0x08, 1)                       # 누름
    t0 = time.time(); sent = 0
    while time.time() - t0 < 1.2:
        time.sleep(0.033); g.post(0x100, 0x08, 0x40000001); sent += 1; r.pump()   # 키 반복
    g.post(0x101, 0x08, 0xC0000001)                        # 뗌
    time.sleep(0.5); r.pump()
    got = r.backs[nb:]
    want = [ids[h0 - 2 - k] for k in range(len(got))] if h0 - 1 - len(got) >= 0 else None
    check('R: holding Backspace for 1.2 s (%d key repeats) goes back about ten steps a second, one step at a time' % sent,
          6 <= len(got) <= 13 and want is not None and [x['id'] for x in got] == want, '%d steps: %s (expected %s)' % (len(got), [x['id'] for x in got], want))
    g.wait(lambda z: z['click'] or z['choice'], 40)
    time.sleep(0.3); r.pump()
    n_after = len(r.backs)
    time.sleep(0.8); r.pump()
    check('R: it stops when the key is released', len(r.backs) == n_after and hist() == h0 - len(got), 'steps after release %d, at step %d (%s)' % (len(r.backs) - n_after, hist(), cur_id()))
    if not first[hist() - 1]['unit']:
        d = cmp_img('R line', first_img[cur_id()], settle_line())
        check('R: where it stopped looks as in the first pass (%s)' % cur_id(), d['n'] == 0, 'diff pixels %d' % d['n'])

    # ---------------- N) 더 앞이 없을 때
    b = r.press(1000)
    check('N: going back as far as it goes lands on the first step (%s)' % ids[0], b and b['id'] == ids[0], r.desc(b))
    g.wait(lambda z: z['click'] or z['choice'], 30); time.sleep(0.6)
    before = g.shot(); nr = len(r.refused); nb = len(r.backs)
    g.key(0x08); time.sleep(0.5); r.pump()
    after = g.shot(); after.save(os.path.join(r.out, 'toast_no_more.png'))
    d = cmp_img('N toast area', before, after, TOAST)
    check('N: Backspace with nothing earlier does nothing' + (' and says so' if present else ' (notice not drawn: screen module off)'), len(r.backs) == nb and r.refused[nr:] == ['no earlier stop'] and (d['n'] > 150 or not present),
          'refused %s, steps %d, notice pixels %d' % (r.refused[nr:], len(r.backs) - nb, d['n']))
    r.refused[nr:] = []            # 기대한 거절
    time.sleep(2.8)                # 알림이 사라질 때까지(뒤의 그림 견주기에 섞이지 않게)

    # ---------------- M) 선택지를 넘어 되감았다가 다시 고르기: 엔진 상태·회차 기록·지도 그림
    nv = len(r.verifies); no = len(r.other)
    # 지금 첫 걸음(선택지 1000:162). 다시 읽어 2100:1234 까지: 선택지는 고르고, 붙잡힌 소리 자막은 Enter
    seen_ids = []; held_n = 0; mapc = None
    for k in range(40):
        units, st = step_fwd()
        held_n += len([u for u in units if u['held']])
        check_hint(units)
        r.pump(); seen_ids.append(cur_id())
        if cur_id() == '2100:300' and mapc is None and st: mapc = open_map('again_2100_300'); g.wait(lambda z: z['click'] or z['choice'], 10)
        if cur_id() == '2100:1234': break
    check('M: reading on again passes the same steps in the same order', seen_ids == ids[1:1 + len(seen_ids)] and seen_ids[-1] == '2100:1234', '%s' % seen_ids)
    check('M: the sound subtitles on the way were held (seen again)', held_n == len([s for s in first[1:1 + len(seen_ids)] if s['unit']]), 'held %d' % held_n)
    vs = r.verifies[nv:]
    check('M: at every step passed again, engine state and the map run journal equal the first pass', vs and all(v['same'] for v in vs) and all('run journal' in v['detail'] for v in vs),
          '%d same, %d different %s' % (sum(1 for v in vs if v['same']), sum(1 for v in vs if not v['same']), [v for v in vs if not v['same']][:2]))
    ch = other_since(no, 'choice ')
    check('M: the choices were recorded again by the map module', len([l for l in ch if re.search(r'choice \S+ option \d', l)]) >= 2, [l.split(' ', 1)[1] for l in ch][-4:])
    if maps.get('2100:300') and mapc:
        d = cmp_img('M map at the choice 2100:300', maps['2100:300']['img'], mapc['img'])
        check('M: the story map at the choice looks as it did the first time there (later choices are not shown as made)', d['n'] == 0 and mapc['audit'], 'diff pixels %d %s' % (d['n'], d.get('box') or ''))
    else:
        r.L('map at the choice not compared (first %s, again %s)' % (bool(maps.get('2100:300')), bool(mapc)))
    if maps.get('2100:1234'):
        m2 = open_map('again_2100_1234'); g.wait(lambda z: z['click'], 10)
        d = cmp_img('M map at 2100:1234', maps['2100:1234']['img'], m2['img']) if m2 else dict(n=-1)
        check('M: after choosing again, the story map at 2100:1234 looks as in the first pass', m2 and d['n'] == 0 and m2['audit'], 'diff pixels %d %s' % (d['n'], d.get('box') or ''))

    # ---------------- A) 자동 진행 중에 Backspace
    # 다시 보는 구간의 대사 둘(L1 → L2)을 고른다: L2 가 음성 있는 대사면 음성 기다림도 본다
    lines = [i for i, s in enumerate(first) if s['op'] == 0x51]
    pairs = [(a, b) for a, b in zip(lines, lines[1:]) if b == a + 1 and a + 1 > 6]          # 사이에 소리 자막이 없는 이웃 대사
    voiced = [(a, b) for a, b in pairs if first[b]['voice']]          # 음성 명령이 딸린 대사(자막 음성). 소리 크기만으로는 효과음과 못 가린다
    quiet = [(a, b) for a, b in pairs if loud.get(ids[b], 1) < 0.02]
    r.L('auto: neighbour line pairs %d, with a voiced second line %d, with a quiet one %d' % (len(pairs), len(voiced), len(quiet)))

    def goto(i):
        """first[i] 자리로(뒤면 한 번에 되감고, 앞이면 Enter 로). 그 자리에서 멈출 때까지."""
        h = hist()
        if i + 1 < h:
            n0 = len(r.stops); b = r.press(h - (i + 1))
            assert b and b['id'] == ids[i], (ids[i], b and b['id'])
            if first[i]['unit']: r.watch(n0, 60, on_hold='stop')
            else: r.at_stop(40, n0)
        while hist() < i + 1: step_fwd()
        assert cur_id() == ids[i], (cur_id(), ids[i])

    def auto_case(tag, a, b, in_voice):
        """돌려주는 값: 눌렀을 때 바라던 기다림 안이었는가(음성 기다림은 음성이 글보다 길 때만 생긴다 → 아니면 다음 후보로)."""
        goto(a)
        n0 = len(r.stops); no = len(r.other)
        g.key(ord('A'))
        on = g.wait(lambda z: z['auto'] == 1, 5)
        if in_voice:
            for _ in range(4): g.key(ord('A'), hold=0.03)      # ×5: 글 기다림이 1/5 로 줄어 음성이 글보다 오래 간다
        t0 = time.time(); reached = False
        while time.time() - t0 < 25:
            g.poke(); r.pump()
            if len(r.stops) > n0 and r.stops[-1]['id'] == ids[b]: reached = True; break
            time.sleep(0.02)
        if in_voice:
            # 글 기다림이 끝나 음성 기다림에 들어갈 때까지(진행 모듈 기록 「wait x1 …」)
            t0 = time.time()
            while time.time() - t0 < 15 and not other_since(no, 'play: wait x') and len(r.stops) == n0 + 1: g.poke(); r.pump(); time.sleep(0.01)
            time.sleep(0.10)
            inside = bool(other_since(no, 'play: wait x')) and not other_since(no, 'play: voice wait') and len(r.stops) == n0 + 1
            where = 'voice wait' if inside else 'NOT in the voice wait'
        else:
            time.sleep(0.5)
            inside = not other_since(no, 'play: wait x') and len(r.stops) == n0 + 1
            where = 'text wait' if inside else 'after the text wait'
        z0 = g.state(); pk = r.peak_now()
        if not inside:
            # 이미 지나갔다: 자동을 끄고(클릭) 다음 후보로
            g.click(400, 300); g.wait(lambda z: z['auto'] == 0, 6); g.wait(lambda z: z['click'] == 1, 20)
            r.L('A/%s: %s -> %s was %s when it was time to press; trying another' % (tag, ids[a], ids[b], where))
            return False
        bk = r.press(key=True)
        z1 = g.wait(lambda z: z['click'] == 1, 10)
        check('A/%s: Backspace during auto progress (%s, auto %d, sound %.2f) turns auto off and goes one step back (%s -> %s)' % (tag, where, z0['auto'], pk, ids[b], ids[a]),
              on and reached and bk and bk['id'] == ids[a] and z1 and z1['auto'] == 0 and bk['wake'] < 300, r.desc(bk))
        d = cmp_img('A/%s line' % tag, first_img[ids[a]], settle_line())
        check('A/%s: that line looks as in the first pass, and auto stays off' % tag, d['n'] == 0 and g.state()['auto'] == 0, 'diff pixels %d, auto %d' % (d['n'], g.state()['auto']))
        return True

    done_text = any(auto_case('text', a, b, False) for a, b in (quiet[::-1] + pairs[::-1])[:3])
    check('A: a text-wait case was run', done_text)
    done_voice = any(auto_case('voice', a, b, True) for a, b in voiced[::-1][:4])
    if not done_voice: r.L('A/voice: no line whose voice outlasts the text wait among %d candidates; the voice-wait case was not run' % len(voiced[:4]))

    # ---------------- S) 붙잡힌 소리 자막에서 바로 저장 → 저장 파일에는 그 앞 대사
    cand = [i for i, s in enumerate(first) if s['unit'] and i > 6 and not first[i - 1]['unit'] and first[i - 1]['op'] == 0x51]
    if cand:
        u = cand[-1]
        goto(u - 1)
        units, st = step_fwd()
        held = bool(units and units[-1]['held'] and units[-1]['id'] == ids[u])
        check('S: setup, the sound subtitle %s is held' % ids[u], held, [x['id'] for x in units])
        if held:
            hint = units[-1]['img_hold']; hint.save(os.path.join(r.out, 'held_subtitle.png'))
            no = len(r.other); t_save = time.time()
            g.key(ord('S')); time.sleep(0.8)
            sv = other_since(no, 'play: S -> slot')
            m = re.search(r'S -> slot (\d+) saved', sv[-1]) if sv else None
            files = [f for f in glob.glob(os.path.join(rw.GAME, 'save', '*.dat')) + glob.glob(os.path.join(rw.GAME, '*.dat')) if os.path.getmtime(f) >= t_save - 1 and os.path.getsize(f) == 50668]
            pos = None
            if files:
                raw = open(files[0], 'rb').read()
                ctx = raw[20:20 + 0x2c3c]
                dp = struct.unpack_from('<H', ctx, 0x50)[0] & 15
                pos = '%04d:%d' % (struct.unpack_from('<H', ctx, 0x12 + 2 * dp)[0], struct.unpack_from('<I', ctx, 0x28 + 4 * dp)[0])
            check('S: saving while it is held stores the line before it (%s), as it would in the first pass' % ids[u - 1], m and pos == ids[u - 1],
                  '%s; file %s holds %s' % (sv[-1].split('play: ')[-1] if sv else 'no save line', os.path.basename(files[0]) if files else None, pos))
            # T) 붙잡힌 채 A → 자동 진행으로 넘어간다
            n0 = len(r.stops)
            g.key(ord('A'))
            on = g.wait(lambda z: z['auto'] == 1, 5)
            t0 = time.time(); moved = False
            while time.time() - t0 < 12:
                g.poke(); r.pump()
                if len(r.stops) > n0: moved = True; break
                time.sleep(0.02)
            check('T: A on the held sound subtitle turns auto on and it moves on by itself', on and moved, 'auto %s, next step %s' % (bool(on), r.stops[-1]['id']))
            g.click(400, 300)                                  # 클릭으로 자동 끔(원작 동작)
            off = g.wait(lambda z: z['auto'] == 0, 6)
            g.wait(lambda z: z['click'] == 1, 20)
            check('T: a click turns auto off as before', bool(off))
    else:
        r.L('no sound subtitle after a line in the first pass; S/T not run')

    # ---------------- X) Tab 건너뛰기 중에 Backspace
    goto(max(7, len(first) - 9))
    n0 = len(r.stops); nb = len(r.backs)
    g.key(0x09)                                            # Tab = 건너뛰기 켜기
    t0 = time.time()
    while time.time() - t0 < 6 and len(r.stops) < n0 + 2: g.poke(); r.pump(); time.sleep(0.01)
    skipped = len(r.stops) - n0
    bk = r.press(key=True)
    z = g.wait(lambda z: z['click'] or z['choice'], 20)
    tab = (g.u32(0x4663fc), g.u32(0x466404))
    time.sleep(0.6); r.pump(); n_stop = len(r.stops)
    time.sleep(0.8); r.pump()
    check('X: Backspace during Tab skip (after %d steps) stops the skip and goes back' % skipped, skipped >= 2 and bk is not None and tab == (0, 0) and z and len(r.stops) == n_stop,
          '%s; skip flags %s; steps after stopping %d' % (r.desc(bk), tab, len(r.stops) - n_stop))
    if z and hist() <= len(first) and not first[hist() - 1]['unit'] and cur_id() in first_img:
        d = cmp_img('X line', first_img[cur_id()], settle_line())
        check('X: where it stopped looks as in the first pass (%s)' % cur_id(), d['n'] == 0, 'diff pixels %d' % d['n'])

    # ---------------- 끝
    r.pump()
    bad = [v for v in r.verifies if not v['same']]
    check('engine state and run journal are the same whenever a step is passed again', not bad and r.verifies, '%d same, %d different %s' % (sum(1 for v in r.verifies if v['same']), len(bad), bad[:3]))
    check('no unexpected refusal, no dropped request', not r.refused and not [l for l in r.events if 'request dropped' in l], r.refused)
    errs = [l for l in r.other if any(k in l.lower() for k in ('exception', 'audit fail', 'error', 'disabled after'))] + [l for l in r.events if 'ERROR' in l]
    check('no error lines', not errs, errs[-3:])
    ok = all(c['ok'] for c in checks)
finally:
    g.w16(0x466450, 1)             # 배경음 설정을 되돌린다
    try:
        r.summary(ok, dict(checks=checks, checks_passed='%d/%d' % (sum(c['ok'] for c in checks), len(checks))))
    finally:
        r.release_audio()
        q = r.finish(ok)
        if os.path.exists(WINMEM_KEEP): shutil.copyfile(WINMEM_KEEP, WINMEM); os.remove(WINMEM_KEEP)   # 창 기억을 시험 전으로
        print('RESULT checks %d/%d, normal quit %s' % (sum(c['ok'] for c in checks), len(checks), q))

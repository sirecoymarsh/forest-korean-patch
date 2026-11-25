# -*- coding: utf-8 -*-
"""되감기 충실도·지연 시험.

처음부터 N 걸음 읽으며 멈춘 자리마다 그림을 떠 두고, 되감기(1걸음·여러 걸음·끝까지)와 다시 읽기를 섞어
① 되돌아간 화면이 처음 지날 때와 같은지(화소 비교) ② 엔진 상태가 같은지(시험 모듈의 verify 줄)
③ 걸린 시간(시험 모듈 기록) ④ 다녀온 뒤에도 정상 종료하는지 본다.
사용: python -I t2_fidelity.py <출력 폴더 이름> [걸음 수]
"""
import json, os, random, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rw

NAME = sys.argv[1] if len(sys.argv) > 1 else 't2'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 60
OUT = os.path.join(r'Y:\AI\forest-qol-test-rewind\out', NAME)
g = rw.Game(OUT)
STOP = re.compile(r'rewind: stop (\d+):(\d+) op 0x([0-9a-f]+) depth (\d+) bgm (\d+) se (\d+)/(\d+) -> history (\d+)')
BACK = re.compile(r'rewind: #(\d+) back (\d+) to (\d+):(\d+) op 0x([0-9a-f]+) depth (\d+).*?key-to-start ([\-\d.]+) ms, voice ([\d.]+), copy ([\d.]+), sound ([\d.]+), script ([\d.]+), rebuild ([\d.]+), paint ([\d.]+), total ([\d.]+) ms \| history left (\d+) \| (\w+) layers kept (\d+)/50, bgm (\d+)>(\d+)(.*)')
VERIFY = re.compile(r'rewind: verify (\d+):(\d+) (SAME|DIFF)(.*)')
REFUSED = re.compile(r'rewind: .*refused: (.*)')

events = []       # 모든 rewind 줄
stops = []        # 로그의 stop 줄(차례대로): dict(id, op, hist)
backs = []
verifies = []
refused = []


def pump():
    new = []
    for l in g.new_events():
        if 'rewind:' not in l: continue
        events.append(l); new.append(l)
        m = STOP.search(l)
        if m: stops.append(dict(id='%s:%s' % (m.group(1), m.group(2)), op=int(m.group(3), 16), bgm=int(m.group(5)), hist=int(m.group(8))))
        m = BACK.search(l)
        if m: backs.append(dict(seq=int(m.group(1)), steps=int(m.group(2)), id='%s:%s' % (m.group(3), m.group(4)), op=int(m.group(5), 16), wake=float(m.group(7)), voice=float(m.group(8)),
                                copy=float(m.group(9)), sound=float(m.group(10)), script=float(m.group(11)), rebuild=float(m.group(12)), paint=float(m.group(13)), total=float(m.group(14)),
                                left=int(m.group(15)), mode=m.group(16), kept=int(m.group(17)), bgm=(int(m.group(18)), int(m.group(19))), note=m.group(20).strip()))
        m = VERIFY.search(l)
        if m: verifies.append(dict(id='%s:%s' % (m.group(1), m.group(2)), same=m.group(3) == 'SAME', detail=m.group(4).strip()))
        m = REFUSED.search(l)
        if m: refused.append(m.group(1))
    return new


def at_stop(timeout=40, need_new_stop=True, n0=None):
    """멈춘 자리(클릭 대기나 선택지)에 닿을 때까지. 닿으면 (상태, 마지막 stop 줄)."""
    t0 = time.time(); n0 = len(stops) if n0 is None else n0
    while time.time() - t0 < timeout:
        g.poke(); pump()
        s = g.state()
        if (s['click'] or s['choice']) and (not need_new_stop or len(stops) > n0):
            time.sleep(0.05); pump()
            return s, stops[-1] if stops else None
        if s['typing'] and not s['click'] and FASTTYPE: g.w32(0x4663d4, 1)   # 시험 가속: 찍히는 글을 한꺼번에(클릭과 같은 엔진 깃발)
        if not g.alive(): raise RuntimeError('game exited')
        time.sleep(0.03)
    return None, None


FASTTYPE = True
CHOICE_AT = [(300, 245), (400, 262), (400, 230), (400, 300), (400, 340), (400, 190)]   # 날짜 잎사귀, 그 밖의 선택지 자리 후보


def go(s):
    """지금 멈춘 자리를 넘긴다: 대사는 Enter, 선택지는 갈래를 누른다(안 눌리면 다른 자리)."""
    if s['choice']:
        for x, y in CHOICE_AT:
            g.click(x, y)
            if g.wait(lambda z: not z['choice'], 1.5): return
        g.L('choice not answered at', s)
    else:
        g.key(0x0D)


MASK = [(736, 548, 800, 600)]   # 대기 표시(움직이는 그림)
shots = {}                      # id → 처음 지날 때의 그림(같은 자리를 여러 번 지나면 맨 처음 것)
order = []                      # 처음 읽을 때 지난 차례(id)
result = dict(compare=[], notes=[])


def settle_shot():
    time.sleep(0.45)
    return g.shot()


def compare(tag, sid, img):
    if sid not in shots:
        result['compare'].append(dict(tag=tag, id=sid, n=None)); g.L('  compare', tag, sid, 'no first-pass picture'); return None
    d = rw.diff(shots[sid], img, MASK)
    result['compare'].append(dict(tag=tag, id=sid, n=d['n'], box=d.get('box')))
    g.L('  compare', tag, sid, 'diff pixels', d['n'], d.get('box') or '')
    if d['n']:
        k = len([c for c in result['compare'] if c['n']])
        if k <= 6:
            shots[sid].save(os.path.join(OUT, 'diff%02d_%s_first.png' % (k, sid.replace(':', '_'))))
            img.save(os.path.join(OUT, 'diff%02d_%s_again.png' % (k, sid.replace(':', '_'))))
    return d


ok = False
try:
    g.skip_events()
    s = g.wait_title()
    assert s, 'title not reached'
    g.L('title', s, 'client', g.client())
    time.sleep(0.8)
    g.click(607, 286)          # 처음부터
    # ---- 1) 처음 읽기
    n0 = 0
    for i in range(N):
        s, st = at_stop(60, True, n0)
        assert s, 'no stop at step %d (state %s)' % (i, g.state())
        n0 = len(stops)
        img = settle_shot()
        sid = st['id']
        if sid not in shots: shots[sid] = img
        order.append(sid)
        if i < 3 or i == N - 1: img.save(os.path.join(OUT, 'first_%03d.png' % i))
        go(s)
    s, st = at_stop(60, True, n0)
    order.append(st['id']); shots.setdefault(st['id'], settle_shot())
    g.L('first pass done:', len(order), 'stops; kinds', sorted(set(hex(x['op']) for x in stops)), 'bgm set', sorted(set(x['bgm'] for x in stops)))

    def back(k, tag):
        """k 걸음 되감고, 닿은 자리의 그림을 처음 것과 견준다."""
        nb = len(backs); n0 = len(stops)
        bg0 = g.bgm_engine()
        g.rewind(k)
        t0 = time.time()
        while len(backs) == nb and time.time() - t0 < 10:
            g.poke(); pump(); time.sleep(0.01)
            if refused and time.time() - t0 > 1.0 and len(backs) == nb: break
        if len(backs) == nb:
            g.L('  back', k, tag, 'NOT DONE', refused[-1:] or ''); result['notes'].append('back %d %s not done' % (k, tag)); return None
        b = backs[-1]
        s, st = at_stop(40, True, n0)
        img = settle_shot()
        bg1 = g.bgm_engine()
        b['bgm_before'] = bg0; b['bgm_after'] = bg1
        g.L('  back', k, tag, '->', b['id'], 'total %.1f ms (voice %.1f sound %.1f script %.1f rebuild %.1f paint %.1f; key-to-start %.1f; kept %d)' % (
            b['total'], b['voice'], b['sound'], b['script'], b['rebuild'], b['paint'], b['wake'], b['kept']), 'bgm', bg0, '->', bg1, b['note'])
        compare(tag, st['id'], img)
        return b

    def fwd(k, tag):
        for j in range(k):
            s = g.state(); n0 = len(stops)
            go(s)
            s, st = at_stop(60, True, n0)
            assert s, 'no stop while going forward'
            compare(tag + '+%d' % (j + 1), st['id'], settle_shot())

    # ---- 2) 한 걸음, 여러 걸음, 다시 읽기
    back(1, 'one')
    back(1, 'one-again')
    back(5, 'five')
    fwd(7, 'reread')
    back(20, 'twenty')
    fwd(3, 'reread20')
    back(2, 'two')
    # ---- 3) 마구잡이 40번
    rnd = random.Random(1125)
    for t in range(40):
        if rnd.random() < 0.6:
            back(rnd.choice([1, 1, 1, 2, 3, 4, 8]), 'rand%02d' % t)
        else:
            fwd(rnd.choice([1, 1, 2, 3]), 'rand%02d' % t)
    # ---- 4) 맨 처음까지
    back(1000, 'all-the-way')
    s = g.state(); g.L('at oldest stop', s)
    back(1, 'beyond-oldest')    # 더 못 돌아감 → 거절되어야 한다
    fwd(4, 'reread-from-start')
    pump()
    ok = True
finally:
    try:
        pump()
        tot = [b['total'] for b in backs]; wk = [b['wake'] for b in backs if b['wake'] >= 0]
        summ = dict(stops_first=len(order), backs=len(backs),
                    total_ms=dict(min=min(tot), max=max(tot), avg=sum(tot) / len(tot)) if tot else None,
                    wake_ms=dict(min=min(wk), max=max(wk), avg=sum(wk) / len(wk)) if wk else None,
                    rebuild_ms_max=max([b['rebuild'] for b in backs] or [0]), paint_ms_max=max([b['paint'] for b in backs] or [0]),
                    verify_same=sum(1 for v in verifies if v['same']), verify_diff=[v for v in verifies if not v['same']][:20],
                    compared=len([c for c in result['compare'] if c['n'] is not None]),
                    pixel_diffs=[c for c in result['compare'] if c['n']][:40], refused=refused, notes=result['notes'], ok=ok)
        json.dump(dict(summary=summ, backs=backs, compare=result['compare']), open(os.path.join(OUT, 'result.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        open(os.path.join(OUT, 'rewind_events.log'), 'w', encoding='utf-8').write('\n'.join(events))
        g.L('SUMMARY', json.dumps(summ, ensure_ascii=False))
    finally:
        q = g.quit() if g.alive() and g.h else False
        g.L('normal quit', q, 'ok', ok)
        g.close()

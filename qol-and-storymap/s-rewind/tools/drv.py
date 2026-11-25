# -*- coding: utf-8 -*-
"""되감기 시험 몰이(공통): 멈춘 자리 찾기·넘기기·되감기·그림 견주기·요약."""
import json, os, re, time
import rw

STOP = re.compile(r'rewind: stop (\d+):(\d+) op 0x([0-9a-f]+) depth (\d+) bgm (\d+) se (\d+)/(\d+) -> history (\d+)(.*)')
EXTRA = re.compile(r'texts (\d+) held (\d+)(?: visual ([\d.]+) subs ([\d.]+))?')
BACK = re.compile(r'rewind: #(\d+) back (\d+) to (\d+):(\d+) op 0x([0-9a-f]+) depth (\d+).*?key-to-start ([\-\d.]+) ms, voice ([\d.]+), copy ([\d.]+), sound ([\d.]+), script ([\d.]+), rebuild ([\d.]+), paint ([\d.]+), total ([\d.]+) ms \| history left (\d+) \| (\w+) layers kept (\d+)/50, bgm (\d+)>(\d+)(.*)')
VERIFY = re.compile(r'rewind: verify (\d+):(\d+) (SAME|DIFF)(.*)')
REFUSED = re.compile(r'rewind: .*refused: (.*)')
CLEARED = re.compile(r'rewind: history cleared \((.*?)\)')
PRESSED = re.compile(r'rewind: pressed (.*)')
CHOICE_AT = [(300, 245), (400, 262), (400, 230), (400, 300), (400, 340), (400, 190)]   # 날짜 잎사귀, 그 밖의 선택지 자리 후보
MASK800 = [(736, 548, 800, 600)]   # 대기 표시(움직이는 그림), 800×600 기준


def ini_on(key, default=False):
    """시험 사본의 forest-qol.ini 에서 그 줄이 1 인가(없으면 default)."""
    try:
        for l in open(os.path.join(rw.GAME, 'forest-qol.ini'), encoding='utf-8-sig', errors='replace'):
            l = l.split(';', 1)[0].strip()
            if l.startswith(key + '='): return l.split('=', 1)[1].strip() not in ('0', '')
    except OSError:
        pass
    return default


class Run:
    def __init__(self, name, fasttype=True, settle=0.45):
        self.out = os.path.join(r'Y:\AI\forest-qol-test-rewind\out', name)
        self.g = rw.Game(self.out)
        self.fasttype = fasttype; self.settle = settle
        self.events = []; self.stops = []; self.backs = []; self.verifies = []; self.refused = []; self.cleared = []; self.other = []
        self.shots = {}; self.order = []; self.cmp = []; self.notes = []; self.recheck = []
        self.L = self.g.L

    # ---- 기록 읽기
    def pump(self):
        new = []
        for l in self.g.new_events():
            if 'rewind:' not in l:
                self.other.append(l); continue
            self.events.append(l); new.append(l)
            m = STOP.search(l)
            if m: self.stops.append(dict(id='%s:%s' % (m.group(1), m.group(2)), op=int(m.group(3), 16), bgm=int(m.group(5)), se=int(m.group(6)), loop=int(m.group(7)), hist=int(m.group(8)),
                                         sub='+subtitle' in m.group(9), voice='+voice' in m.group(9), unit='+unit' in m.group(9), reread='+reread' in m.group(9)))
            m = BACK.search(l)
            if m:
                x = EXTRA.search(m.group(20))
                self.backs.append(dict(seq=int(m.group(1)), steps=int(m.group(2)), id='%s:%s' % (m.group(3), m.group(4)), op=int(m.group(5), 16), wake=float(m.group(7)), voice=float(m.group(8)),
                                       copy=float(m.group(9)), sound=float(m.group(10)), script=float(m.group(11)), rebuild=float(m.group(12)), paint=float(m.group(13)), total=float(m.group(14)),
                                       left=int(m.group(15)), mode=m.group(16), kept=int(m.group(17)), bgm=(int(m.group(18)), int(m.group(19))),
                                       note=EXTRA.sub('', m.group(20)).strip(), texts=int(x.group(1)) if x else 0, held=int(x.group(2)) if x else -1,
                                       visual=float(x.group(3)) if x and x.group(3) else -1.0, subs=float(x.group(4)) if x and x.group(4) else 0.0))
            m = VERIFY.search(l)
            if m: self.verifies.append(dict(id='%s:%s' % (m.group(1), m.group(2)), same=m.group(3) == 'SAME', detail=m.group(4).strip()))
            m = REFUSED.search(l)
            if m: self.refused.append(m.group(1))
            m = CLEARED.search(l)
            if m: self.cleared.append(m.group(1))
        return new

    # ---- 멈춘 자리
    def at_stop(self, timeout=40, n0=None, need_new=True):
        g = self.g; t0 = time.time(); n0 = len(self.stops) if n0 is None else n0
        while time.time() - t0 < timeout:
            g.poke(); self.pump()
            s = g.state()
            if (s['click'] or s['choice']) and (not need_new or len(self.stops) > n0):
                time.sleep(0.05); self.pump()
                return s, (self.stops[-1] if self.stops else None)
            if s['typing'] and not s['click'] and self.fasttype: g.w32(0x4663d4, 1)   # 시험 가속: 찍히는 글을 한꺼번에(클릭과 같은 엔진 깃발)
            if not g.alive(): raise RuntimeError('game exited')
            time.sleep(0.03)
        return None, None

    def go(self, s=None):
        g = self.g; s = s or g.state()
        if s['choice']:
            for x, y in CHOICE_AT:
                g.click(x, y)
                if g.wait(lambda z: not z['choice'], 1.5): return True
            self.L('choice not answered at', s); return False
        g.key(0x0D); return True

    def shot(self):
        time.sleep(self.settle)
        return self.g.shot()

    def mask(self, img):
        w, h = img.size
        if (w, h) == (800, 600): return MASK800
        # 큰 창: 4:3 그림이 가운데 들어가고 남는 곳은 검은 띠(화면 모듈의 배치와 같은 식)
        if w * 600 <= h * 800: cw, ch = w, (w * 600 + 400) // 800
        else: ch, cw = h, (h * 800 + 300) // 600
        ox, oy = (w - cw) // 2, (h - ch) // 2
        sx, sy = cw / 800.0, ch / 600.0
        return [(int(ox + a * sx) - 2, int(oy + b * sy) - 2, int(ox + c * sx) + 3, int(oy + d * sy) + 3) for a, b, c, d in MASK800]

    def keep(self, sid, img):
        """처음 지날 때의 그림을 둔다(큰 창이면 PNG 로 눌러서)."""
        if sid in self.shots: return
        if img.size[0] * img.size[1] > 1200 * 900:
            import io
            b = io.BytesIO(); img.save(b, 'PNG', compress_level=1); self.shots[sid] = b.getvalue()
        else:
            self.shots[sid] = img

    def first_img(self, sid):
        v = self.shots[sid]
        if isinstance(v, bytes):
            import io
            from PIL import Image
            return Image.open(io.BytesIO(v)).convert('RGB')
        return v

    def compare(self, tag, sid, img, tol=8):
        if sid not in self.shots:
            self.cmp.append(dict(tag=tag, id=sid, n=None)); self.L('  compare', tag, sid, 'no first-pass picture'); return None
        first = self.first_img(sid)
        d = rw.diff(first, img, self.mask(img), tol)
        if d['n']:
            # 다르면 0.25초 뒤에 한 번 더 찍어 견준다. 그때 같으면: 화면은 온전하고, 앞 그림이 덜 찍혔거나 그 사이에 스스로 고쳐진 잠깐의 다름이다
            # → 「다름」으로 세지 않되 따로 적고 그림도 남긴다(잠깐의 다름은 t14·t16 처럼 쉬지 않고 찍는 시험으로 따로 본다).
            time.sleep(0.25)
            img2 = self.g.shot(); d2 = rw.diff(first, img2, self.mask(img2), tol)
            if not d2['n']:
                self.recheck.append(dict(tag=tag, id=sid, n=d['n'], box=d.get('box')))
                self.L('  compare', tag, sid, 'differed by', d['n'], d.get('box') or '', 'but is the same when taken again 0.25 s later')
                if len(self.recheck) <= 6: img.save(os.path.join(self.out, 'recheck%02d_%s_first_try.png' % (len(self.recheck), sid.replace(':', '_'))))
                img, d = img2, d2
        self.cmp.append(dict(tag=tag, id=sid, n=d['n'], box=d.get('box')))
        self.L('  compare', tag, sid, 'diff pixels', d['n'], d.get('box') or '')
        if d['n']:
            k = len([c for c in self.cmp if c['n']])
            if k <= 8:
                first.save(os.path.join(self.out, 'diff%02d_%s_first.png' % (k, sid.replace(':', '_'))))
                img.save(os.path.join(self.out, 'diff%02d_%s_again.png' % (k, sid.replace(':', '_'))))
        return d

    # ---- 처음 읽기
    def start_new_game(self):
        g = self.g
        g.skip_events()
        s = g.wait_title()
        assert s, 'title not reached'
        self.L('title', s, 'client', g.client())
        g.w16(0x466450, 1)         # 배경음 켬(설정 깃발). 소리 시험(t7)이 꺼 둔 채 끝나면 엔진이 그 설정을 rssave.dat 에 적어 다음 실행까지 남는다
        time.sleep(0.8)
        g.click(607, 286)          # 처음부터

    def first_pass(self, n, save_every=0):
        n0 = len(self.stops)
        for i in range(n):
            s, st = self.at_stop(60, n0)
            assert s, 'no stop at step %d (state %s)' % (i, self.g.state())
            n0 = len(self.stops)
            img = self.shot(); sid = st['id']
            self.keep(sid, img); self.order.append(sid)
            if save_every and i % save_every == 0: img.save(os.path.join(self.out, 'first_%03d_%s.png' % (i, sid.replace(':', '_'))))
            assert self.go(s), 'could not go on at step %d' % i
        s, st = self.at_stop(60, n0)
        self.order.append(st['id']); self.keep(st['id'], self.shot())
        self.L('first pass done:', len(self.order), 'stops; kinds', sorted(set(hex(x['op']) for x in self.stops)), 'bgm', sorted(set(x['bgm'] for x in self.stops)),
               'se loops', len([x for x in self.stops if x['loop']]))

    # ---- 되감기·다시 읽기
    def back(self, k, tag, compare=True, settle=True):
        g = self.g; nb = len(self.backs); n0 = len(self.stops); nr = len(self.refused)
        bg0 = g.bgm_engine()
        g.rewind(k)
        t0 = time.time()
        while len(self.backs) == nb and time.time() - t0 < 10:
            g.poke(); self.pump(); time.sleep(0.01)
            if len(self.refused) > nr: break
        if len(self.backs) == nb:
            self.L('  back', k, tag, 'NOT DONE', self.refused[-1:] or ''); self.notes.append('back %d %s not done: %s' % (k, tag, (self.refused[-1:] or [''])[0])); return None
        b = self.backs[-1]
        s, st = self.at_stop(40, n0)
        b['bgm_engine'] = (bg0, g.bgm_engine()); b['tag'] = tag
        self.L('  back', k, tag, '->', b['id'], 'screen %.1f ms, with sound %.1f ms (rebuild %.1f subs %.1f paint %.1f | voice-stop %.1f sound %.1f; key-to-start %.1f; kept %d; held %d)' % (
            b['visual'], b['total'], b['rebuild'], b['subs'], b['paint'], b['voice'], b['sound'], b['wake'], b['kept'], b['held']), 'bgm', b['bgm_engine'], b['note'])
        if compare and st: self.compare(tag, st['id'], self.shot() if settle else g.shot())
        return b

    def fwd(self, k, tag, compare=True):
        for j in range(k):
            s = self.g.state(); n0 = len(self.stops)
            if not (s['click'] or s['choice']): s, _ = self.at_stop(40, need_new=False)
            self.go(s)
            s, st = self.at_stop(60, n0)
            assert s, 'no stop while going forward'
            if compare: self.compare(tag + '+%d' % (j + 1), st['id'], self.shot())

    # ---- 소리 자막 걸음까지 보는 몰이(t11·t13)
    PRI = 0x4690a8          # 엔진이 들고 있는 「지금 상태」 한 벌(저장하면 파일에 들어간다)
    paged = frozenset()     # 쪽을 넘기는 자막 id(뜨자마자 붙잡힌다)
    shot_at = 0.30          # 소리 자막이 뜬 뒤 이만큼 지나 화면을 찍는다
    notice_wait = 0.0       # 게임을 켜고 처음 붙잡을 때는 알림 한 줄이 3.5초 뜬다(화면 모듈이 켜져 있으면 그림에 나온다). 0 이 아니면 그만큼 더 기다렸다가 붙잡힌 화면을 찍는다
    held_once = False

    def peak_now(self):
        import audio
        if not getattr(self, 'found', None): self.found = audio.sessions(self.g.pid)
        try:
            p, m = audio.peak(self.found)
        except OSError:
            audio.release(self.found); self.found = []; return 0.0
        if m is False: self.g.mute()
        return p

    def listen(self, sec):
        best = 0.0; t0 = time.time()
        while time.time() - t0 < sec:
            self.g.poke(); best = max(best, self.peak_now()); time.sleep(0.012)
        return best

    def release_audio(self):
        import audio
        if getattr(self, 'found', None): audio.release(self.found); self.found = []

    def pri_pos(self):
        g = self.g; d = g.u16(self.PRI + 0x50) & 15
        return '%04d:%d' % (g.u16(self.PRI + 0x12 + 2 * d), g.u32(self.PRI + 0x28 + 4 * d))

    def watch(self, n0, timeout=120, on_unit=None, on_hold='enter', page2_at=None):
        """다음에 「대사·선택지」에서 멈출 때까지 본다. 그 사이에 흐른 소리 자막마다: 뜬 지 shot_at 초 뒤의 화면, 소리 크기의 흐름.
        on_unit(u) 가 True 를 돌려주면 그 자막이 뜬 순간 그만 본다.
        자막이 붙잡히면(기록 줄 holding …): 붙잡힌 화면·엔진 상태를 적고, on_hold 가 'enter' 면 Enter 로 넘기고 'stop' 이면 그만 본다.
        page2_at: 처음 지날 때 쪽 넘기는 자막의 둘째 쪽을 찍는 때.
        돌려주는 것: (소리 자막들, 멈춘 자리 또는 None)"""
        g = self.g
        seen = n0; units = []; t0 = time.time(); cur = None; ev0 = len(self.events)
        while time.time() - t0 < timeout:
            g.poke(); self.pump()
            now = time.time()
            while seen < len(self.stops):
                st = self.stops[seen]; seen += 1
                if cur and 'dur' not in cur: cur['dur'] = now - cur['t']
                cur = None
                if not st['unit']: continue
                cur = dict(id=st['id'], t=now, sub=st['sub'], reread=st['reread'], env=[], img=None, pri=self.pri_pos(), held=False)
                units.append(cur)
                if on_unit and on_unit(cur): return units, None
            if cur and not cur['held']:
                dt = now - cur['t']
                cur['env'].append((dt, self.peak_now()))
                if cur['img'] is None and dt >= self.shot_at: cur['img'] = g.shot(); cur['img_at'] = dt
                if page2_at and cur['id'] in self.paged and 'img2' not in cur and dt >= page2_at: cur['img2'] = g.shot()
            new = self.events[ev0:]; ev0 = len(self.events)
            if any('holding the sound subtitle' in l for l in new):
                if cur is None:                                         # 이 관찰이 시작되기 전에 뜬 자막이 붙잡혔다
                    cur = dict(id=self.stops[-1]['id'] if self.stops else '?', t=now, sub=False, reread=True, env=[], img=None, pri=self.pri_pos(), held=False)
                    units.append(cur)
                cur['held'] = True; cur['dur'] = now - cur['t']; cur['hold_at'] = now - cur['t']
                first_hold = not self.held_once; self.held_once = True
                time.sleep(0.30 + (self.notice_wait if first_hold else 0.0))
                if cur['img'] is None: cur['img'] = g.shot()            # 쪽 넘기는 자막은 뜨자마자 붙잡힌다
                cur['img_hold'] = g.shot(); cur['state_hold'] = g.state(); cur['pri_hold'] = self.pri_pos()
                cur['peak_hold'] = self.listen(0.5) if cur['id'] not in self.paged else None
                if on_hold == 'stop': break
                g.key(0x0D)
            z = g.state()
            if (z['click'] or z['choice']) and len(self.stops) > n0 and not self.stops[-1]['unit'] and seen == len(self.stops):
                time.sleep(0.05); self.pump()
                if seen == len(self.stops): break
            if z['typing'] and not z['click'] and self.fasttype: g.w32(0x4663d4, 1)
            if not g.alive(): raise RuntimeError('game exited')
            time.sleep(0.008)
        else:
            raise RuntimeError('no stop within %d s (state %s)' % (timeout, g.state()))
        for u in units:
            u['peak'] = max([p for _, p in u['env']] or [0.0])
        last = self.stops[-1] if self.stops else None
        return units, (last if last and not last['unit'] else None)

    def press(self, k=1, key=False):
        """되감기 요청 → 되돌린 기록 줄이 나올 때까지. key=True 면 진짜 Backspace 키(한 걸음), 아니면 시험 메시지(k 걸음).
        돌려주는 것에 「어디서 눌렀나」(where)도 붙인다. 거절되거나 4초 안에 안 되면 None."""
        g = self.g
        nb = len(self.backs); nr = len(self.refused); ne = len(self.events)
        if key: g.key(0x08)
        else: g.rewind(k)
        t0 = time.time()
        while len(self.backs) == nb and time.time() - t0 < 4:
            g.poke(); self.pump(); time.sleep(0.004)
            if len(self.refused) > nr: return None
        if len(self.backs) == nb: return None
        b = self.backs[-1]
        w = [m.group(1) for l in self.events[ne:] for m in [PRESSED.search(l)] if m]
        b['where'] = w[-1] if w else ''
        return b

    @staticmethod
    def desc(b):
        return b and ('went to %s (%s), key-to-start %.1f ms, screen %.1f ms%s' % (b['id'], b.get('where', ''), b['wake'], b['visual'], (' ' + b['note']) if b['note'] else ''))

    def hist(self):
        """지금 자리 = 줄의 길이(마지막으로 줄에 들어간 걸음의 번호)."""
        self.pump()
        return self.stops[-1]['hist'] if self.stops else 0

    def fwd_lines(self, k, tag='', compare=False):
        """대사·선택지 k 개만큼 앞으로. 그 사이의 소리 자막은 흐르거나(처음 보는 곳) 붙잡히면 Enter 로 넘긴다."""
        st = None
        for j in range(k):
            s = self.g.state()
            if not (s['click'] or s['choice']): s, _ = self.at_stop(60, need_new=False)
            n0 = len(self.stops); self.go(s)
            _, st = self.watch(n0, 120)
            assert st, 'no line while going forward'
            if compare: self.compare(tag + '+%d' % (j + 1), st['id'], self.shot())
        return st

    def back_to_line(self, k, tag, compare=True):
        """대사·선택지 k 개만큼 뒤로: 한 걸음씩 가며 소리 자막 걸음은 세지 않는다. 마지막 되감기를 돌려준다."""
        b = None; n = 0
        while n < k:
            b = self.back(1, tag, compare=False)
            if b is None: return None
            if b['op'] != 0x42: n += 1
        if compare and b: self.compare(tag, b['id'], self.shot())
        return b

    # ---- 요약
    def summary(self, ok, extra=None):
        self.pump()
        backs = self.backs
        def stat(key, sel=None):
            v = [b[key] for b in backs if (sel is None or sel(b)) and b[key] >= 0]
            v.sort()
            return dict(n=len(v), min=v[0], med=v[len(v) // 2], p90=v[int(len(v) * 0.9) - 1 if len(v) > 1 else 0], max=v[-1]) if v else None
        summ = dict(stops_first=len(self.order), backs=len(backs), visual_ms=stat('visual'), total_ms=stat('total'), wake_ms=stat('wake'), voice_ms=stat('voice'), sound_ms=stat('sound'),
                    script_ms=stat('script'), rebuild_ms=stat('rebuild'), paint_ms=stat('paint'),
                    total_ms_same_bgm=stat('total', lambda b: b['bgm'][0] == b['bgm'][1]), total_ms_bgm_change=stat('total', lambda b: b['bgm'][0] != b['bgm'][1]),
                    kept_layers=stat('kept'),
                    verify_same=sum(1 for v in self.verifies if v['same']), verify_diff=[v for v in self.verifies if not v['same']][:20],
                    compared=len([c for c in self.cmp if c['n'] is not None]), pixel_diff_count=len([c for c in self.cmp if c['n']]),
                    pixel_diffs=[c for c in self.cmp if c['n']][:40], refused=self.refused, cleared=self.cleared, notes=self.notes, ok=ok,
                    same_on_second_try=self.recheck, partial_captures=getattr(self.g, 'partial_shots', 0), capture_retries=getattr(self.g, 'shot_retries', 0))
        if extra: summ.update(extra)
        json.dump(dict(summary=summ, backs=backs, compare=self.cmp), open(os.path.join(self.out, 'result.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        open(os.path.join(self.out, 'rewind_events.log'), 'w', encoding='utf-8').write('\n'.join(self.events))
        open(os.path.join(self.out, 'other_events.log'), 'w', encoding='utf-8').write('\n'.join(self.other))
        self.L('SUMMARY', json.dumps(summ, ensure_ascii=False))
        return summ

    def finish(self, ok):
        g = self.g
        q = g.quit() if g.alive() and g.h else False
        self.L('normal quit', q, 'ok', ok)
        g.close()
        return q

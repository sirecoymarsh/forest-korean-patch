# -*- coding: utf-8 -*-
"""이야기의 지도 시안 — model.json 배치를 게임 UI 재료로 그린다(PIL, 2배로 그려 줄임).

상태는 실제 기록에서 읽는다: rssave.dat 의 읽음 비트(누적) + 이번 회차(시안에선 가정).
게임 안 렌더러(native/chart_ui.cpp)와 같은 규칙을 쓴다:
  금빛 = 이번 회차(지금 자리·지나온 길), ✓ = 끝까지 읽음/고른 적 있음, 흐림 = 아직.
  닿지 않은 장·선택은 이름·문구·행선지를 가린다(？？？).
"""
import json, os, sys, struct, math
from PIL import Image, ImageDraw, ImageFont

ROOT = r'P:\AI\forest-flowchart-claude'
A = os.path.join(ROOT, 'assets')
M = json.load(open(os.path.join(ROOT, 'data', 'model.json'), encoding='utf-8'))
BAND = json.load(open(os.path.join(A, 'band.json')))
S = 2

FONT_SB = os.path.join(A, 'fonts', 'ForestChartSerif-SemiBold.ttf')
FONT_BK = os.path.join(A, 'fonts', 'ForestChartSerif-Black.ttf')
_fc = {}


def font(size, black=False):
    k = (round(size * 2) / 2, black)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FONT_BK if black else FONT_SB, max(6, int(k[0] * S)))
    return _fc[k]


INK = (58, 35, 15, 255)
INK_DIM = (128, 108, 76, 255)
INK_SOFT = (96, 70, 40, 255)
GOLD = (255, 206, 72, 255)
GOLD_TXT = (255, 246, 102, 255)
CREAM = (222, 204, 152, 215)
FAINT = (150, 140, 118, 150)
RUST = (226, 104, 60, 255)
WHITE = (252, 248, 232, 255)
LEAF_EDGE = (20, 42, 12, 255)
GOLD_EDGE = (70, 40, 0, 255)

_img = {}


def asset(name):
    if name not in _img:
        _img[name] = Image.open(os.path.join(A, name)).convert('RGBA')
    return _img[name]


CH = {c['id']: c for c in M['chapters']}
PAGE = {p['chapter']: p for p in M['pages']}


# ------------------------------------------------------------------ 상태
def load_readbits(path):
    sv = open(path, 'rb').read()
    n = len(sv)
    best = None
    for s0 in range(0x90, n - 6):
        p = s0; out = {}; ok = True
        while p < n:
            if p + 6 > n:
                ok = False; break
            sid, ln = struct.unpack_from('<HI', sv, p)
            if not (1 <= sid <= 9999) or ln > 4000:
                ok = False; break
            out['%04d' % sid] = sv[p + 6:p + 6 + ln]
            p += 6 + ln
        if ok and p == n and (best is None or len(out) > len(best)):
            best = out
    return best or {}


class State:
    """bits: 누적 읽음, current: {'scene','choice','after':[cid,idx]}, run: [(cid, idx)…]"""

    def __init__(self, bits, current=None, run=None, run_scenes=None, show_all=False):
        self.bits = bits
        self.current = current or {}
        self.run = run or []
        self.run_pick = {c: i for c, i in self.run}
        self.run_scenes = set(run_scenes or [])
        self.all = show_all
        self._infer()

    def _infer(self):
        """직접 증거 + 확실한 거꾸로 추론(뒤 선택에 닿았고 그리로 가는 길이 하나뿐이면 그 길을 지났다)."""
        self.reached = set()
        self.chosen = set()
        for cid, c in M['choices'].items():
            if cid in self.run_pick or self.current.get('choice') == cid:
                self.reached.add(cid)
            if any(self.read(w[0], w[1]) for w in c.get('pre', []) + c.get('reach', [])):
                self.reached.add(cid)
            for o in c['options']:
                if self.run_pick.get(cid) == o['idx'] or any(self.read(w[0], w[1]) for w in o['witness']):
                    self.chosen.add((cid, o['idx'])); self.reached.add(cid)
        changed = True
        while changed:
            changed = False
            for cid in list(self.reached):
                preds = [p for p in M['choices'][cid].get('preds', []) if p[0] != cid]
                if len(preds) == 1:
                    pc, pi = preds[0]
                    if (pc, pi) not in self.chosen:
                        self.chosen.add((pc, pi)); changed = True
                    if pc not in self.reached:
                        self.reached.add(pc); changed = True

    def read(self, sid, slot):
        b = self.bits.get(sid)
        return bool(b) and slot < len(b) * 8 and (b[slot >> 3] >> (slot & 7)) & 1

    def scene_frac(self, sid):
        s = M['scenes'][sid]
        return sum(1 for x in s['slots'] if self.read(sid, x)) / len(s['slots']) if s['slots'] else 0.0

    def scene_seen(self, sid):
        return self.all or self.scene_frac(sid) > 0 or sid in self.run_scenes or self.current.get('scene') == sid

    def scene_done(self, sid):
        return any(self.read(sid, x) for x in M['scenes'][sid]['exit_slots'])

    def opt_chosen(self, cid, o):
        return (cid, o['idx']) in self.chosen

    def choice_seen(self, cid):
        return self.all or cid in self.reached

    def chapter_seen(self, ch):
        return self.all or any(self.scene_seen(s) for s in ch['scenes'])

    def cur_chapter(self):
        sid = self.current.get('scene')
        return M['scenes'][sid]['chapter'] if sid else None


# ------------------------------------------------------------------ 그리기 도구
def paste(canvas, im, x, y, w, h):
    if w < 1 or h < 1:
        return
    canvas.alpha_composite(im.resize((max(1, int(w * S)), max(1, int(h * S))), Image.LANCZOS), (int(x * S), int(y * S)))


def text_fit(d, xy, box_w, s, size, fill, black=False, anchor='lm', stroke=0, stroke_fill=None, min_size=7):
    sz = size
    while sz > min_size and d.textlength(s, font=font(sz, black)) > box_w * S:
        sz -= 0.5
    d.text((xy[0] * S, xy[1] * S), s, font=font(sz, black), fill=fill, anchor=anchor,
           stroke_width=int(round(stroke * S)), stroke_fill=stroke_fill)


def glow_text(d, xy, s, size, anchor='mm'):
    d.text((xy[0] * S, xy[1] * S), s, font=font(size, True), fill=GOLD_TXT, anchor=anchor,
           stroke_width=int(1.7 * S), stroke_fill=GOLD_EDGE)


def check(d, x, y, size, color, width=2.2):
    pts = [(x, y + size * 0.55), (x + size * 0.38, y + size * 0.92), (x + size, y + size * 0.05)]
    d.line([(p[0] * S, p[1] * S) for p in pts], fill=color, width=max(1, int(width * S)), joint='curve')


def bezier(p0, p1, p2, p3, n=28):
    out = []
    for i in range(n + 1):
        t = i / n
        a = (1 - t) ** 3; b = 3 * (1 - t) ** 2 * t; c = 3 * (1 - t) * t * t; e = t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + e * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + e * p3[1]))
    return out


def poly(d, pts, color, width, dash=None):
    P = [(x * S, y * S) for x, y in pts]
    wd = max(1, int(width * S))
    if not dash:
        d.line(P, fill=color, width=wd, joint='curve')
        return
    on, off = dash[0] * S, dash[1] * S
    pos = 0.0; draw_on = True; cur = [P[0]]
    for i in range(1, len(P)):
        x0, y0 = P[i - 1]; x1, y1 = P[i]
        L = math.hypot(x1 - x0, y1 - y0)
        t = 0.0
        while L - t > 0:
            lim = on if draw_on else off
            step = min(lim - pos, L - t)
            t += step; pos += step
            px, py = x0 + (x1 - x0) * t / L, y0 + (y1 - y0) * t / L
            if draw_on:
                cur.append((px, py))
            if pos >= lim - 1e-6:
                if draw_on and len(cur) > 1:
                    d.line(cur, fill=color, width=wd)
                draw_on = not draw_on; pos = 0.0; cur = [(px, py)]
    if draw_on and len(cur) > 1:
        d.line(cur, fill=color, width=wd)


def arrow_head(d, tip, frm, color, size=7):
    ang = math.atan2(tip[1] - frm[1], tip[0] - frm[0])
    pts = [tip, (tip[0] - size * math.cos(ang - 0.42), tip[1] - size * math.sin(ang - 0.42)),
           (tip[0] - size * math.cos(ang + 0.42), tip[1] - size * math.sin(ang + 0.42))]
    d.polygon([(x * S, y * S) for x, y in pts], fill=color)


def pin(d, layer, x, y, z, below=False):
    """지금 자리: 금빛 점 + 「지금 여기」."""
    r = 6 * max(z, .8)
    paste(layer, asset('glow_gold.png'), x - 26, y - 18, 52, 36)
    d.ellipse(((x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S), fill=GOLD, outline=GOLD_EDGE, width=int(1.5 * S))
    glow_text(d, (x, y + (17 if below else -15) * max(z, .8)), '지금 여기', 12 * max(z, .85))


# ------------------------------------------------------------------ 틀·머리·발
def frame_base():
    return asset('frame_bg.png').resize((800 * S, 600 * S), Image.LANCZOS)


def frame_top(canvas):
    canvas.alpha_composite(asset('frame_fg.png').resize((800 * S, 600 * S), Image.LANCZOS))


def oval_button(canvas, d, cx, cy, label, size=14, hover=False):
    f = font(size, True)
    w = d.textlength(label, font=f) / S + 24
    paste(canvas, asset('oval_green.png' if hover else 'oval_brown.png'), cx - w / 2 - 7, cy - 17, w + 14, 34)
    d.text((cx * S + S, cy * S + 2 * S), label, font=f, fill=(38, 27, 5, 210), anchor='mm', stroke_width=S, stroke_fill=(38, 27, 5, 210))
    d.text((cx * S, cy * S), label, font=f, fill=GOLD_TXT, anchor='mm', stroke_width=S, stroke_fill=(64, 39, 5, 255))
    return w


def chrome(canvas, st, viewing, info=None, hover=None):
    d = ImageDraw.Draw(canvas)
    xs = 284
    items = [('전체', None)] + [(c['id'], c) for c in M['chapters']]
    cur_ch = st.cur_chapter()
    for label, ch in items:
        f = font(14.5 if label == '전체' else 18, True)
        w = d.textlength(label, font=f) / S + 21
        cx, cy = xs + w / 2, 35
        sel = viewing == label
        seen = ch is None or st.chapter_seen(ch)
        if sel:
            paste(canvas, asset('oval_brown.png'), cx - w / 2 - 9, cy - 19, w + 18, 38)
            d.text((cx * S + S, cy * S + 2 * S), label, font=f, fill=(38, 27, 5, 220), anchor='mm', stroke_width=S, stroke_fill=(38, 27, 5, 220))
            d.text((cx * S, cy * S), label, font=f, fill=GOLD_TXT, anchor='mm', stroke_width=S, stroke_fill=(64, 39, 5, 255))
        else:
            d.text((cx * S, cy * S), label, font=f, fill=INK if seen else (172, 148, 104, 255), anchor='mm')
        if ch is not None and ch['id'] == cur_ch:
            d.ellipse(((cx - 3.5) * S, (cy + 15) * S, (cx + 3.5) * S, (cy + 22) * S), fill=(222, 156, 18, 255), outline=(110, 62, 0, 255))
        xs += w
    if viewing and viewing != '전체':
        ch = CH[viewing]
        title = ch['title'] if st.chapter_seen(ch) else '？？？'
        text_fit(d, (289, 74), 490, title, 21, INK, black=True)
    else:
        text_fit(d, (289, 74), 490, '전체 지도', 21, INK, black=True)
    d.text((26 * S, 556 * S), '이야기의 지도', font=font(27, True), fill=INK, anchor='lm')
    if info:
        lines = info if isinstance(info, list) else [info]
        for i, ln in enumerate(lines[:2]):
            text_fit(d, (236, 543 + i * 21 - (10 if len(lines) == 1 else 0)), 300, ln, 13, INK_SOFT)
    bx = 552
    for label in ['다시 가리기' if st.all else '가린 것 보기', '지금 자리', '닫기']:
        f = font(14, True)
        w = d.textlength(label, font=f) / S + 24
        oval_button(canvas, d, bx + w / 2, 556, label, hover=(hover == label))
        bx += w + 5


# ------------------------------------------------------------------ 장 쪽
def chapter_page(chid, st, view=None, info=None, focus=None, hover=None):
    page = PAGE[chid]
    ch = CH[chid]
    canvas = frame_base()
    W, H = page['size']
    bx0, by0, bx1, by1 = 0, BAND['inner'][1] + 4, 800, BAND['inner'][3] - 4
    bw, bh = bx1 - bx0 - 50, by1 - by0 - 40
    if view is None:
        f = min(bw / W, bh / H)
        if f >= 0.82:
            z = min(f, 1.1)
            ox = bx0 + (bx1 - bx0 - W * z) / 2; oy = by0 + (by1 - by0 - H * z) / 2
        else:
            z = 0.92
            fx, fy = focus or (0, H / 2)
            ox = bx0 + 30 - fx * z if fx * z < bw * 0.5 else bx0 + (bx1 - bx0) / 2 - fx * z
            ox = min(bx0 + 30, max(ox, bx1 - 30 - W * z))
            oy = by0 + (by1 - by0) / 2 - fy * z
            oy = min(by0 + 24, max(oy, by1 - 24 - H * z)) if H * z > bh else by0 + (by1 - by0 - H * z) / 2
    else:
        z, ox, oy = view
    layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    def T(x, y):
        return ox + x * z, oy + y * z

    strip = page['strip']
    order = page['order']
    cur_scene = st.current.get('scene')
    lw_ = max(z, .65)
    # 이야기 차례 선
    for a_, b_ in zip(order, order[1:]):
        ra, rb = strip[a_], strip[b_]
        run = a_ in st.run_scenes and (b_ in st.run_scenes or b_ == cur_scene)
        seen = st.scene_seen(a_) and st.scene_seen(b_)
        if abs(ra[1] - rb[1]) < 1:
            l, r = (ra, rb) if ra[0] < rb[0] else (rb, ra)
            pts = [T(l[0] + l[2], l[1] + l[3] / 2), T(r[0], r[1] + r[3] / 2)]
        else:
            pa = T(ra[0] + ra[2] / 2, ra[1] + ra[3]); pb = T(rb[0] + rb[2] / 2, rb[1])
            pts = bezier(pa, (pa[0], pa[1] + 26 * z), (pb[0], pb[1] - 26 * z), pb)
        poly(d, pts, GOLD if run else (CREAM if seen else FAINT), (4.0 if run else 2.2) * lw_, dash=None if seen else (5, 5))
    # 명판
    for sid in order:
        r = strip[sid]
        x, y = T(r[0], r[1]); w, h = r[2] * z, r[3] * z
        seen = st.scene_seen(sid)
        is_cur = sid == cur_scene and not st.current.get('choice') and not st.current.get('after')
        if sid == cur_scene:
            paste(layer, asset('glow_gold.png'), x - 22 * z, y - 20 * z, w + 44 * z, h + 40 * z)
        paste(layer, asset('plate_lit.png' if seen else 'plate_dim.png'), x, y, w, h)
        title = M['scenes'][sid]['title'] if seen else '？？？'
        done = seen and st.scene_done(sid)
        tx = x + (27 if done else 14) * z
        text_fit(d, (tx, y + h / 2 + 1 * z), w - (40 if done else 27) * z, title, 14 * z, INK if seen else INK_DIM, black=True)
        if done:
            check(d, x + 10 * z, y + h / 2 - 7 * z, 12.5 * z, INK, 2.4 * z)
        elif seen and not st.all:
            fr = st.scene_frac(sid)
            if 0 < fr < 1:
                poly(d, [(x + 14 * z, y + h - 8.5 * z), (x + 14 * z + (w - 28 * z) * fr, y + h - 8.5 * z)], (125, 76, 26, 235), 2.2 * z)
        if is_cur:
            pin(d, layer, x + w / 2, y - 2 * z, z)
    # 선택 묶음
    for cl in page['clusters']:
        sc = cl['scene']
        r = strip[sc]
        first = min(cl['pos'], key=lambda c: (cl['pos'][c][0], cl['pos'][c][1]))
        fp = cl['pos'][first]
        if cl['anchor'] == 'right':
            pa = T(r[0] + r[2], r[1] + r[3] / 2)
        else:
            pa = T(r[0] + 34, r[1] + r[3])
        pb = T(fp[0], fp[1] + M['sizes']['q_h'] / 2)
        seen = st.choice_seen(first)
        run = first in st.run_pick or st.current.get('choice') == first
        if cl['anchor'] == 'right':
            pts = bezier(pa, (pa[0] + 30 * z, pa[1]), (pb[0] - 30 * z, pb[1]), pb)
        else:
            pts = bezier(pa, (pa[0], pb[1]), (pb[0] - 30 * z, pb[1]), pb)
        poly(d, pts, GOLD if run else (CREAM if seen else FAINT), (3.8 if run else 2.2) * lw_, dash=None if seen else (5, 5))
        for cid, p in cl['pos'].items():
            draw_choice(layer, d, cid, p, T, z, st, cl, hover)
    canvas.alpha_composite(layer)
    frame_top(canvas)
    chrome(canvas, st, chid, info)
    return canvas.resize((800, 600), Image.LANCZOS)


def draw_choice(layer, d, cid, p, T, z, st, cl, hover=None):
    c = M['choices'][cid]
    sz = M['sizes']
    x, y = T(p[0], p[1]); w = p[2] * z
    reached = st.choice_seen(cid)
    qh = sz['q_h'] * z; lh = sz['l_h'] * z
    lw_ = max(z, .65)
    if st.current.get('choice') == cid:
        paste(layer, asset('glow_gold.png'), x - 22 * z, y - 22 * z, w + 44 * z, p[3] * z + 44 * z)
    paste(layer, asset('q_lit.png' if reached else 'q_dim.png'), x, y, w, qh)
    q = c['question'] or '……'
    text_fit(d, (x + 15 * z, y + qh / 2 + 1 * z), w - 30 * z, q if reached else '？？？', 13 * z, INK if reached else INK_DIM, black=True)
    if st.current.get('choice') == cid:
        pin(d, layer, x + w - 26 * z, y - 2 * z, z)
    pick = st.run_pick.get(cid)
    after = st.current.get('after')
    for i, o in enumerate(c['options']):
        ly = y + qh + 3 * z + i * lh
        lx = x + 10 * z
        lw = w - 10 * z
        chosen = st.opt_chosen(cid, o)
        this_run = pick == o['idx']
        is_hover = hover == (cid, o['idx'])
        if this_run:
            paste(layer, asset('glow_gold.png'), lx - 14 * z, ly - 9 * z, lw + 28 * z, lh + 18 * z)
        elif is_hover:
            paste(layer, asset('glow_green.png'), lx - 14 * z, ly - 9 * z, lw + 28 * z, lh + 18 * z)
        leaf = 'leaf_hi.png' if (this_run or is_hover) else ('leaf_lit.png' if (chosen or st.all) else 'leaf_dim.png')
        paste(layer, asset(leaf), lx, ly + 1 * z, lw, lh - 2 * z)
        label = o['label'] if reached else '？？？'
        if this_run:
            col, edge = GOLD_TXT, GOLD_EDGE
        elif chosen or st.all:
            col, edge = WHITE, LEAF_EDGE
        else:
            col, edge = (196, 202, 178, 255), (18, 30, 12, 255)
        tx = lx + (25 if (chosen and not this_run) else 13) * z
        text_fit(d, (tx, ly + lh / 2), lw * 0.68, label, 12.5 * z, col, black=True, stroke=1.5 * z, stroke_fill=edge)
        if chosen and not this_run:
            check(d, lx + 9 * z, ly + lh / 2 - 5.5 * z, 10.5 * z, (255, 248, 206, 255), 2.2 * z)
        if not (st.all or chosen):
            continue
        ex, ey = lx + lw - 2 * z, ly + lh / 2
        tags = []
        cur_here = after and after[0] == cid and after[1] == o['idx']
        for oc in o['outs']:
            k = oc['k']
            if k in ('choice', 'back') and oc['node'] in cl['pos']:
                tp = cl['pos'][oc['node']]
                tx2, ty2 = T(tp[0], tp[1] + sz['q_h'] / 2)
                dest_seen = st.choice_seen(oc['node'])
                gold = this_run and (oc['node'] in st.run_pick or st.current.get('choice') == oc['node'])
                if tx2 > ex + 4:
                    pts = bezier((ex, ey), (ex + 44 * z, ey), (tx2 - 44 * z, ty2), (tx2 - 2, ty2))
                else:   # 되돌아가는 간선: 아래로 돌아 앞 칸으로
                    lowest = max(T(0, q[1] + q[3])[1] for q in cl['pos'].values())
                    yy = lowest + 18 * z
                    pts = bezier((ex, ey), (ex + 50 * z, ey), (ex + 50 * z, yy), ((ex + tx2) / 2, yy)) + \
                        bezier(((ex + tx2) / 2, yy), (tx2 - 50 * z, yy), (tx2 - 50 * z, ty2), (tx2 - 2, ty2))[1:]
                if cur_here and not dest_seen:
                    # 이번 회차가 이 간선 위에 있다: 반쯤 금빛, 나머지는 점선
                    half = max(2, int(len(pts) * 0.22))
                    poly(d, pts[:half + 1], GOLD, 3.8 * lw_)
                    poly(d, pts[half:], CREAM, 2.0 * lw_, dash=(5, 5))
                    pin(d, layer, pts[half][0], pts[half][1], z, below=True)
                elif not dest_seen and not st.all:
                    poly(d, pts, CREAM, 2.0 * lw_, dash=(5, 5))
                else:
                    col2 = GOLD if gold else CREAM
                    poly(d, pts, col2, (3.8 if gold else 2.1) * lw_, dash=(7, 5) if k == 'back' else None)
                    arrow_head(d, (tx2, ty2), pts[-3], col2, 8 * lw_)
            elif k == 'end':
                tags.append(('이어짐', CREAM))
            elif k == 'restart':
                tags.append(('다시 시작', RUST))
            elif k == 'stop':
                tags.append(('이야기 끝', RUST))
        tx3 = ex + 8 * z
        for t, colr in dict.fromkeys(tags):
            f = font(11.5 * max(z, .8), True)
            d.text((tx3 * S, ey * S), t, font=f, fill=colr, anchor='lm', stroke_width=int(1.4 * S), stroke_fill=(16, 16, 12, 255))
            tx3 += d.textlength(t, font=f) / S + 8
        if cur_here and not any(oc['k'] in ('choice', 'back') for oc in o['outs']):
            pin(d, layer, tx3 + 14 * z, ey, z)


# ------------------------------------------------------------------ 전체 지도
def overview(st, info=None, hover=None):
    canvas = frame_base()
    layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    PW, PH = 214, 68
    xs = [44, 293, 542]
    ys = [140, 263, 386]
    pos = {}
    order = [(0, 0), (0, 1), (0, 2), (1, 2), (1, 1), (1, 0), (2, 0), (2, 1), (2, 2)]
    for i, ch in enumerate(M['chapters']):
        r, k = order[i]
        pos[ch['id']] = (xs[k], ys[r])
    cur_ch = st.cur_chapter()
    ids = [c['id'] for c in M['chapters']]
    run_chs = set(M['scenes'][s]['chapter'] for s in st.run_scenes)
    for a_, b_ in zip(ids, ids[1:]):
        (xa, ya), (xb, yb) = pos[a_], pos[b_]
        seen = st.chapter_seen(CH[a_]) and st.chapter_seen(CH[b_])
        run = a_ in run_chs and (b_ in run_chs or b_ == cur_ch)
        if ya == yb:
            l, r = ((xa, ya), (xb, yb)) if xa < xb else ((xb, yb), (xa, ya))
            pts = [(l[0] + PW, l[1] + PH / 2), (r[0], r[1] + PH / 2)]
        else:
            pa = (xa + PW / 2, ya + PH); pb = (xb + PW / 2, yb)
            pts = bezier(pa, (pa[0], pa[1] + 30), (pb[0], pb[1] - 30), pb)
        poly(d, pts, GOLD if run else (CREAM if seen else FAINT), 4.4 if run else 2.6, dash=None if seen else (6, 6))
    for ch in M['chapters']:
        x, y = pos[ch['id']]
        seen = st.chapter_seen(ch)
        if ch['id'] == cur_ch:
            paste(layer, asset('glow_gold.png'), x - 24, y - 22, PW + 48, PH + 44)
        elif hover == ch['id']:
            paste(layer, asset('glow_green.png'), x - 22, y - 20, PW + 44, PH + 40)
        paste(layer, asset('plate_lit.png' if seen else 'plate_dim.png'), x, y, PW, PH)
        d.text(((x + 22) * S, (y + 26) * S), ch['id'], font=font(20, True), fill=INK if seen else INK_DIM, anchor='lm')
        nx = x + 22 + d.textlength(ch['id'], font=font(20, True)) / S + 10
        title = ch['title'] if seen else '？？？'
        text_fit(d, (nx, y + 27), x + PW - 36 - nx, title, 15.5, INK if seen else INK_DIM, black=True)
        if seen:
            sc = [s for s in ch['scenes'] if s in M['scenes']]
            done = sum(1 for s in sc if st.scene_done(s))
            nch = sum(len(M['scenes'][s]['choices']) for s in sc)
            seen_ch = sum(1 for s in sc for c in M['scenes'][s]['choices'] if st.choice_seen(c))
            txt = f'이야기 {done}/{len(sc)}' + (f'  ·  선택 {seen_ch}/{nch}' if nch else '')
            d.text(((x + 24) * S, (y + 50) * S), txt, font=font(12), fill=INK_SOFT, anchor='lm')
            if done == len(sc) and seen_ch == nch:
                check(d, x + PW - 31, y + 17, 15, INK, 2.6)
        if ch['id'] == cur_ch:
            glow_text(d, (x + PW / 2, y - 11), '지금 여기', 12.5)
    canvas.alpha_composite(layer)
    frame_top(canvas)
    chrome(canvas, st, '전체', info)
    return canvas.resize((800, 600), Image.LANCZOS)


if __name__ == '__main__':
    bits = load_readbits(r'P:\AI\forest-kr-build\game\save\rssave.dat')
    run_scenes = CH['I']['scenes'] + CH['II']['scenes'] + ['3061', '3062', '3063', '2300']
    st = State(bits, current={'scene': '2300', 'after': ['2300@0x0018DA', 2]},
               run=[('2300@0x0018DA', 2)], run_scenes=run_scenes)
    out = os.path.join(ROOT, 'out')
    overview(st, ['장을 누르면 그 장의 이야기 차례와 갈림길이 펼쳐집니다.', '금빛은 이번 회차, ✓ 는 끝까지 읽은 이야기입니다.']).save(os.path.join(out, 'mock_overview.png'))
    pg = PAGE['III']
    fx = pg['clusters'][0]['pos']['2300@0x0018DA']
    chapter_page('III', st, info=['「당신은──」에서 이번에는 「밖으로」를 골랐습니다.', '「안으로」도 고른 적이 있습니다(✓).'],
                 focus=(fx[0] + 120, fx[1] + 40)).save(os.path.join(out, 'mock_III.png'))
    chapter_page('I', st, info='선택지에 마우스를 올리면 그 갈래가 어디로 이어졌는지 여기 나옵니다.', hover=('2100@0x000148', 1)).save(os.path.join(out, 'mock_I.png'))
    chapter_page('II', st).save(os.path.join(out, 'mock_II.png'))
    print('ok')

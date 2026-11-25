# -*- coding: utf-8 -*-
"""시안 시트: 4배 1:1 잘라 보기. 열 = 지금(1배를 늘림) / AI 그대로 / 섞기(기본) / 섞기 진하게."""
import sys, os, json, numpy as np, cv2
sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
from blend4 import blend, alpha4
from PIL import Image, ImageDraw, ImageFont
SRC = r'Y:\AI\forest-4k\src'; AI = r'Y:\AI\forest-4k\sample_ai'
F = ImageFont.truetype(r'C:\Windows\Fonts\malgun.ttf', 26); FS = ImageFont.truetype(r'C:\Windows\Fonts\malgun.ttf', 20)
CW, CH = 480, 360   # 4배 잘라 보기 크기(1배 120×90)
BG = (58, 58, 58)

def load(item):
    arc, n = item.split('/')
    im = cv2.imread(os.path.join(SRC, arc, n + '.png'), cv2.IMREAD_UNCHANGED)
    a1 = im[:, :, 3] if im.shape[2] == 4 else None
    if a1 is not None and (a1 == 255).all(): a1 = None
    rgb = np.ascontiguousarray(im[:, :, :3])
    ai = cv2.imread(os.path.join(AI, arc, n + '.png'), cv2.IMREAD_COLOR)
    return rgb, a1, ai

def compose(rgb4, a4):
    if a4 is None: return rgb4
    a = a4.astype(np.float32)[:, :, None] / 255
    return (rgb4.astype(np.float32) * a + np.array(BG[::-1], np.float32) * (1 - a) + 0.5).astype(np.uint8)

def picks(rgb, a1, n=2):
    h, w = rgb.shape[:2]
    if a1 is not None:   # 인물: 머리(위쪽 보이는 부분)
        ys, xs = np.nonzero(a1 > 128)
        top = ys.min(); sel = ys < top + 90
        cx = int(xs[sel].mean()); cy = top + 45
        return [(cx, cy)]
    g = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY).astype(np.float32)
    e = cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    d = cv2.blur(e, (120, 90))
    m = np.zeros_like(d); m[45:h - 45, 60:w - 60] = 1; d = d * m - (1 - m) * 1e9
    y, x = np.unravel_index(np.argmax(d), d.shape); out = [(x, y)]
    if n > 1:   # 부드러운 곳: 결이 낮지만 평평하지는 않은 곳(아래 25% 분위)
        v = d.copy(); v[v < 0] = np.inf
        q = np.nanpercentile(v[np.isfinite(v)], 20)
        cand = np.argwhere(np.abs(v - q) < q * 0.15)
        cand = [c for c in cand if abs(c[1] - x) > 140 or abs(c[0] - y) > 110]
        if cand: y2, x2 = cand[len(cand) // 2]; out.append((x2, y2))
    return out

def crops(item, centers=None):
    rgb, a1, ai = load(item)
    h, w = rgb.shape[:2]
    a4 = alpha4(a1) if a1 is not None else None
    now = cv2.resize(rgb, (w * 4, h * 4), interpolation=cv2.INTER_LINEAR)   # 지금 화면 = 1배 이중선형 늘림
    if a1 is not None: now_a = cv2.resize(a1, (w * 4, h * 4), interpolation=cv2.INTER_LINEAR)
    b1, k1 = blend(rgb, ai, 40, 120)
    b2, k2 = blend(rgb, ai, 20, 80)
    cols = [compose(now, now_a if a1 is not None else None), compose(ai, a4), compose(b1, a4), compose(b2, a4)]
    rows = []
    for cx, cy in (centers or picks(rgb, a1)):
        x0 = int(np.clip(cx * 4 - CW // 2, 0, w * 4 - CW)); y0 = int(np.clip(cy * 4 - CH // 2, 0, h * 4 - CH))
        rows.append([c[y0:y0 + CH, x0:x0 + CW] for c in cols])
    return rows, (k1, k2)

def build(items, out, title):
    allrows = []
    for it in items:
        name = it if isinstance(it, str) else it[0]
        rows, ks = crops(name, None if isinstance(it, str) else it[1])
        for r in rows: allrows.append((name, r, ks))
    pad = 8; lab = 40; head = 92
    W = 4 * (CW + pad) + pad; H = head + len(allrows) * (CH + lab + pad)
    sheet = Image.new('RGB', (W, H), (24, 24, 24)); d = ImageDraw.Draw(sheet)
    d.text((pad, 6), title, font=F, fill=(240, 240, 240))
    hdr = ['지금 화면(1배를 늘림)', 'AI 그대로(high-fidelity)', '섞기(레콘키스타 기본)', '섞기 진하게(AI 더 많이)']
    for i, t in enumerate(hdr): d.text((pad + i * (CW + pad), 50), t, font=F, fill=(255, 220, 140))
    y = head
    for name, r, ks in allrows:
        d.text((pad, y + 6), f'{name}   (4배 1:1, 1배 120×90 칸)   섞기 AI 비율 기본 {ks[0]*100:.0f}% · 진하게 {ks[1]*100:.0f}%', font=FS, fill=(200, 200, 200))
        for i, c in enumerate(r):
            sheet.paste(Image.fromarray(c[:, :, ::-1]), (pad + i * (CW + pad), y + lab))
        y += CH + lab + pad
    sheet.save(out, optimize=True)
    print(out, sheet.size)

if __name__ == '__main__':
    OUT = r'Y:\AI\forest-4k\sheets'; os.makedirs(OUT, exist_ok=True)
    build(['grpe/1803', 'grpe/4040', 'grpe/4010', 'grpo_bg/4302'], os.path.join(OUT, 'sample_scenes.png'), 'Forest 4배 시안 ① 배경·CG (I·II장 그림)')
    build(['grpo_bu/0021', 'grpo_bu/0011', ('grpo_f/0401', [(170, 215)]), ('grpo_f/0502', [(235, 240)]), ('grpo_ci/1202', [(400, 300)])], os.path.join(OUT, 'sample_people.png'), 'Forest 4배 시안 ② 인물·효과 (I·II장 그림)')

# -*- coding: utf-8 -*-
"""이야기의 지도 그림 재료.

전부 게임의 한국어판 UI 그림에서 만든다(세이브 화면 틀, 장 제목 명판, 질문 띠, 잎사귀).
  frame_bg.png  800x600  양피지 띠 + 어둡게 가라앉힌 담쟁이 벽(검은 칸·「저장」 지움)
  frame_fg.png  800x600  양피지 띠만(담쟁이 자리는 투명) — 차트가 찢긴 종이 밑으로 들어간다
  band.json     담쟁이 띠의 열별 위/아래 경계
  plate_*.png   장면 명판(빈 양피지), q_*.png 질문 띠, leaf_*.png 잎사귀, glow_*.png 빛
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageEnhance
import cv2

ROOT = r'P:\AI\forest-flowchart-claude'
REF = os.path.join(ROOT, 'ref', 'ko')
JA = r'C:\Users\CADRIA~1\AppData\Local\Temp\claude\P--AI\7923c8e2-4614-4129-823b-30c38b62b3f1\scratchpad\ui_png'
OUT = os.path.join(ROOT, 'assets')
os.makedirs(OUT, exist_ok=True)


def lum(a):
    return a[..., 0] * 0.3 + a[..., 1] * 0.59 + a[..., 2] * 0.11


# ------------------------------------------------------------------ 틀
src = Image.open(os.path.join(REF, 'save_visible.png')).convert('RGB')
a = np.asarray(src).astype(np.float32)
L = lum(a)
H, W = L.shape
top = np.zeros(W, int)
bot = np.zeros(W, int)
for x in range(W):
    y = 92
    while y < 300 and L[y, x] >= 90:
        y += 1
    top[x] = y
    y = top[x] + 60
    while y < H - 9 and not (L[y:y + 8, x] >= 110).all():
        y += 1
    while y > top[x] + 60 and L[y - 1, x] >= 90:
        y -= 1
    bot[x] = y

band = np.zeros((H, W), bool)
for x in range(W):
    band[top[x]:bot[x], x] = True

# 검은 칸(세이브 슬롯)이 박힌 담쟁이 벽을 새로 짠다:
# 칸이 없는 왼쪽 가장자리(열 4~100)의 결을 좌우로 번갈아 뒤집어 이어 붙인다.
# 같은 높이대의 깨끗한 조각(왼쪽 0~100, 오른쪽 690~800 열)을 무작위로 골라 겹쳐 짠다.
rng = np.random.default_rng(7)
P, STEP = 72, 40
acc = np.zeros_like(a)
wsum = np.zeros(a.shape[:2], np.float32)
win1 = np.hanning(P + 2)[1:-1].astype(np.float32)
win = np.outer(win1, win1) + 1e-3
srcx = list(range(0, 100 - P + 1, 4)) + list(range(690, W - P + 1, 4))
for ty in range(80, 540, STEP):
    for tx in range(-P // 2, W, STEP):
        sx = int(rng.choice(srcx))
        sy = int(np.clip(ty + rng.integers(-10, 11), 0, H - P))
        patch = a[sy:sy + P, sx:sx + P]
        if rng.random() < 0.5:
            patch = patch[:, ::-1]
        y0, x0 = ty, tx
        ys0, xs0 = max(0, -y0), max(0, -x0)
        y1, x1 = min(H, y0 + P), min(W, x0 + P)
        if y1 <= max(0, y0) or x1 <= max(0, x0):
            continue
        pp = patch[ys0:ys0 + (y1 - max(0, y0)), xs0:xs0 + (x1 - max(0, x0))]
        ww = win[ys0:ys0 + (y1 - max(0, y0)), xs0:xs0 + (x1 - max(0, x0))]
        acc[max(0, y0):y1, max(0, x0):x1] += pp * ww[..., None]
        wsum[max(0, y0):y1, max(0, x0):x1] += ww
woven = acc / np.maximum(wsum, 1e-3)[..., None]
a2 = np.where(band[..., None], woven, a)

# 담쟁이 벽을 가라앉힌다(글자·선이 또렷하게)
blur = cv2.GaussianBlur(a2, (0, 0), 1.2)
dark = (a2 * 0.45 + blur * 0.55) * 0.62
# 가운데를 조금 더 어둡게(가장자리 빛 번짐 느낌)
yy, xx = np.mgrid[0:H, 0:W]
vign = 1.0 - 0.18 * (((xx - W / 2) / (W / 2)) ** 2)
dark *= vign[..., None]
bm = band[..., None].astype(np.float32)
bm = cv2.GaussianBlur(bm[..., 0], (0, 0), 0.7)[..., None]
a3 = a2 * (1 - bm) + dark * bm

# 아래 띠의 「저장」 글자와 오른쪽 검은 단추 자리 지우기 — 깨끗한 양피지를 옮겨 온다
def patch(dst_box, dx):
    x0, y0, x1, y1 = dst_box
    a3[y0:y1, x0:x1] = a3[y0:y1, x0 + dx:x1 + dx]

img8 = np.clip(a3, 0, 255).astype(np.uint8)
for x0, x1, dx in [(10, 136, 170), (546, 790, -250)]:
    y0 = int(max(bot[x0:x1].max(), bot[x0 + dx:x1 + dx].max())) + 2
    y1 = 600
    srcp = img8[y0:y1, x0 + dx:x1 + dx].copy()
    mask = np.full(srcp.shape[:2], 255, np.uint8)
    mask[:2, :] = 0; mask[-2:, :] = 0; mask[:, :2] = 0; mask[:, -2:] = 0
    center = ((x0 + x1) // 2, (y0 + y1) // 2)
    img8 = cv2.seamlessClone(srcp, img8, mask, center, cv2.NORMAL_CLONE)
img8[596:600, :] = img8[595:596, :]
a3 = img8.astype(np.float32)

bg = Image.fromarray(np.clip(a3, 0, 255).astype(np.uint8), 'RGB')
bg.save(os.path.join(OUT, 'frame_bg.png'))

# 앞판: 양피지만(경계는 밝기로 부드럽게)
alpha = np.zeros((H, W), np.float32)
for x in range(W):
    alpha[:top[x], x] = 1
    alpha[bot[x]:, x] = 1
edge = np.clip((L - 45) / 75.0, 0, 1)
near = cv2.dilate((np.abs(np.diff(alpha, axis=0, prepend=alpha[:1])) > 0).astype(np.uint8), np.ones((5, 3), np.uint8)) > 0
alpha = np.where(near, np.maximum(alpha * 0.0 + edge, 0), alpha)
alpha = np.where(band & ~near, 0, alpha)
fg = np.dstack([np.clip(a3, 0, 255), alpha * 255]).astype(np.uint8)
Image.fromarray(fg, 'RGBA').save(os.path.join(OUT, 'frame_fg.png'))
json.dump({'top': top.tolist(), 'bot': bot.tolist(),
           'inner': [0, int(top.max()), W, int(bot.min())],
           'outer': [0, int(top.min()), W, int(bot.max())]},
          open(os.path.join(OUT, 'band.json'), 'w'))
print('band top', top.min(), top.max(), 'bot', bot.min(), bot.max())

# ------------------------------------------------------------------ 장면 명판(빈 양피지)
dt = Image.open(os.path.join(REF, 'dt1_0001.png')).convert('RGBA')
d = np.asarray(dt).astype(np.float32)
Ld = lum(d)
inner = np.zeros(Ld.shape, bool)
inner[9:53, 10:247] = True
txt = inner & (Ld < 150) & (d[..., 3] > 200)
txt = cv2.dilate(txt.astype(np.uint8), np.ones((5, 5), np.uint8))
rgb = cv2.inpaint(np.clip(d[..., :3], 0, 255).astype(np.uint8), txt, 6, cv2.INPAINT_TELEA)
plate = np.dstack([rgb, d[..., 3].astype(np.uint8)])
plate = Image.fromarray(plate, 'RGBA').filter(ImageFilter.SMOOTH)
plate.save(os.path.join(OUT, 'plate_lit.png'))


def dim(im, k=0.42, sat=0.35):
    rgb = im.convert('RGB')
    rgb = ImageEnhance.Color(rgb).enhance(sat)
    rgb = ImageEnhance.Brightness(rgb).enhance(k)
    out = rgb.convert('RGBA')
    out.putalpha(im.getchannel('A'))
    return out

dim(plate).save(os.path.join(OUT, 'plate_dim.png'))

# ------------------------------------------------------------------ 질문 띠
q = Image.open(os.path.join(JA, 'grps_sel_q00', 'body.png')).convert('RGBA')
q.save(os.path.join(OUT, 'q_lit.png'))
dim(q).save(os.path.join(OUT, 'q_dim.png'))

# ------------------------------------------------------------------ 잎사귀
leaf = Image.open(os.path.join(JA, 'grps_sel_a00', 'body.png')).convert('RGBA')
leaf_f = Image.open(os.path.join(JA, 'grps_sel_a00', 'body_f.png')).convert('RGBA')
leaf.save(os.path.join(OUT, 'leaf_lit.png'))
leaf_f.save(os.path.join(OUT, 'leaf_hi.png'))
dim(leaf, 0.40, 0.25).save(os.path.join(OUT, 'leaf_dim.png'))

# ------------------------------------------------------------------ 빛(금빛=이번 회차, 초록=고른 칸)
def glow(w, h, color, rad, inset, a=255):
    im = Image.new('RGBA', (w, h), color + (0,))
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((inset, inset, w - inset, h - inset), radius=rad, fill=a)
    m = m.filter(ImageFilter.GaussianBlur(inset / 2.2))
    im.putalpha(m)
    return im

glow(220, 90, (255, 214, 92), 18, 22).save(os.path.join(OUT, 'glow_gold.png'))
glow(220, 90, (120, 255, 90), 18, 22, 200).save(os.path.join(OUT, 'glow_green.png'))

# 단추 밑 타원(타이틀 단추와 같은 갈색/초록 번짐)
def oval(w, h, color, a):
    im = Image.new('RGBA', (w, h), color + (0,))
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).ellipse((8, 8, w - 8, h - 8), fill=a)
    m = m.filter(ImageFilter.GaussianBlur(5))
    im.putalpha(m)
    return im

oval(160, 40, (92, 52, 6), 235).save(os.path.join(OUT, 'oval_brown.png'))
oval(160, 40, (70, 230, 20), 235).save(os.path.join(OUT, 'oval_green.png'))
print('assets ok')

# -*- coding: utf-8 -*-
"""「뒤로」 단추(4730·4740) — 원작 빛무리(둥근 막대, 맞춘 값 glow_fit.json)를 새로 그리고, 코덱스와 같은 설정으로 「뒤로」를 얹는다."""
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
B = 'Y:/AI/claude-work/forest-music-titles/back'
FONT = 'C:/Windows/Fonts/NotoSerifKR-VF.ttf'
H, W, SS = 26, 56, 4
fit = json.load(open(f'{B}/glow_fit.json'))
RIM = {'4730': (94, 57, 0), '4740': (65, 230, 0)}
INNER = {'4730': (83.5, 51.5, 0), '4740': (57.5, 204.5, 0)}


def stadium(cx, cy, hx, hy, sig):
    gy, gx = np.mgrid[0:H * SS, 0:W * SS]
    x = (gx + 0.5) / SS - cx; y = (gy + 0.5) / SS - cy
    ex = np.maximum(np.abs(x) - (hx - hy), 0)
    inside = (ex ** 2 + y ** 2) <= hy ** 2
    im = Image.fromarray((inside * 255).astype(np.uint8)).resize((W, H), Image.BOX).filter(ImageFilter.GaussianBlur(sig))
    return np.array(im).astype(float)


for n in ('4730', '4740'):
    p = fit[n]
    al = stadium(p['cx'], p['cy'], p['hx'], p['hy'], p['sig'])
    t = (1 - al / 255.0)[..., None]
    rgb = np.array(INNER[n])[None, None, :] * (1 - t) + np.array(RIM[n])[None, None, :] * t
    blank = Image.fromarray(np.dstack([np.clip(rgb + 0.5, 0, 255), np.clip(al + 0.5, 0, 255)]).astype(np.uint8), 'RGBA')
    blank.save(f'{B}/glow_{n}.png')
    canvas = blank.copy()
    f = ImageFont.truetype(FONT, 18); f.set_variation_by_name('Bold')
    d = ImageDraw.Draw(canvas); pos = (10, -2)
    d.text((pos[0] + 1, pos[1] + 2), '뒤로', font=f, fill=(38, 27, 5, 220), stroke_width=1, stroke_fill=(38, 27, 5, 220))
    d.text(pos, '뒤로', font=f, fill=(255, 246, 102, 255), stroke_width=1, stroke_fill=(64, 39, 5, 255))
    canvas.save(f'{B}/new_{n}.patch.png')
    src = Image.open(f'{B}/ja_{n}.png').convert('RGBA')
    diff = (np.array(canvas) != np.array(src)).any(2)
    Image.fromarray((diff * 255).astype(np.uint8)).convert('RGB').save(f'{B}/new_{n}.mask.png')
    print(n, 'changed px', int(diff.sum()))

rows = []
for n in ('4730', '4740'):
    rows += [Image.open(f'{B}/ja_{n}.png'), Image.open(f'{B}/glow_{n}.png'), Image.open(f'{B}/ko_{n}.png'), Image.open(f'{B}/new_{n}.patch.png')]
sc = 6; w, h = W * sc, H * sc
sheet = Image.new('RGBA', (4 * (w + 10) + 10, 2 * (h + 10) + 10), (30, 30, 40, 255))
for i, im in enumerate(rows):
    big = im.convert('RGBA').resize((w, h), Image.NEAREST)
    bg = Image.new('RGBA', (w, h), (25, 15, 5, 255)); bg.alpha_composite(big)
    sheet.alpha_composite(bg, (10 + (i % 4) * (w + 10), 10 + (i // 4) * (h + 10)))
sheet.convert('RGB').save(f'{B}/new_sheet.png')

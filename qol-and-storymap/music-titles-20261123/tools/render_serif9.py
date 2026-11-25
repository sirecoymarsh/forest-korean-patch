# -*- coding: utf-8 -*-
"""음악 감상 목록 최종(11-23 밤 사용자 「폰트를 게임에 어울리는걸로」): 본명조 Black(NotoSerifKR-VF 900) 20px.
바탕은 render_ko.py 가 만든 원작 바탕(ko_s21_800/blank_3400·3500), 배치·색은 지금과 같다."""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
B = 'Y:/AI/claude-work/forest-music-titles'
sys.path.insert(0, B)
from render_ko import TITLES, INK
OUT = f'{B}/ko_serif9'
os.makedirs(OUT, exist_ok=True)
f = ImageFont.truetype('C:/Windows/Fonts/NotoSerifKR-VF.ttf', 20); f.set_variation_by_axes([900])
for base in (3400, 3500):
    bg = np.array(Image.open(f'{B}/ko_s21_800/blank_{base}.png').convert('RGB'))
    for k in range(1, 15):
        im = Image.fromarray(bg).convert('RGBA')
        layer = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
        num, title = f'{k}.', TITLES[k - 1]
        x = 15 if k < 10 else 13
        gb = f.getbbox('가'); y = (4 + 23) / 2 - (gb[1] + gb[3]) / 2
        d.text((x, y), num, font=f, fill=INK + (255,))
        nx = x + f.getlength(num) + max(5, f.size * 0.35)
        d.text((nx, y), title, font=f, fill=INK + (255,))
        im.alpha_composite(layer)
        out = im.convert('RGBA')
        out.save(f'{OUT}/{base + k}.patch.png')
        ja = np.array(Image.open(f'{B}/ja/{base + k}.png').convert('RGBA'))
        m = (np.array(out) != ja).any(2)
        Image.fromarray((m * 255).astype(np.uint8)).convert('RGB').save(f'{OUT}/{base + k}.mask.png')
print('rendered 28')

# -*- coding: utf-8 -*-
"""음악 감상 목록 글꼴 시안: 후보마다 14줄을 그려 실제 화면(배경 4006 + 단추)에 합성해 나란히 본다."""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
B = 'Y:/AI/claude-work/forest-music-titles'
sys.path.insert(0, B)
from render_ko import TITLES, INK
CAND = [
    ('now',    '지금: 본고딕 800',          'C:/Windows/Fonts/NotoSansKR-VF.ttf', 800),
    ('serif6', '본명조 SemiBold(이야기 지도 글꼴)', 'C:/Windows/Fonts/NotoSerifKR-VF.ttf', 600),
    ('serif9', '본명조 Black',              'C:/Windows/Fonts/NotoSerifKR-VF.ttf', 900),
    ('maru',   '마루 부리 SemiBold',        'P:/AI/Codex/projects/nights-of-azure-2-gemini-scenario-kit-2026-08-29/builds/github_release_2026-09-26_RC11_launcher1.0.7/res/MaruBuri-SemiBold.ttf', None),
    ('jua',    '주아',                      'P:/AI/Codex/projects/touka-ui-polish/source/fonts/Jua-Regular.ttf', None),
    ('gowun',  '고운돋움',                  'P:/AI/Codex/projects/ookamikakushi-pc-native/data/fonts/GowunDodum-Regular.ttf', None),
]
POS = {int(k): v for k, v in json.load(open(f'{B}/bar_pos.json')).items()}


def font(path, size, w):
    f = ImageFont.truetype(path, size)
    if w is not None: f.set_variation_by_axes([w])
    return f


def ink_h(f):
    b = f.getbbox('가'); return b[3] - b[1]


TARGET = ink_h(font(CAND[0][2], 21, 800))     # 지금 글자와 같은 한글 높이


def fit(path, w):
    for s in range(12, 40):
        if ink_h(font(path, s, w)) >= TARGET: return s
    return 21


def bar(bg, k, f):
    im = Image.fromarray(bg).convert('RGBA')
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    num, title = f'{k}.', TITLES[k - 1]
    x = 15 if k < 10 else 13
    gb = f.getbbox('가'); y = (4 + 23) / 2 - (gb[1] + gb[3]) / 2
    d.text((x, y), num, font=f, fill=INK + (255,))
    nx = x + f.getlength(num) + max(5, f.size * 0.35)
    d.text((nx, y), title, font=f, fill=INK + (255,))
    right = d.textbbox((nx, y), title, font=f)[2]
    im.alpha_composite(layer)
    return im.convert('RGB'), right


def screen(bars):
    bg = Image.open(f'{B}/bg/ko_4006.png').convert('RGBA')
    for n, im in bars.items():
        bg.alpha_composite(im.convert('RGBA'), tuple(POS[n]))
    for p, xy in ((f'{B}/back/ja_4770.png', (335, 539)), (f'{B}/back/ja_4771.png', (418, 539)), (f'{B}/back/new_4730.patch.png', (707, 539))):
        bg.alpha_composite(Image.open(p).convert('RGBA'), xy)
    return bg.convert('RGB')


blank = np.array(Image.open(f'{B}/ko_s21_800/blank_3400.png').convert('RGB'))
os.makedirs(f'{B}/trials', exist_ok=True)
info = {}
for key, label, path, w in CAND:
    s = 21 if key == 'now' else fit(path, w)
    f = font(path, s, w)
    bars, rmax = {}, 0
    for k in range(1, 15):
        im, r = bar(blank, k, f); bars[3400 + k] = im; rmax = max(rmax, r)
    sc = screen(bars); sc.save(f'{B}/trials/screen_{key}.png')
    info[key] = dict(label=label, size=s, right=round(rmax, 1))
    print(key, label, 'size', s, 'max right', round(rmax, 1))
json.dump(info, open(f'{B}/trials/info.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# 비교표: 후보마다 화면의 목록 부분(1배, x 20~780, y 95~515)을 1.5배로, 2열
LF = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 26)
crop = (20, 95, 780, 515); z = 1.0
cw, ch = int((crop[2] - crop[0]) * z), int((crop[3] - crop[1]) * z)
cols, rows = 2, (len(CAND) + 1) // 2
sheet = Image.new('RGB', (cols * (cw + 20) + 20, rows * (ch + 56) + 20), (34, 34, 46))
dd = ImageDraw.Draw(sheet)
for i, (key, label, _, _) in enumerate(CAND):
    c, r = i % cols, i // cols
    x, y = 20 + c * (cw + 20), 20 + r * (ch + 56)
    dd.text((x, y), f'{chr(65 + i)}. {label}', font=LF, fill=(250, 220, 150))
    im = Image.open(f'{B}/trials/screen_{key}.png').crop(crop).resize((cw, ch), Image.LANCZOS)
    sheet.paste(im, (x, y + 36))
sheet.save(f'{B}/trials/compare_screen.png'); print(sheet.size)

# 가까이: 3·9·13·14번 막대를 3배로(부드럽게 늘림 — 큰 창에서 보이는 꼴)
picks = [3, 5, 9, 14]
bw, bh = 214 * 3, 28 * 3
sheet2 = Image.new('RGB', (len(picks) * (bw + 12) + 300, len(CAND) * (bh + 10) + 20), (34, 34, 46))
d2 = ImageDraw.Draw(sheet2)
for r, (key, label, _, _) in enumerate(CAND):
    y = 10 + r * (bh + 10)
    d2.text((10, y + bh // 2 - 14), f'{chr(65 + r)}. {label}', font=ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 20), fill=(250, 220, 150))
    scr = Image.open(f'{B}/trials/screen_{key}.png')
    for c, k in enumerate(picks):
        x0, y0 = POS[3400 + k]
        b = scr.crop((x0, y0, x0 + 214, y0 + 28)).resize((bw, bh), Image.BICUBIC)
        sheet2.paste(b, (300 + c * (bw + 12), y))
sheet2.save(f'{B}/trials/compare_close.png'); print(sheet2.size)

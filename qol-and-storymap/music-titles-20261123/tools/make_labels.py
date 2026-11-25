# -*- coding: utf-8 -*-
"""특전 세 화면 배경(grpe 4004 CG·4005 장면·4006 음악)의 영어 라벨을 한국어로. 1배(게임 wcg용)와 4K(hiart jpg)를 같은 배치로 그린다.
바탕은 라벨 둘레가 완전히 고른 색(1배 28,17,5 / 4K 27,17,5)이라 라벨 칸을 그 색으로 메우고 흰 글자를 얹는다.
"""
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
B = 'Y:/AI/claude-work/forest-music-titles/bg'
HI = 'P:/AI/forest-kr-build/game/hiart/grpe'
FONT = 'C:/Windows/Fonts/NotoSerifKR-VF.ttf'
LABEL = {4004: 'CG 감상', 4005: '장면 감상', 4006: '음악 감상'}
BOX = (15, 528, 310, 582)          # 지울 칸(1배): 원작·영문 라벨이 모두 이 안(x 24~292, y 534~573)
X0, YC, GH = 26, 553.5, 35         # 글자 왼쪽, 세로 가운데, 한글 높이(원작 한자 높이 37~39 보다 조금 작게)
WEIGHT = 900


def font(size):
    f = ImageFont.truetype(FONT, size); f.set_variation_by_axes([WEIGHT]); return f


def fit_size(scale):
    # 「감」 의 높이가 GH*scale 가 되는 크기
    for s in range(20 * scale, 80 * scale):
        b = font(s).getbbox('감')
        if b[3] - b[1] >= GH * scale: return s
    return 40 * scale


S1 = 40   # 원작 한자 라벨 높이(39px)에 맞춤: 35 에서 잉크 34px 였다


def draw(im, text, scale, bg):
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = (v * scale for v in BOX)
    d.rectangle((x0, y0, x1 - 1, y1 - 1), fill=bg)
    s = S1 * scale; f = font(s)
    gb = font(S1).getbbox('감')
    y = (YC - (gb[1] + gb[3]) / 2) * scale
    d.text((X0 * scale, y), text, font=f, fill=(255, 255, 255))
    return s, d.textbbox((X0 * scale, y), text, font=f)


out = {}
for n, text in LABEL.items():
    one = Image.open(f'{B}/en_{n}.png').convert('RGB')
    s1, bb1 = draw(one, text, 1, (28, 17, 5))
    one.save(f'{B}/ko_{n}.png')
    four = Image.open(f'{HI}/{n}.jpg').convert('RGB')
    s4, bb4 = draw(four, text, 4, (27, 17, 5))
    four.save(f'{B}/ko_{n}_4x.jpg', quality=95, subsampling=0)
    # 4배를 1배로 줄여 1배와 비교(라벨 칸)
    small = np.array(four.resize((800, 600), Image.BOX)).astype(int)[BOX[1]:BOX[3], BOX[0]:BOX[2]]
    o1 = np.array(one).astype(int)[BOX[1]:BOX[3], BOX[0]:BOX[2]]
    out[n] = dict(text=text, size1=s1, bbox1=[round(v, 1) for v in bb1], size4=s4, mad_4to1=round(float(np.abs(small - o1).mean()), 2))
    print(n, out[n])
json.dump(out, open(f'{B}/labels.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
# 보기
sheet = Image.new('RGB', (860, 3 * 2 * 70 + 20), (40, 40, 50)); y = 10
for n in LABEL:
    for p in (f'{B}/en_{n}.png', f'{B}/ko_{n}.png'):
        sheet.paste(Image.open(p).convert('RGB').crop((0, 520, 420, 590)).resize((840, 140)).crop((0, 0, 840, 60)) if False else Image.open(p).convert('RGB').crop((0, 520, 420, 590)), (10, y)); y += 70
four = Image.open(f'{B}/ko_4006_4x.jpg').crop((0, 520 * 4, 420 * 4, 590 * 4)).resize((420, 70), Image.LANCZOS)
sheet.paste(four, (440, 10 + 5 * 70))
sheet.save(f'{B}/labels_ko.png')

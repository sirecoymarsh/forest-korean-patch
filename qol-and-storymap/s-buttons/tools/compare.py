# -*- coding: utf-8 -*-
"""원래 줄 / 새 줄(평소·지도에 마우스·자동에 마우스)을 게임 캡처에서 잘라 4배로 나란히.
  python -I compare.py ORIG.png NEW.png NEW_HOVER_MAP.png NEW_HOVER_AUTO.png OUT.png"""
import sys
from PIL import Image, ImageDraw, ImageFont

orig, new, hmap, hauto, out = sys.argv[1:6]
BOX = (590, 562, 800, 600)          # 오른쪽 아래: 대기 표시 ▼ + 아이콘 줄
K = 4
rows = [('원래 줄', orig), ('새 줄 — 평소', new), ('새 줄 — 지도에 마우스', hmap), ('새 줄 — 자동에 마우스', hauto)]
font = ImageFont.truetype(r'C:\Windows\Fonts\malgunbd.ttf', 18)
small = ImageFont.truetype(r'C:\Windows\Fonts\malgun.ttf', 14)
bw, bh = (BOX[2] - BOX[0]) * K, (BOX[3] - BOX[1]) * K
real_w = BOX[2] - BOX[0] + 40
pad = 18
W = pad * 3 + bw + real_w
H = pad + len(rows) * (bh + 34) + pad
sheet = Image.new('RGB', (W, H), (24, 24, 22))
d = ImageDraw.Draw(sheet)
for i, (label, path) in enumerate(rows):
    im = Image.open(path).convert('RGB')
    y0 = pad + i * (bh + 34)
    d.text((pad, y0), label, font=font, fill=(240, 232, 210))
    crop = im.crop(BOX)
    sheet.paste(crop.resize((bw, bh), Image.NEAREST), (pad, y0 + 28))
    one = im.crop((BOX[0] - 40, BOX[1], BOX[2], BOX[3]))
    sheet.paste(one, (pad * 2 + bw, y0 + 28))
d.text((pad * 2 + bw, pad), '실제 크기', font=small, fill=(200, 192, 170))
sheet.save(out)
print('saved', out, sheet.size)

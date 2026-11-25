# -*- coding: utf-8 -*-
"""하단 아이콘 줄(grps\\compane.lwg) 시안: 지금 / 밝힌 판 + 「이야기의 지도」 아이콘.

엔진(Forest.exe 0x40fab1~0x40fb37)은 compane 에서 rev·next·bak·fow·hide·voc·auto·menu 여덟 단추를
이름으로 만든다. Forest 그림엔 auto·menu 층이 없어 두 칸이 비어 있다(콜백은 게임이 0x414de2 에서 걸어 둠).

  python tools\\compane_mock.py <캡처.png> <출력.png>
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PILOT = r'P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest\work\forest-en-korean-pilot'
sys.path.insert(0, os.path.join(PILOT, 'adapter'))
from lwg_container import parse_lwg  # noqa: E402

SRC = os.path.join(ROOT, 'ref', 'sys')
NORMAL = ['bg', 'slide', 'rev', 'bak', 'fow', 'next', 'voc', 'hide']
IVORY = (236, 230, 212)
GREEN = (0, 254, 80)


def layers():
    L = parse_lwg(open(os.path.join(SRC, 'compane.lwg'), 'rb').read())
    out = {}
    for e in L.entries:
        im = Image.open(os.path.join(SRC, 'compane', e.name + '.png')).convert('RGBA')
        out[e.name] = [e.x, e.y, im]
    return out


def brighten(im, gain=2.2, fill_gain=2.0):
    """모양은 그대로, 평소 색만 상아색·진하게. 안쪽 반투명 채움(알파 26)은 어둡게 두어 밝은 배경에서도 선이 서게."""
    a = np.array(im).astype(float)
    al = a[..., 3]
    lum = a[..., :3].mean(-1)
    line = lum > 40                               # 선(밝은 픽셀) / 안쪽 채움(검정)
    out = a.copy()
    out[line, 0], out[line, 1], out[line, 2] = IVORY
    out[line, 3] = np.minimum(235, al[line] * gain)
    out[~line, 3] = np.minimum(90, al[~line] * fill_gain)
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def map_icon(hover=False):
    """14×14 갈림길: 아래 줄기에서 두 갈래로 나뉘고 끝마다 마디. 8배로 그려 줄인다(기존 아이콘처럼 부드러운 가장자리)."""
    S = 8
    big = Image.new('RGBA', (14 * S, 14 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    col = GREEN if hover else IVORY
    lw = int(1.15 * S)
    fill = (GREEN + (150,)) if hover else (0, 0, 0, 60)
    def node(cx, cy, r):
        d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=fill, outline=col + (255,), width=lw)
    # 줄기 → 가지
    d.line([(7.0 * S, 11.0 * S), (7.0 * S, 7.6 * S)], fill=col + (255,), width=lw)
    d.line([(7.0 * S, 7.8 * S), (3.0 * S, 4.4 * S)], fill=col + (255,), width=lw)
    d.line([(7.0 * S, 7.8 * S), (11.0 * S, 4.4 * S)], fill=col + (255,), width=lw)
    node(7.0, 11.6, 1.9)
    node(2.6, 2.9, 1.9)
    node(11.4, 2.9, 1.9)
    small = big.resize((14, 14), Image.LANCZOS)
    a = np.array(small).astype(float)
    a[..., 3] *= (0.80 if hover else 0.85)
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


def strip(L, proposal, hover_map=False, hover=None, thumb=None):
    """compane 194×18 그림. proposal 이면 밝힌 판 + 지도 아이콘(⇑ 왼쪽 17px 칸, 슬라이더 12px 줄임).
    thumb: 슬라이더 손잡이 x(엔진이 값에 따라 옮긴다)."""
    c = Image.new('RGBA', (194, 18), (0, 0, 0, 0))
    for n in NORMAL:
        x, y, im = L[n]
        if n == 'slide' and thumb is not None:
            x = thumb
        if hover == n:
            im = L[n + '_f'][2]
        elif proposal:
            im = brighten(im)
        if proposal and n == 'bg':
            im = im.crop((0, 0, im.width - 12, im.height))
        c.alpha_composite(im, (x, y))
    if proposal:
        c.alpha_composite(map_icon(hover_map), (71, 2))
    return c


def main(cap, out):
    L = layers()
    shot = Image.open(cap).convert('RGBA')
    W, H = shot.size
    # 캡처에서 줄 위치 찾기(지금 판 알파로 상관)
    g = np.array(shot.convert('L')).astype(float)
    m = np.array(strip(L, False))[..., 3].astype(float); m -= m.mean()
    best = None
    for y in range(H - 60, H - 17):
        for x in range(W - 260, W - 193):
            cc = g[y:y + 18, x:x + 194]; cc = cc - cc.mean()
            s = (cc * m).sum() / (np.sqrt((cc * cc).sum() * (m * m).sum()) + 1e-9)
            if best is None or s > best[0]:
                best = (s, x, y)
    _, X, Y = best
    # 슬라이더 손잡이 자리(밝은 세로 막대)
    t = np.array(L['slide'][2])[..., 3].astype(float); t -= t.mean()
    tb = None
    for x in range(3, 75):
        cc = g[Y + 2:Y + 16, X + x:X + x + 4]; cc = cc - cc.mean()
        s = (cc * t).sum() / (np.sqrt((cc * cc).sum() * (t * t).sum()) + 1e-9)
        if tb is None or s > tb[0]:
            tb = (s, x)
    TH = tb[1]
    # 아이콘 자리를 지운 바탕
    mask = np.zeros((H, W), np.uint8)
    cur = np.array(strip(L, False, thumb=TH))[..., 3] > 0
    mask[Y:Y + 18, X:X + 194][cur] = 255
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8))
    bg = cv2.inpaint(np.array(shot.convert('RGB')), mask, 3, cv2.INPAINT_TELEA)
    bg = Image.fromarray(bg).convert('RGBA')

    def scene(proposal, hover_map=False):
        s = bg.copy() if proposal else shot.copy()
        if proposal:
            s.alpha_composite(strip(L, True, hover_map, thumb=min(TH, 62)), (X, Y))
        return s

    now, new, newh = scene(False), scene(True), scene(True, True)
    box = (X - 175, Y - 46, W, H)                   # 오른쪽 아래(대사 끝줄·대기 표시 포함)
    font = ImageFont.truetype(r'C:\Windows\Fonts\malgunbd.ttf', 17)
    small = ImageFont.truetype(r'C:\Windows\Fonts\malgun.ttf', 14)
    k = 3
    cw, ch = (box[2] - box[0]) * k, (box[3] - box[1]) * k
    pad = 18
    one_w = W - (X - 230)
    sheet = Image.new('RGB', (pad * 3 + cw + one_w, pad + 3 * (ch + 40) + pad), (24, 24, 22))
    d = ImageDraw.Draw(sheet)
    rows = [('지금', now), ('제안 — 평소', new), ('제안 — 지도에 마우스', newh)]
    for i, (t, s) in enumerate(rows):
        y0 = pad + i * (ch + 40)
        d.text((pad, y0), t, font=font, fill=(240, 232, 210))
        crop = s.crop(box)
        sheet.paste(crop.resize((cw, ch), Image.NEAREST), (pad, y0 + 26))
        one = s.crop((X - 230, Y - 110, W, H))       # 실제 크기
        sheet.paste(one.convert('RGB'), (pad * 2 + cw, y0 + 26))
    d.text((pad * 2 + cw, pad), '실제 크기', font=small, fill=(200, 192, 170))
    sheet.save(out)
    new.convert('RGB').save(out.replace('.png', '_full.png'))
    print('strip at', X, Y, 'thumb', TH, '->', out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])

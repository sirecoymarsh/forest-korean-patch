# -*- coding: utf-8 -*-
"""Forest 아이콘 줄(grps\\compane.lwg, 194×18) 새 판 만들기.

  python -I make_compane.py            → s-buttons\\compane_new\\(층 PNG + .meta.xml), s-buttons\\out\\compane.lwg,
                                          s-buttons\\out\\icons_sheet.png(8배 대조표)

- 원래 평소 아이콘(rev·bak·fow·next·voc·hide·slide·bg)은 10-10 시안(forest-flowchart-claude\\tools\\compane_mock.py)의
  brighten 그대로 상아색으로 밝힌다. 모양·마우스 올림(_f 초록)은 원래대로.
- voc_off(이 줄에 음성 없음)는 꺼진 단추라 덜 밝힌다(켜진 voc 의 약 절반 알파를 지킴).
- 슬라이더(slide_lev 판정 칸·bg 홈줄)를 34px 줄여 두 칸을 만든다: 지도(menu) x=54, 자동(auto) x=71.
  엔진은 손잡이 위치·값을 slide_lev 폭-손잡이 폭으로 셈한다(0x43b05a·0x43b0ec·0x43b2f1) → 0~255 끝에서 끝까지 그대로.
- 새 아이콘은 원래 아이콘의 선 구조(바깥 밝은 테두리 → 안쪽 회색 → 검정 알파 26 채움, 윗·왼쪽이 밝음)를
  8배로 그려 줄인 뒤 원래 아이콘과 같은 brighten 을 거친다. 마우스 올림은 원래 _f 처럼 초록으로 속까지 채운다.
"""
import os, shutil, struct, subprocess, sys
import numpy as np
import cv2
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)                                   # P:\AI\forest-qol\s-buttons
SRC = os.path.join(os.path.dirname(BASE), 'work', 'compane_png')   # 원래 층(통합 세션이 grps.xfl 에서 꺼냄)
OUT_DIR = os.path.join(BASE, 'compane_new')
OUT = os.path.join(BASE, 'out')
TOOL = r'P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest\work\forest-en-korean-pilot\ui_work\tools\UiAssetTool.exe'

IVORY = (236, 230, 212)
GREEN = (0, 254, 79)
LIGHT_GREEN = (169, 254, 199)    # 원래 _f 의 가장자리 반투명 색(a9fec7)
SHRINK = 34                      # 두 칸(17px 간격 × 2)
MAP_X, AUTO_X = 54, 71
S = 8                            # 크게 그려 줄이는 배율


# ------------------------------------------------------------------ 원래 층 밝히기(10-10 시안과 같은 식)
def brighten(im, gain=2.2, fill_gain=2.0, cap=235, fill_cap=90):
    a = np.array(im.convert('RGBA')).astype(float)
    al = a[..., 3]
    lum = a[..., :3].mean(-1)
    line = (lum > 40) & (al > 0)
    fill = (lum <= 40) & (al > 0)
    out = a.copy()
    out[line, 0], out[line, 1], out[line, 2] = IVORY
    out[line, 3] = np.minimum(cap, al[line] * gain)
    out[fill, 3] = np.minimum(fill_cap, al[fill] * fill_gain)
    return Image.fromarray(out.clip(0, 255).round().astype(np.uint8))


# ------------------------------------------------------------------ 새 아이콘 그리기
def _hires(draw_fn):
    m = Image.new('L', (14 * S, 14 * S), 0)
    draw_fn(ImageDraw.Draw(m))
    return np.array(m).astype(np.float32) / 255.0


def _down(rgba_premul):
    """premultiplied float RGBA(0~1, 크게) → 14×14 RGBA uint8."""
    small = cv2.resize(rgba_premul, (14, 14), interpolation=cv2.INTER_AREA)
    a = small[..., 3:4]
    rgb = np.where(a > 1e-6, small[..., :3] / np.maximum(a, 1e-6), 0)
    out = np.concatenate([rgb, a], -1)
    return (out * 255).clip(0, 255).round().astype(np.uint8)


def render(ink, fill, hover=False):
    """ink: 선(테두리) 덮임 0~1, fill: 안쪽 덮임 0~1 (크게 그린 판).
    평소 = 원래 아이콘의 선 구조, hover = 원래 _f 처럼 초록으로 속까지."""
    solid = np.clip(ink + fill, 0, 1)
    # 밖을 향한 법선으로 빛(왼쪽 위) 받는 정도: 원래 아이콘은 윗·왼 테두리가 알파 ~150, 아래·오른 ~102
    blur = cv2.GaussianBlur(solid, (0, 0), S * 0.9)
    gy, gx = np.gradient(blur)
    n = np.sqrt(gx * gx + gy * gy) + 1e-6
    lit = ((gx / n) + (gy / n)) / np.sqrt(2)        # 안쪽을 향한 기울기 · (1,1)/√2 = 밖 법선 · (-1,-1)/√2
    lit = np.clip(lit, -1, 1)
    # 테두리 안쪽 깊이(px): 바깥 ~0.8px 은 밝은 색, 그 안은 회색(원래 828b85)
    solid8 = (solid > 0.5).astype(np.uint8)
    depth = cv2.distanceTransform(solid8, cv2.DIST_L2, 5) / S
    H = np.zeros(solid.shape + (4,), np.float32)
    if not hover:
        a_ink = (128 + 28 * lit) / 255.0
        white = np.array([0.97, 0.995, 0.975], np.float32)
        gray = np.array([0.51, 0.545, 0.52], np.float32)
        t = np.clip((depth - 0.7) / 0.6, 0, 1)[..., None]
        col_ink = white * (1 - t) + gray * t
        a_ink = a_ink * (1 - 0.35 * t[..., 0])      # 안쪽 회색은 알파도 낮다(원래 86)
        a_fill = 26 / 255.0
        col_fill = np.zeros(3, np.float32)
    else:
        a_ink = (180 + 25 * lit) / 255.0
        col_ink = np.broadcast_to(np.array(GREEN, np.float32) / 255, solid.shape + (3,))
        a_fill = 141 / 255.0
        col_fill = np.array(GREEN, np.float32) / 255
    # 선과 채움을 겹쳐(선이 위) premultiplied 로
    ai = (ink * a_ink)[..., None]
    af = (np.clip(fill - ink, 0, 1) * a_fill)[..., None]
    H[..., :3] = col_ink * ai + col_fill * af * (1 - ai)
    H[..., 3:4] = ai + af * (1 - ai)
    out = _down(H)
    if hover:   # 원래 _f 처럼 덮임이 모자란 가장자리는 옅은 초록
        cov = cv2.resize(solid, (14, 14), interpolation=cv2.INTER_AREA)
        edge = (cov < 0.85) & (out[..., 3] > 0)
        k = (1 - cov[edge])[:, None]
        out[..., :3][edge] = (np.array(GREEN) * (1 - k) + np.array(LIGHT_GREEN) * k).round()
    return Image.fromarray(out)


def auto_masks():
    """▷ 재생 삼각형: 원래 △(bak) 를 오른쪽으로 눕힌 크기(14×14 칸, 꼭짓점 오른쪽 가운데)."""
    pts = [(0.5, 0.5), (13.5, 7.0), (0.5, 13.5)]
    P = [(x * S, y * S) for x, y in pts]
    solid = _hires(lambda d: d.polygon(P, fill=255))
    w = int(round(1.35 * S))
    inner = cv2.erode((solid > 0.5).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * w + 1, 2 * w + 1)))
    inner = cv2.GaussianBlur(inner.astype(np.float32), (0, 0), S * 0.15)
    ink = np.clip(solid - inner, 0, 1)
    fill = np.clip(inner, 0, 1)
    return ink, fill


def map_masks():
    """이야기의 지도 = 갈림길: 아래 마디에서 줄기가 올라가 두 갈래로 나뉘고 끝마다 마디(10-10 시안의 모양)."""
    lw = 1.35
    def lines(d):
        W = int(round(lw * S))
        d.line([(7.0 * S, 10.2 * S), (7.0 * S, 7.6 * S)], fill=255, width=W)
        d.line([(7.0 * S, 7.9 * S), (3.4 * S, 4.6 * S)], fill=255, width=W)
        d.line([(7.0 * S, 7.9 * S), (10.6 * S, 4.6 * S)], fill=255, width=W)
        d.ellipse([(7.0 - 0.6) * S, (7.6 - 0.6) * S, (7.0 + 0.6) * S, (7.6 + 0.6) * S], fill=255)  # 갈림 마디 메움
    nodes = [(7.0, 11.55, 2.0), (2.55, 2.75, 2.0), (11.45, 2.75, 2.0)]
    def rings(d):
        for cx, cy, r in nodes:
            d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=255)
    def holes(d):
        for cx, cy, r in nodes:
            ri = r - lw
            d.ellipse([(cx - ri) * S, (cy - ri) * S, (cx + ri) * S, (cy + ri) * S], fill=255)
    L, R, Hh = _hires(lines), _hires(rings), _hires(holes)
    ink = np.clip(np.maximum(L * (1 - Hh), R - Hh), 0, 1)
    fill = Hh
    return ink, fill


def hit_floor(im):
    """엔진의 단추 판정은 그 층의 알파가 0 이 아닌 화소다(그것도 아래로 2줄 밀려 있다 — 원래 아이콘도 같다).
    원래 아이콘은 속을 알파 26 으로 채워 칸 전체가 눌렸다. 선만 있는 새 아이콘은 빈 틈에서 판정이 끊기므로
    14×14 칸 전체에 알파 1(검정, 눈에 안 보임)을 깐다."""
    a = np.array(im)
    empty = a[..., 3] == 0
    a[empty] = (0, 0, 0, 1)
    return Image.fromarray(a)


# ------------------------------------------------------------------ 줄 짜기
def build():
    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR)
    os.makedirs(OUT, exist_ok=True)
    meta = open(os.path.join(SRC, '.meta.xml'), encoding='utf-8').read()
    layers = {}
    for f in os.listdir(SRC):
        if f.endswith('.png'):
            layers[f[:-4]] = Image.open(os.path.join(SRC, f)).convert('RGBA')

    out = {}
    for name, im in layers.items():
        if name in ('rev', 'bak', 'fow', 'next', 'voc', 'hide', 'slide', 'bg'):
            out[name] = brighten(im)
        elif name == 'voc_off':
            out[name] = brighten(im, gain=1.45, fill_gain=1.0, cap=125, fill_cap=26)
        else:
            out[name] = im                                   # _f(초록)·slide_lev(판정 칸)·레이어 1(바탕 칸)
    # 슬라이더 줄이기
    out['slide_lev'] = layers['slide_lev'].crop((0, 0, layers['slide_lev'].width - SHRINK, layers['slide_lev'].height))
    out['bg'] = out['bg'].crop((0, 0, out['bg'].width - SHRINK, out['bg'].height))
    # 새 단추
    ai, af = auto_masks()
    mi, mf = map_masks()
    raw = {'auto': render(ai, af), 'menu': render(mi, mf)}
    out['auto'] = hit_floor(brighten(raw['auto']))
    out['menu'] = hit_floor(brighten(raw['menu']))
    out['auto_f'] = hit_floor(render(ai, af, hover=True))
    out['menu_f'] = hit_floor(render(mi, mf, hover=True))

    for name, im in out.items():
        im.save(os.path.join(OUT_DIR, name + '.png'))
    # 층 표: 새 단추는 rev 뒤(같은 꼴: 평소 층 다음 _f 층)
    add = ('    <Item x="{a}" y="2" flag="40">auto</Item>\n'
           '    <Item x="{a}" y="2" flag="40">auto_f</Item>\n'
           '    <Item x="{m}" y="2" flag="40">menu</Item>\n'
           '    <Item x="{m}" y="2" flag="40">menu_f</Item>\n').format(a=AUTO_X, m=MAP_X)
    anchor = '    <Item x="173" y="2" flag="40">hide</Item>\n'
    assert anchor in meta
    meta = meta.replace(anchor, add + anchor)
    with open(os.path.join(OUT_DIR, '.meta.xml'), 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(meta.replace('\r\n', '\n'))

    lwg = os.path.join(OUT, 'compane.lwg')
    r = subprocess.run([TOOL, 'lwg-pack-png', OUT_DIR, lwg], capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip())
    if r.returncode:
        sys.exit('pack failed')
    # 표 뒤 4바이트 = 그림 자료 길이(원래 파일이 그렇다; 도구는 0 을 쓴다) — 원래 꼴로 맞춘다
    d = bytearray(open(lwg, 'rb').read())
    te = 24 + struct.unpack_from('<i', d, 20)[0]
    struct.pack_into('<I', d, te, len(d) - te - 4)
    open(lwg, 'wb').write(d)
    return out, raw, layers


def sheet(out, raw, layers):
    """8배 대조표: 원래(그대로) / 원래(밝힘) / 새 아이콘 원 구조 / 밝힘 / 마우스 올림."""
    k = 8
    rows = [
        ('orig', [layers[n] for n in ('rev', 'bak', 'fow', 'next', 'hide')] + [None, None]),
        ('bright', [out[n] for n in ('rev', 'bak', 'fow', 'next', 'hide')] + [out['menu'], out['auto']]),
        ('raw new', [None] * 5 + [raw['menu'], raw['auto']]),
        ('hover', [layers[n + '_f'] for n in ('rev', 'bak', 'fow', 'next', 'hide')] + [out['menu_f'], out['auto_f']]),
    ]
    cw = 14 * k + 12
    W = 12 + cw * 7
    Hh = 12 + len(rows) * (14 * k + 12)
    bg = Image.new('RGBA', (W, Hh), (52, 56, 54, 255))
    for ri, (_, ims) in enumerate(rows):
        for ci, im in enumerate(ims):
            if im is None:
                continue
            big = im.resize((im.width * k, im.height * k), Image.NEAREST)
            bg.alpha_composite(big, (12 + ci * cw, 12 + ri * (14 * k + 12)))
    bg.convert('RGB').save(os.path.join(OUT, 'icons_sheet.png'))


if __name__ == '__main__':
    o, r, l = build()
    sheet(o, r, l)
    print('ok', OUT)

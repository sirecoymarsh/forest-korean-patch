# -*- coding: utf-8 -*-
"""4K 글자 시험 캡처·비교 도우미.
cap(name): 창 캡처(물리) + 엔진 앞 판(800×600, 메모리) 을 같이 저장하고,
           「1배를 늘린 것」(앞 판을 같은 쌍선형으로 늘림)과 캡처를 위아래로 붙인 비교 그림을 만든다.
"""
import os, sys, struct, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ftest
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = os.environ.get('HCAP_OUT', r'Y:\AI\claude-work\hitext\run')
os.makedirs(OUT, exist_ok=True)
_m = None


def mem():
    global _m
    if _m is None:
        _m = ftest.Mem()
    return _m


def front():
    m = mem()
    eng = m.u32(0x466398); f = m.u32(eng + 0x9c); vb = m.u32(f); sub = f + struct.unpack('<i', m.read(vb + 4, 4))[0]
    bits = m.u32(sub + 8)
    raw = m.read(bits, 800 * 600 * 4)
    a = np.frombuffer(raw, np.uint8).reshape(600, 800, 4)
    return a[:, :, 2::-1].copy()   # RGB


def stretch(a, cw, ch):
    """시험 화면 판과 같은 쌍선형(화소 가운데 맞춤)."""
    h, w, _ = a.shape
    ys = (np.arange(ch) + 0.5) * h / ch - 0.5
    xs = (np.arange(cw) + 0.5) * w / cw - 0.5
    y0 = np.floor(ys).astype(int); fy = ys - y0; y1 = np.clip(y0 + 1, 0, h - 1); fy[y0 < 0] = 0; y0 = np.clip(y0, 0, h - 1)
    x0 = np.floor(xs).astype(int); fx = xs - x0; x1 = np.clip(x0 + 1, 0, w - 1); fx[x0 < 0] = 0; x0 = np.clip(x0, 0, w - 1)
    a = a.astype(np.float32)
    top = a[y0][:, x0] * (1 - fx)[None, :, None] + a[y0][:, x1] * fx[None, :, None]
    bot = a[y1][:, x0] * (1 - fx)[None, :, None] + a[y1][:, x1] * fx[None, :, None]
    return np.clip(top * (1 - fy)[:, None, None] + bot * fy[:, None, None] + 0.5, 0, 255).astype(np.uint8)


def label(im, text):
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype(r'C:\Windows\Fonts\malgun.ttf', 22)
    except Exception:
        f = None
    d.rectangle((0, 0, 8 + 13 * len(text), 32), fill=(255, 255, 255))
    d.text((6, 3), text, fill=(0, 0, 0), font=f)
    return im


def cap(name, crop=(160, 470, 690, 560), note=''):
    """crop: 800×600 좌표의 비교할 자리."""
    h = ftest.main_window()
    ftest.act(h)
    shot = ftest.shot(os.path.join(OUT, name + '_win.png'))
    F = front()
    Image.fromarray(F).save(os.path.join(OUT, name + '_engine1x.png'))
    W, H = shot.size
    k = W / 800.0
    up = stretch(F, W, H)
    x0, y0, x1, y1 = [int(round(v * k)) for v in crop]
    a = Image.fromarray(up[y0:y1, x0:x1]); b = shot.crop((x0, y0, x1, y1))
    pair = Image.new('RGB', (x1 - x0, (y1 - y0) * 2 + 8), (255, 0, 255))
    pair.paste(a, (0, 0)); pair.paste(b, (0, y1 - y0 + 8))
    label(pair, '1배를 늘린 것(위) / 4K 글자(아래) ' + note)
    pair.save(os.path.join(OUT, name + '_pair.png'))
    # 수치: 캡처를 800×600 으로 상자 평균해 엔진 1배와 비교(글자 자리·색이 맞는지), 늘린 1배와의 차이
    s = np.asarray(shot.convert('RGB'), np.float32)
    kk = int(round(k))
    if abs(k - kk) < 1e-6:
        small = s.reshape(600, kk, 800, kk, 3).mean(axis=(1, 3))
        reg = (slice(crop[1], crop[3]), slice(crop[0], crop[2]))
        mad = np.abs(small[reg] - F[reg].astype(np.float32)).mean()
        mx = np.abs(small[reg] - F[reg].astype(np.float32)).max()
    else:
        mad = mx = -1
    return {'name': name, 'mad_down_vs_engine': round(float(mad), 2), 'max': round(float(mx), 1)}


_snaps = []


def snap(name, note=''):
    """찍히는 중처럼 빠른 장면: 창 그림과 앞 판만 메모리에 담고 나중에 flush 로 비교 그림을 만든다."""
    h = ftest.main_window()
    im = ftest.shot(None, h)
    _snaps.append((name, im.copy(), front(), note))


def flush(crop=(160, 470, 690, 560)):
    out = []
    for name, shot, F, note in _snaps:
        shot.save(os.path.join(OUT, name + '_win.png')); Image.fromarray(F).save(os.path.join(OUT, name + '_engine1x.png'))
        W, H = shot.size; k = W / 800.0
        up = stretch(F, W, H)
        x0, y0, x1, y1 = [int(round(v * k)) for v in crop]
        pair = Image.new('RGB', (x1 - x0, (y1 - y0) * 2 + 8), (255, 0, 255))
        pair.paste(Image.fromarray(up[y0:y1, x0:x1]), (0, 0)); pair.paste(shot.crop((x0, y0, x1, y1)), (0, y1 - y0 + 8))
        label(pair, '1배를 늘린 것(위) / 4K 글자(아래) ' + note); pair.save(os.path.join(OUT, name + '_pair.png'))
        out.append(name)
    _snaps.clear()
    return out


def state():
    return ftest.state()


def wait_text(sec=10.0):
    m = mem(); t = time.time()
    while time.time() - t < sec:
        ftest.act()
        if m.u32(0x4663e8) == 1:
            return True
        time.sleep(0.15)
    return False


def log_tail(n=6):
    p = os.path.join(ftest.GAME, 'hitext.log')
    try:
        with open(p, 'rb') as f:
            return f.read().decode('utf-8', 'replace').splitlines()[-n:]
    except OSError:
        return []

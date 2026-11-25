# -*- coding: utf-8 -*-
"""섞기(레콘키스타 blend_art.blend) + 투명도 4배(AI 없음, 0/255 가 만나는 테두리만 경사 2배)."""
import numpy as np, cv2

def blend(src_rgb, ai_rgb, lo=40, hi=120, feather=9):
    h, w = src_rgb.shape[:2]
    g = cv2.cvtColor(src_rgb, cv2.COLOR_BGR2GRAY).astype(np.float32)
    edge = cv2.GaussianBlur(cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1)), (3, 3), 0)
    m = np.clip((edge - lo) / (hi - lo), 0, 1)
    m = cv2.GaussianBlur(cv2.resize(m, (w * 4, h * 4), interpolation=cv2.INTER_LINEAR), (feather, feather), 0)
    soft = cv2.resize(src_rgb, (w * 4, h * 4), interpolation=cv2.INTER_LANCZOS4)
    out = (ai_rgb.astype(np.float32) * m[:, :, None] + soft.astype(np.float32) * (1 - m[:, :, None]))
    return np.clip(out + 0.5, 0, 255).astype(np.uint8), float(m.mean())

def alpha4(a1):
    """a1: 1배 투명도 uint8 -> 4배. Lanczos 4배; 1배에서 0 과 255 가 3x3 안에서 만나는 테두리에만(5x5 흐림으로 이어) 가운데 기준 경사 2배;
    1배에서 0/255 이던 칸은 4x4 그대로 고정."""
    h, w = a1.shape
    v = cv2.resize(a1.astype(np.float32), (w * 4, h * 4), interpolation=cv2.INTER_LANCZOS4)
    k = np.ones((3, 3), np.uint8)
    has0 = cv2.dilate((a1 == 0).astype(np.uint8), k) > 0
    has255 = cv2.dilate((a1 == 255).astype(np.uint8), k) > 0
    border = (has0 & has255).astype(np.float32)
    bw = cv2.GaussianBlur(cv2.resize(border, (w * 4, h * 4), interpolation=cv2.INTER_NEAREST), (5, 5), 0)
    steep = np.clip((v - 127.5) * 2 + 127.5, 0, 255)
    v = v * (1 - bw) + steep * bw
    v = np.clip(v, 0, 255)
    rep = lambda m: np.repeat(np.repeat(m, 4, 0), 4, 1)
    v[rep(a1 == 255)] = 255
    v[rep(a1 == 0)] = 0
    return (v + 0.5).astype(np.uint8)

def lost_alpha_pct(a1, a4):
    small = cv2.resize(a4, (a1.shape[1], a1.shape[0]), interpolation=cv2.INTER_AREA).astype(np.float64)
    tot = a1.astype(np.float64).sum()
    return 0.0 if tot == 0 else 100.0 * max(0.0, tot - small.sum()) / tot

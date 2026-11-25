# -*- coding: utf-8 -*-
"""이야기 지도 번쩍임 재기 (2026-11-23).

숨긴 시험 사본(기본 Y:/AI/forest-color-test/game)의 Forest 창 그림(DWM 쪽 창 화면)을 짧은 간격으로 읽어,
지도가 다시 그려지는 동안 검은 화면이 몇 장·얼마나 오래 보이는지 센다. 게임 입력은 PostMessage 만.

  python -X utf8 flicker_probe.py <이름> [--sec 4] [--mode invalidate|hover] [--every 0.25]

  invalidate: 0.25초마다 창을 「다시 그려야 함」으로 표시(InvalidateRect) — 지도 WM_PAINT 를 그대로 부름
  hover     : 마우스 이동을 띠 위로 왕복시켜(명판에 올렸다 뗐다) 지도의 Redraw 를 부름 — 사용자 손과 같은 길
결과: <OUT>/<이름>.json (프레임마다 시각·어두운 비율), 검은 프레임 몇 장은 PNG 로.
"""
import ctypes, ctypes.wintypes as wt, json, os, sys, time, argparse
import numpy as np
from pathlib import Path

GAME = Path(os.environ.get('FOREST_GAME', r'Y:\AI\forest-color-test\game'))
OUT = Path(os.environ.get('PROBE_OUT', r'Y:\AI\claude-work\forest-map-flicker'))
U = ctypes.WinDLL('user32', use_last_error=True)
G = ctypes.WinDLL('gdi32', use_last_error=True)
K = ctypes.WinDLL('kernel32', use_last_error=True)

U.GetDC.restype = wt.HDC; U.GetDC.argtypes = [wt.HWND]
U.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
G.CreateCompatibleDC.restype = wt.HDC; G.CreateCompatibleDC.argtypes = [wt.HDC]
G.SelectObject.restype = wt.HGDIOBJ; G.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
G.BitBlt.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HDC, ctypes.c_int, ctypes.c_int, wt.DWORD]
G.DeleteObject.argtypes = [wt.HGDIOBJ]; G.DeleteDC.argtypes = [wt.HDC]
G.CreateDIBSection.restype = wt.HBITMAP
G.CreateDIBSection.argtypes = [wt.HDC, ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
U.InvalidateRect.argtypes = [wt.HWND, ctypes.c_void_p, wt.BOOL]
U.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
U.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
U.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
U.IsWindowVisible.argtypes = [wt.HWND]
U.GetWindow.argtypes = [wt.HWND, wt.UINT]; U.GetWindow.restype = wt.HWND
U.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
K.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
K.OpenProcess.restype = wt.HANDLE
U.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
U.UpdateWindow.argtypes = [wt.HWND]
GRAB = 'printwindow'


class BMIH(ctypes.Structure):
    _fields_ = [('biSize', wt.DWORD), ('biWidth', ctypes.c_long), ('biHeight', ctypes.c_long), ('biPlanes', wt.WORD),
                ('biBitCount', wt.WORD), ('biCompression', wt.DWORD), ('biSizeImage', wt.DWORD), ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', wt.DWORD), ('biClrImportant', wt.DWORD)]


def game_window():
    """시험 사본 경로의 Forest.exe 가 가진 LiosGameClass 창."""
    want = str(GAME / 'Forest.exe').lower()
    found = []
    EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(h, _):
        buf = ctypes.create_unicode_buffer(64); U.GetClassNameW(h, buf, 64)
        if buf.value != 'LiosGameClass': return True
        pid = wt.DWORD(); U.GetWindowThreadProcessId(h, ctypes.byref(pid))
        hp = K.OpenProcess(0x1000, False, pid.value)
        if hp:
            n = wt.DWORD(1024); p = ctypes.create_unicode_buffer(1024)
            if K.QueryFullProcessImageNameW(hp, 0, p, ctypes.byref(n)) and p.value.lower() == want:
                found.append(h)
            K.CloseHandle(hp)
        return True
    U.EnumWindows(EnumProc(cb), 0)
    return found[0] if found else None


class Grab:
    def __init__(self, h):
        self.h = h
        r = wt.RECT(); U.GetClientRect(h, ctypes.byref(r)); self.w, self.hh = r.right, r.bottom
        self.wdc = U.GetDC(h); self.mdc = G.CreateCompatibleDC(self.wdc)
        bi = BMIH(ctypes.sizeof(BMIH), self.w, -self.hh, 1, 32, 0, 0, 0, 0, 0, 0)
        self.bits = ctypes.c_void_p()
        self.bmp = G.CreateDIBSection(self.wdc, ctypes.byref(bi), 0, ctypes.byref(self.bits), None, 0)
        self.old = G.SelectObject(self.mdc, self.bmp)
        self.arr = np.ctypeslib.as_array(ctypes.cast(self.bits, ctypes.POINTER(ctypes.c_uint8)), shape=(self.hh, self.w, 4))

    def frame(self):
        if GRAB == 'bitblt':
            G.BitBlt(self.mdc, 0, 0, self.w, self.hh, self.wdc, 0, 0, 0x00CC0020)
        else:
            U.PrintWindow(self.h, self.mdc, 3)   # PW_CLIENTONLY | PW_RENDERFULLCONTENT (DWM 쪽 그림)
        s = self.arr[::10, ::10, :3]
        dark = float((s.max(axis=2) < 24).mean())
        return dark, float(s.mean())

    def save(self, path):
        from PIL import Image
        Image.fromarray(self.arr[:, :, 2::-1].copy()).save(path)

    def close(self):
        G.SelectObject(self.mdc, self.old); G.DeleteObject(self.bmp); G.DeleteDC(self.mdc); U.ReleaseDC(self.h, self.wdc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name'); ap.add_argument('--sec', type=float, default=4.0)
    ap.add_argument('--mode', default='invalidate'); ap.add_argument('--every', type=float, default=0.25)
    ap.add_argument('--keep', type=int, default=4)
    ap.add_argument('--grab', default='printwindow')
    a = ap.parse_args()
    global GRAB
    GRAB = a.grab
    OUT.mkdir(parents=True, exist_ok=True)
    h = game_window()
    if not h: print('no test-copy window'); return 2
    if a.mode == 'paintms':
        # 지도 한 장 그리는 시간: 다시 그려야 함 표시 → UpdateWindow(창 스레드에 WM_PAINT 를 보내 끝날 때까지 기다림)
        ms = []
        for _ in range(int(a.sec / a.every)):
            U.InvalidateRect(h, None, False)
            t = time.perf_counter(); U.UpdateWindow(h); ms.append(round(1000 * (time.perf_counter() - t), 2))
            time.sleep(a.every)
        res = dict(name=a.name, mode='paintms', n=len(ms), median=float(np.median(ms)), min=min(ms), max=max(ms), all=ms)
        (OUT / f'{a.name}.json').write_text(json.dumps(res), encoding='utf-8')
        print(json.dumps(res)); return 0
    g = Grab(h)
    # 마우스 왕복 경로(물리 좌표): 띠 가운데 줄을 가로로(800×600 논리 y=300 근처)
    sx = g.w / 800.0
    path = [(int(x * sx), int(300 * sx)) for x in range(80, 721, 40)]
    frames, pokes = [], []
    kept = 0
    t0 = time.perf_counter(); nxt = t0; k = 0
    while True:
        t = time.perf_counter() - t0
        if t > a.sec: break
        if time.perf_counter() >= nxt:
            if a.mode == 'invalidate':
                U.InvalidateRect(h, None, False)
            else:
                x, y = path[k % len(path)] if (k // len(path)) % 2 == 0 else path[len(path) - 1 - k % len(path)]
                U.PostMessageW(h, 0x200, 0, (y << 16) | (x & 0xffff))
            pokes.append(round(t, 4)); k += 1; nxt += a.every
        d, m = g.frame()
        frames.append((round(time.perf_counter() - t0, 4), round(d, 4), round(m, 1)))
        if d > 0.9 and kept < a.keep:
            g.save(OUT / f'{a.name}_black{kept}.png'); kept += 1
    g.save(OUT / f'{a.name}_last.png')
    g.close()
    # 검은 구간: 어두운 비율 > 0.9 인 프레임이 이어진 묶음
    runs, cur = [], None
    for t, d, m in frames:
        if d > 0.9:
            cur = [t, t] if cur is None else [cur[0], t]
        elif cur is not None:
            runs.append(cur); cur = None
    if cur: runs.append(cur)
    base = [d for _, d, _ in frames]
    res = dict(name=a.name, mode=a.mode, client=[g.w, g.hh], sec=a.sec, every=a.every, frames=len(frames),
               frame_ms=round(1000 * a.sec / max(1, len(frames)), 2), pokes=len(pokes),
               black_frames=sum(1 for d in base if d > 0.9), black_runs=len(runs),
               black_run_ms=[round(1000 * (r[1] - r[0]), 1) for r in runs][:40],
               dark_median=float(np.median(base)) if base else None)
    (OUT / f'{a.name}.json').write_text(json.dumps(dict(summary=res, frames=frames, pokes=pokes), ensure_ascii=False), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
"""시험 사본(숨은 데스크톱·음소거)에서: 타이틀 → 특전 → 「오프닝」 → 영상 재생 → 끝난 뒤 타이틀로 돌아오는지."""
import ctypes, os, sys, time, subprocess, struct
from ctypes import wintypes
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32')
GAME = r'Y:\AI\claude-work\forest-optest\game'
OUT = r'Y:\AI\claude-work\forest-optest\out2'
MUTE = r'Y:\AI\claude-work\forest-optest\tools\mute.ps1'
os.makedirs(OUT, exist_ok=True)

class SI(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('r', wintypes.LPWSTR), ('desk', wintypes.LPWSTR), ('t', wintypes.LPWSTR)] + \
               [(n, wintypes.DWORD) for n in ('x', 'y', 'xs', 'ys', 'xc', 'yc', 'fa', 'fl')] + \
               [('sw', wintypes.WORD), ('cr2', wintypes.WORD), ('r2', ctypes.c_void_p), ('i', wintypes.HANDLE), ('o', wintypes.HANDLE), ('e', wintypes.HANDLE)]
class PI(ctypes.Structure):
    _fields_ = [('hp', wintypes.HANDLE), ('ht', wintypes.HANDLE), ('pid', wintypes.DWORD), ('tid', wintypes.DWORD)]
user32.CreateDesktopW.restype = wintypes.HANDLE
desk_name = 'ForestOpTest2'
hdesk = user32.CreateDesktopW(desk_name, None, None, 0, 0x10000000, None)
si = SI(); si.cb = ctypes.sizeof(SI); si.desk = 'WinSta0\\' + desk_name
pi = PI()
assert kernel32.CreateProcessW(os.path.join(GAME, 'Forest.exe'), None, None, None, False, 0, None, GAME, ctypes.byref(si), ctypes.byref(pi))
pid = pi.pid; hp = pi.hp
log = open(os.path.join(OUT, 'test.log'), 'w', encoding='utf-8')
def L(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); log.write(s + '\n'); log.flush()
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def wins():
    res = []
    def cb(h, l):
        p = wintypes.DWORD(); user32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid: res.append(h)
        return True
    user32.EnumDesktopWindows(hdesk, WNDENUMPROC(cb), 0); return res
def cls(h):
    b = ctypes.create_unicode_buffer(256); user32.GetClassNameW(h, b, 256); return b.value
def title(h):
    b = ctypes.create_unicode_buffer(256); user32.GetWindowTextW(h, b, 256); return b.value
def children(h):
    res = []
    def cb(c, l): res.append(c); return True
    user32.EnumChildWindows(h, WNDENUMPROC(cb), 0); return res
def main_wnd():
    for h in wins():
        if title(h) == 'Forest' and user32.GetWindow(h, 4) == 0: return h
def rd(addr, n=4):
    b = ctypes.create_string_buffer(n); r = ctypes.c_size_t()
    kernel32.ReadProcessMemory(hp, ctypes.c_void_p(addr), b, n, ctypes.byref(r)); return b.raw
def state():
    sc = struct.unpack('<I', rd(0x46639c))[0]
    if not sc: return (0, 0)
    base = struct.unpack('<I', rd(sc))[0]; cur = struct.unpack('<I', rd(sc + 0x44))[0]; sid = struct.unpack('<H', rd(sc + 0x3c, 2))[0]
    return (sid, cur - base)
def movie_visible(h):
    return [cls(c) + (':vis' if user32.IsWindowVisible(c) else ':hid') for c in children(h)]
def mute():
    subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', MUTE, '-ProcessId', str(pid)], capture_output=True)
def poke(h):
    user32.PostMessageW(h, 0x1C, 1, 0); user32.PostMessageW(h, 0x06, 1, 0)
def click(h, x, y):
    lp = (y << 16) | x
    user32.PostMessageW(h, 0x200, 0, lp); time.sleep(0.3)
    user32.PostMessageW(h, 0x201, 1, lp); time.sleep(0.1); user32.PostMessageW(h, 0x202, 0, lp)
def shot(name):
    h = main_wnd()
    rc = wintypes.RECT(); user32.GetClientRect(h, ctypes.byref(rc)); w, hh = rc.right, rc.bottom
    hdc = user32.GetDC(h); mdc = gdi32.CreateCompatibleDC(hdc); bmp = gdi32.CreateCompatibleBitmap(hdc, w, hh); gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(h, mdc, 2)
    stride = (w * 3 + 3) & ~3; buf = ctypes.create_string_buffer(stride * hh)
    class BIH(ctypes.Structure):
        _fields_ = [('sz', wintypes.DWORD), ('w', wintypes.LONG), ('h', wintypes.LONG), ('pl', wintypes.WORD), ('bc', wintypes.WORD), ('c', wintypes.DWORD), ('si', wintypes.DWORD), ('x', wintypes.LONG), ('y', wintypes.LONG), ('cu', wintypes.DWORD), ('ci', wintypes.DWORD)]
    bi = BIH(); bi.sz = 40; bi.w = w; bi.h = -hh; bi.pl = 1; bi.bc = 24
    gdi32.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    with open(os.path.join(OUT, name + '.bmp'), 'wb') as f:
        f.write(b'BM' + struct.pack('<IHHI', 54 + len(buf.raw), 0, 0, 54)); f.write(struct.pack('<IiiHHIIiiII', 40, w, -hh, 1, 24, 0, len(buf.raw), 0, 0, 0, 0)); f.write(buf.raw)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(h, hdc)
    L('shot', name, (w, hh), state(), movie_visible(h))

def wait_pc(lo, hi, limit, label):
    t0 = time.time()
    while time.time() - t0 < limit:
        mute(); h = main_wnd()
        if h:
            poke(h); s = state()
            if s[0] == 1 and lo <= s[1] <= hi: L(label, 'reached', s, int(time.time() - t0), 's'); return True
        time.sleep(1)
    L(label, 'TIMEOUT', state()); return False
try:
    ok = wait_pc(488, 497, 180, 'title')
    time.sleep(2); shot('01_title')
    h = main_wnd()
    click(h, 607, 403)           # 특전
    ok = wait_pc(926, 935, 20, 'extras')
    time.sleep(1); shot('02_extras')
    click(h, 607, 403)           # 오프닝
    for i in range(8):
        time.sleep(1); mute(); poke(h)
    shot('03_playing_8s')
    t0 = time.time(); back = False
    while time.time() - t0 < 90:
        time.sleep(2); mute(); poke(h); s = state()
        if s[0] == 1 and 488 <= s[1] <= 497: back = True; L('back to title after', int(time.time() - t0) + 8, 's'); break
    shot('04_after')
    L('RESULT', 'PASS' if back else 'FAIL')
finally:
    kernel32.TerminateProcess(hp, 0); time.sleep(1); user32.CloseDesktop(hdesk); L('done')

# -*- coding: utf-8 -*-
"""Forest 오프닝 다시 틀기 실험(시험 사본, 숨은 데스크톱, 음소거).
타이틀에 닿으면 [0x466428](오프닝 끝 표식)=0 으로 두고 창에 0x41e 를 보내 엔진의 부팅 길로 오프닝을 다시 튼다.
사진은 out\ 에 남긴다."""
import ctypes, os, sys, time, subprocess, struct
from ctypes import wintypes
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32')

GAME = r'Y:\AI\claude-work\forest-optest\game'
OUT = r'Y:\AI\claude-work\forest-optest\out'
MUTE = r'Y:\AI\claude-work\forest-optest\tools\mute.ps1'
os.makedirs(OUT, exist_ok=True)

class SI(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('r', wintypes.LPWSTR), ('desk', wintypes.LPWSTR), ('t', wintypes.LPWSTR)] + \
               [(n, wintypes.DWORD) for n in ('x', 'y', 'xs', 'ys', 'xc', 'yc', 'fa', 'fl')] + \
               [('sw', wintypes.WORD), ('cr2', wintypes.WORD), ('r2', ctypes.c_void_p), ('i', wintypes.HANDLE), ('o', wintypes.HANDLE), ('e', wintypes.HANDLE)]
class PI(ctypes.Structure):
    _fields_ = [('hp', wintypes.HANDLE), ('ht', wintypes.HANDLE), ('pid', wintypes.DWORD), ('tid', wintypes.DWORD)]

user32.CreateDesktopW.restype = wintypes.HANDLE
desk_name = 'ForestOpTest'
hdesk = user32.CreateDesktopW(desk_name, None, None, 0, 0x10000000, None)
si = SI(); si.cb = ctypes.sizeof(SI); si.desk = 'WinSta0\\' + desk_name
pi = PI()
ok = kernel32.CreateProcessW(os.path.join(GAME, 'Forest.exe'), None, None, None, False, 0, None, GAME, ctypes.byref(si), ctypes.byref(pi))
if not ok:
    print('launch failed', ctypes.get_last_error()); sys.exit(1)
pid = pi.pid; hp = pi.hp
print('pid', pid)
log = open(os.path.join(OUT, 'probe.log'), 'w', encoding='utf-8')
def L(*a):
    s = ' '.join(str(x) for x in a); print(s); log.write(s + '\n'); log.flush()

def mute():
    subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', MUTE, '-ProcessId', str(pid)], capture_output=True)

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def wins():
    res = []
    def cb(h, l):
        p = wintypes.DWORD(); user32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid: res.append(h)
        return True
    user32.EnumDesktopWindows(hdesk, WNDENUMPROC(cb), 0)
    return res
def cls(h):
    b = ctypes.create_unicode_buffer(256); user32.GetClassNameW(h, b, 256); return b.value
def title(h):
    b = ctypes.create_unicode_buffer(256); user32.GetWindowTextW(h, b, 256); return b.value
def children(h):
    res = []
    def cb(c, l): res.append(c); return True
    user32.EnumChildWindows(h, WNDENUMPROC(cb), 0)
    return res
def main_wnd():
    for h in wins():
        if title(h) == 'Forest' and user32.GetWindow(h, 4) == 0: return h
def rd(addr, n=4):
    b = ctypes.create_string_buffer(n); r = ctypes.c_size_t()
    kernel32.ReadProcessMemory(hp, ctypes.c_void_p(addr), b, n, ctypes.byref(r)); return b.raw
def wr(addr, data):
    r = ctypes.c_size_t(); return kernel32.WriteProcessMemory(hp, ctypes.c_void_p(addr), data, len(data), ctypes.byref(r))
def state():
    sc = struct.unpack('<I', rd(0x46639c))[0]
    if not sc: return 'no script'
    base = struct.unpack('<I', rd(sc))[0]; cur = struct.unpack('<I', rd(sc + 0x44))[0]; sid = struct.unpack('<H', rd(sc + 0x3c, 2))[0]
    flag = struct.unpack('<I', rd(0x466428))[0]
    return f'sid={sid} pc={cur - base} opflag={flag}'
def shot(name):
    h = main_wnd()
    if not h: L('shot: no window'); return
    rc = wintypes.RECT(); user32.GetClientRect(h, ctypes.byref(rc)); w, hh = rc.right, rc.bottom
    hdc = user32.GetDC(h); mdc = gdi32.CreateCompatibleDC(hdc); bmp = gdi32.CreateCompatibleBitmap(hdc, w, hh); gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(h, mdc, 2)
    class BIH(ctypes.Structure):
        _fields_ = [('sz', wintypes.DWORD), ('w', wintypes.LONG), ('h', wintypes.LONG), ('pl', wintypes.WORD), ('bc', wintypes.WORD), ('c', wintypes.DWORD), ('si', wintypes.DWORD), ('x', wintypes.LONG), ('y', wintypes.LONG), ('cu', wintypes.DWORD), ('ci', wintypes.DWORD)]
    bi = BIH(); bi.sz = 40; bi.w = w; bi.h = -hh; bi.pl = 1; bi.bc = 24
    stride = (w * 3 + 3) & ~3; buf = ctypes.create_string_buffer(stride * hh)
    gdi32.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    with open(os.path.join(OUT, name + '.bmp'), 'wb') as f:
        f.write(b'BM' + struct.pack('<IHHI', 54 + len(buf.raw), 0, 0, 54))
        f.write(struct.pack('<IiiHHIIiiII', 40, w, -hh, 1, 24, 0, len(buf.raw), 0, 0, 0, 0)); f.write(buf.raw)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(h, hdc)
    L('shot', name, w, hh, 'children', [cls(c) for c in children(h)])

def wait_title(limit):
    t0 = time.time()
    while time.time() - t0 < limit:
        mute()
        h = main_wnd()
        if h:
            user32.PostMessageW(h, 0x1C, 1, 0); user32.PostMessageW(h, 0x06, 1, 0)   # 활성 알림(비활성이면 진행이 멈춤)
            s = state()
            if 'sid=1 pc=48' in s: return s
        time.sleep(1)
    return 'timeout ' + state()

try:
    L('boot', wait_title(150))
    time.sleep(2); shot('01_title'); L(state())
    h = main_wnd()
    L('write flag', wr(0x466428, struct.pack('<I', 0)))
    user32.PostMessageW(h, 0x41e, 0, 0)
    for i in range(6):
        time.sleep(1); mute()
        user32.PostMessageW(h, 0x1C, 1, 0); user32.PostMessageW(h, 0x06, 1, 0)
    shot('02_after6s'); L(state())
    for i in range(70):
        time.sleep(1); mute()
        user32.PostMessageW(h, 0x1C, 1, 0); user32.PostMessageW(h, 0x06, 1, 0)
        if i % 10 == 0: L(i, state(), [cls(c) for c in children(h)])
    shot('03_after76s'); L(state())
    time.sleep(5); shot('04_after81s'); L(state())
finally:
    kernel32.TerminateProcess(hp, 0)
    time.sleep(1)
    user32.CloseDesktop(hdesk)
    L('done')

# -*- coding: utf-8 -*-
"""Forest 숨긴 시험 도구(아이콘 줄 갈래). 창은 모든 모니터 오른쪽 바깥, 소리 끔, 입력은 창 메시지로만(진짜 커서·키보드 안 씀).

  python -I ftest.py guard            게임을 띄우고(앞 창 안 빼앗음) 끝날 때까지 모든 창을 화면 밖에 두고 소리를 끈다(백그라운드로)
  python -I ftest.py act              엔진에 「활성」이라고 알림(비활성이면 엔진이 멈춘다)
  python -I ftest.py shot OUT.png     PrintWindow 로 게임 화면(800×600)
  python -I ftest.py move X Y | click X Y | rclick X Y | key NAME | altshift N
  python -I ftest.py state            자동·숨김·설정·시스템 화면 깃발, 단추 콜백 칸, 슬라이더 값
  python -I ftest.py quit             창 닫기 → 게임의 종료 확인 「예」 → 꺼질 때까지
  python -I ftest.py log [N]          forest-chart-progress\\events.log 꼬리
게임 폴더는 FTEST_GAME 환경 변수(기본 Y:\\AI\\forest-qol-test-buttons\\game).
"""
import ctypes, ctypes.wintypes as wt, os, struct, subprocess, sys, time

GAME = os.environ.get('FTEST_GAME', r'Y:\AI\forest-qol-test-buttons\game')
EXE = os.path.join(GAME, 'Forest.exe')
MUTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin', 'mutewatch.exe')

u32 = ctypes.WinDLL('user32', use_last_error=True)
k32 = ctypes.WinDLL('kernel32', use_last_error=True)
g32 = ctypes.WinDLL('gdi32', use_last_error=True)
try:
    u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass

WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
u32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
u32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
k32.ReadProcessMemory.argtypes = [wt.HANDLE, wt.LPCVOID, wt.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.OpenProcess.restype = wt.HANDLE


def find_pid():
    """실행 파일 경로가 GAME\\Forest.exe 인 프로세스."""
    TH32CS_SNAPPROCESS = 2

    class PE(ctypes.Structure):
        _fields_ = [('dwSize', wt.DWORD), ('cntUsage', wt.DWORD), ('th32ProcessID', wt.DWORD), ('th32DefaultHeapID', ctypes.c_void_p),
                    ('th32ModuleID', wt.DWORD), ('cntThreads', wt.DWORD), ('th32ParentProcessID', wt.DWORD), ('pcPriClassBase', ctypes.c_long),
                    ('dwFlags', wt.DWORD), ('szExeFile', ctypes.c_wchar * 260)]
    k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    e = PE(); e.dwSize = ctypes.sizeof(PE)
    ok = k32.Process32FirstW(snap, ctypes.byref(e))
    found = []
    while ok:
        if e.szExeFile.lower() == 'forest.exe':
            h = k32.OpenProcess(0x1000, False, e.th32ProcessID)
            if h:
                buf = ctypes.create_unicode_buffer(1024); n = wt.DWORD(1024)
                if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) and os.path.normcase(buf.value) == os.path.normcase(EXE):
                    found.append(e.th32ProcessID)
                k32.CloseHandle(h)
        ok = k32.Process32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return found[0] if found else None


def windows(pid, visible=True):
    out = []
    def cb(h, l):
        p = wt.DWORD(); u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and (not visible or u32.IsWindowVisible(h)):
            out.append(h)
        return True
    u32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def cls(h):
    b = ctypes.create_unicode_buffer(256); u32.GetClassNameW(h, b, 256); return b.value


def title(h):
    b = ctypes.create_unicode_buffer(256); u32.GetWindowTextW(h, b, 256); return b.value


def rect(h):
    r = wt.RECT(); u32.GetWindowRect(h, ctypes.byref(r)); return r


def main_window(pid=None):
    pid = pid or find_pid()
    if not pid:
        raise SystemExit('game not running')
    for h in windows(pid):
        if cls(h) == 'LiosGameClass':
            return h
    for h in windows(pid):
        if title(h) == 'Forest':
            return h
    raise SystemExit('window not found')


def offscreen_x():
    return u32.GetSystemMetrics(76) + u32.GetSystemMetrics(78) + 400   # 가상 화면 오른쪽 + 400


# ---------------------------------------------------------------- guard
def guard():
    if find_pid():
        print('already running'); return
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 4          # SW_SHOWNOACTIVATE: 첫 ShowWindow 가 앞 창을 빼앗지 않게
    env = dict(os.environ); env['TEMP'] = env['TMP'] = r'Y:\AI\claude-work\claude-temp'
    p = subprocess.Popen([EXE], cwd=GAME, startupinfo=si, env=env)
    print('launched pid', p.pid, flush=True)
    m = subprocess.Popen([MUTE, str(p.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    X = offscreen_x()
    seen = {}
    t0 = time.time()
    SWP = 0x0001 | 0x0010 | 0x0004      # NOSIZE | NOACTIVATE | NOZORDER
    while p.poll() is None:
        for h in windows(p.pid):
            r = rect(h)
            want_x = X + (0 if cls(h) == 'LiosGameClass' else 900)
            if r.left < X - 50:
                u32.SetWindowPos(h, None, want_x, 40, 0, 0, SWP)
                key = (h, cls(h))
                if key not in seen:
                    seen[key] = 1
                    print('%.2fs moved %s cls=%s title=%s from %d,%d' % (time.time() - t0, h, cls(h), title(h), r.left, r.top), flush=True)
        time.sleep(0.01 if time.time() - t0 < 30 else 0.03)
    print('game exited code', p.returncode, flush=True)
    m.wait(5)


# ---------------------------------------------------------------- 조작
def post(h, m, w, l):
    u32.PostMessageW(h, m, w, l)


def act(h=None):
    h = h or main_window()
    post(h, 0x1C, 1, 0); post(h, 0x06, 1, 0)


def L(x, y):
    return ((y & 0xffff) << 16) | (x & 0xffff)


def move(x, y):
    h = main_window(); act(h); post(h, 0x200, 0, L(x, y))


def click(x, y):
    h = main_window(); act(h)
    post(h, 0x200, 0, L(x, y)); time.sleep(0.12)
    post(h, 0x201, 1, L(x, y)); time.sleep(0.1)
    post(h, 0x202, 0, L(x, y))


def rclick(x, y):
    h = main_window(); act(h)
    post(h, 0x200, 0, L(x, y)); time.sleep(0.1)
    post(h, 0x204, 2, L(x, y)); time.sleep(0.1)
    post(h, 0x205, 0, L(x, y))


def drag(x0, y0, x1, y1, steps=8):
    h = main_window(); act(h)
    post(h, 0x200, 0, L(x0, y0)); time.sleep(0.1)
    post(h, 0x201, 1, L(x0, y0)); time.sleep(0.1)
    for i in range(1, steps + 1):
        x = round(x0 + (x1 - x0) * i / steps); y = round(y0 + (y1 - y0) * i / steps)
        post(h, 0x200, 1, L(x, y)); time.sleep(0.05)
    post(h, 0x202, 0, L(x1, y1))


VK = {'ENTER': 0x0D, 'SPACE': 0x20, 'ESC': 0x1B, 'SHIFT': 0x10, 'CTRL': 0x11, 'TAB': 0x09, 'F8': 0x77,
      'UP': 0x26, 'DOWN': 0x28, 'HOME': 0x24}


def key(name):
    h = main_window(); act(h)
    vk = VK.get(name.upper(), ord(name.upper()[0]))
    sc = u32.MapVirtualKeyW(vk, 0)
    post(h, 0x100, vk, 1 | (sc << 16)); time.sleep(0.08)
    post(h, 0x101, vk, 1 | (sc << 16) | 0xC0000000)


def altshift(n):
    """Alt+Shift+숫자 = 그 칸 불러오기(원작 숨은 키)."""
    h = main_window(); act(h)
    vk = 0x30 + n
    post(h, 0x100, 0x10, 1); time.sleep(0.05)
    post(h, 0x104, vk, 1 | (1 << 29)); time.sleep(0.08)
    post(h, 0x105, vk, 1 | (1 << 29) | 0xC0000000); time.sleep(0.05)
    post(h, 0x101, 0x10, 1 | 0xC0000000)


# ---------------------------------------------------------------- 화면
def shot(out, h=None):
    from PIL import Image
    h = h or main_window()
    r = rect(h)
    W, H = r.right - r.left, r.bottom - r.top
    hdc = u32.GetDC(h); mdc = g32.CreateCompatibleDC(hdc); bmp = g32.CreateCompatibleBitmap(hdc, W, H)
    g32.SelectObject(mdc, bmp)
    u32.PrintWindow(h, mdc, 2)

    class BIH(ctypes.Structure):
        _fields_ = [('biSize', wt.DWORD), ('biWidth', ctypes.c_long), ('biHeight', ctypes.c_long), ('biPlanes', wt.WORD), ('biBitCount', wt.WORD),
                    ('biCompression', wt.DWORD), ('biSizeImage', wt.DWORD), ('biXPelsPerMeter', ctypes.c_long), ('biYPelsPerMeter', ctypes.c_long),
                    ('biClrUsed', wt.DWORD), ('biClrImportant', wt.DWORD)]
    bi = BIH(); bi.biSize = ctypes.sizeof(BIH); bi.biWidth = W; bi.biHeight = -H; bi.biPlanes = 1; bi.biBitCount = 32
    buf = ctypes.create_string_buffer(W * H * 4)
    g32.GetDIBits(mdc, bmp, 0, H, buf, ctypes.byref(bi), 0)
    g32.DeleteObject(bmp); g32.DeleteDC(mdc); u32.ReleaseDC(h, hdc)
    im = Image.frombuffer('RGBA', (W, H), buf.raw, 'raw', 'BGRA', 0, 1).convert('RGB')
    pt = wt.POINT(0, 0); u32.ClientToScreen(h, ctypes.byref(pt))
    c = wt.RECT(); u32.GetClientRect(h, ctypes.byref(c))
    ox, oy = pt.x - r.left, pt.y - r.top
    im = im.crop((ox, oy, ox + c.right, oy + c.bottom))
    im.save(out)
    return im


# ---------------------------------------------------------------- 메모리
class Mem:
    def __init__(self):
        self.pid = find_pid()
        if not self.pid:
            raise SystemExit('game not running')
        self.h = k32.OpenProcess(0x0010 | 0x0400, False, self.pid)

    def read(self, addr, n):
        b = ctypes.create_string_buffer(n); got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), b, n, ctypes.byref(got)):
            return None
        return b.raw

    def u32(self, addr):
        b = self.read(addr, 4); return struct.unpack('<I', b)[0] if b else None


def state():
    m = Mem()
    d = {}
    for name, a in [('auto', 0x466408), ('hide', 0x466420), ('settings', 0x46640c), ('system', 0x4663cc), ('skip', 0x466404),
                    ('ctrl', 0x466400), ('wait2', 0x4663e8), ('s418', 0x466418)]:
        d[name] = m.u32(a)
    win = m.u32(0x46630c)
    d['msgwin'] = hex(win or 0)
    if win:
        d['slot_auto'] = hex(m.u32(win + 0x2c94)); d['slot_menu'] = hex(m.u32(win + 0x2c8c))
        d['row_off'] = m.u32(win + 0x2c7c); d['enabled'] = m.u32(win + 0x2c74)
        sl = m.u32(win + 0x60)
        if sl:
            d['slider'] = (m.u32(sl + 0x38), m.u32(sl + 0x18), m.u32(sl + 0x20), m.u32(sl + 0x28))   # 값, x, 폭, 움직일 길이
    cfg = m.read(0x46644c, 30)
    d['cfg'] = cfg.hex() if cfg else None
    return d


def quit_game():
    pid = find_pid()
    if not pid:
        print('not running'); return
    h = main_window(pid)
    post(h, 0x112, 0xF060, 0)
    dlg = None
    for _ in range(40):
        act(h); time.sleep(0.25)
        for w in windows(pid):
            if cls(w) == '#32770':
                dlg = w; break
        if dlg:
            break
    if not dlg:
        print('no confirmation dialog'); return
    print('dialog', title(dlg))
    post(dlg, 0x111, 6, 0)
    for _ in range(60):
        time.sleep(0.25)
        if not find_pid():
            print('quit normally'); return
    print('still running')


def log(n=30):
    p = os.path.join(GAME, 'forest-chart-progress', 'events.log')
    with open(p, 'rb') as f:
        lines = f.read().decode('utf-8', 'replace').splitlines()
    print('\n'.join(lines[-n:]))


if __name__ == '__main__':
    a = sys.argv[1:]
    c = a[0]
    if c == 'guard': guard()
    elif c == 'act': act(); print('activated')
    elif c == 'shot': shot(a[1]); print('saved', a[1])
    elif c == 'move': move(int(a[1]), int(a[2]))
    elif c == 'click': click(int(a[1]), int(a[2]))
    elif c == 'rclick': rclick(int(a[1]), int(a[2]))
    elif c == 'drag': drag(*map(int, a[1:5]))
    elif c == 'key': key(a[1])
    elif c == 'altshift': altshift(int(a[1]))
    elif c == 'state': print(state())
    elif c == 'quit': quit_game()
    elif c == 'log': log(int(a[1]) if len(a) > 1 else 30)
    elif c == 'wins':
        pid = find_pid()
        for h in windows(pid):
            r = rect(h); print(h, cls(h), title(h), r.left, r.top, r.right, r.bottom)
    else: print(__doc__)

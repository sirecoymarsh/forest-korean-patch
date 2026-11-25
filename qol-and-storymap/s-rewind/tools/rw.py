# -*- coding: utf-8 -*-
"""Forest 되감기 시험 도우미 (2026-11-25).

- 시험 사본을 「숨은 데스크톱」에서 띄운다: 창이 사용자 화면에 안 나오고, 초점을 안 뺏고, 사용자 입력이 안 섞인다.
- 소리는 프로세스 세션을 음소거(ini 의 hiart_test_mute + mute.ps1).
- 입력은 PostMessage 만. 엔진이 비활성이면 멈추므로 활성 메시지를 함께 보낸다.
- 상태는 프로세스 메모리를 읽어서 본다(엔진 주소는 P:\\AI\\forest-qol\\엔진_메모.md).
"""
import ctypes, math, os, struct, subprocess, sys, time
from ctypes import wintypes
from PIL import Image

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32')
user32.CreateDesktopW.restype = wintypes.HANDLE
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.RegisterWindowMessageW.restype = wintypes.UINT
kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

GAME = r'Y:\AI\forest-qol-test-rewind\game'
MUTE = r'Y:\AI\claude-work\forest-optest\tools\mute.ps1'
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
PROBE = user32.RegisterWindowMessageW('ForestRewindTest')   # 되감기 모듈의 시험 메시지(ini rewind_test=1): lParam = 걸음 수


class SI(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('r', wintypes.LPWSTR), ('desk', wintypes.LPWSTR), ('t', wintypes.LPWSTR)] + \
               [(n, wintypes.DWORD) for n in ('x', 'y', 'xs', 'ys', 'xc', 'yc', 'fa', 'fl')] + \
               [('sw', wintypes.WORD), ('cr2', wintypes.WORD), ('r2', ctypes.c_void_p), ('i', wintypes.HANDLE), ('o', wintypes.HANDLE), ('e', wintypes.HANDLE)]


class PI(ctypes.Structure):
    _fields_ = [('hp', wintypes.HANDLE), ('ht', wintypes.HANDLE), ('pid', wintypes.DWORD), ('tid', wintypes.DWORD)]


class Game:
    def __init__(self, out, desk='ForestRewindTest'):
        self.out = out
        os.makedirs(out, exist_ok=True)
        self.logf = open(os.path.join(out, 'run.log'), 'a', encoding='utf-8')
        self.desk_name = desk
        self.hdesk = user32.CreateDesktopW(desk, None, None, 0, 0x10000000, None)
        assert self.hdesk, 'CreateDesktop failed'
        si = SI(); si.cb = ctypes.sizeof(SI); si.desk = 'WinSta0\\' + desk
        pi = PI()
        ok = kernel32.CreateProcessW(os.path.join(GAME, 'Forest.exe'), None, None, None, False, 0, None, GAME, ctypes.byref(si), ctypes.byref(pi))
        assert ok, 'CreateProcess failed %d' % ctypes.get_last_error()
        self.pid = pi.pid; self.hp = pi.hp
        self.h = None
        self.ev_pos = 0
        self.L('launched pid', self.pid, 'on hidden desktop', desk)

    def L(self, *a):
        s = time.strftime('%H:%M:%S ') + ' '.join(str(x) for x in a)
        print(s, flush=True); self.logf.write(s + '\n'); self.logf.flush()

    # ---- 창
    def wins(self):
        res = []
        def cb(h, l):
            p = wintypes.DWORD(); user32.GetWindowThreadProcessId(h, ctypes.byref(p))
            if p.value == self.pid: res.append(h)
            return True
        user32.EnumDesktopWindows(self.hdesk, WNDENUMPROC(cb), 0)
        return res

    @staticmethod
    def cls(h):
        b = ctypes.create_unicode_buffer(256); user32.GetClassNameW(h, b, 256); return b.value

    @staticmethod
    def title(h):
        b = ctypes.create_unicode_buffer(256); user32.GetWindowTextW(h, b, 256); return b.value

    def main(self):
        for h in self.wins():
            if self.title(h) == 'Forest' and user32.GetWindow(h, 4) == 0 and self.cls(h) != '#32770':
                self.h = h; return h
        return None

    def alive(self):
        code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(self.hp, ctypes.byref(code))
        if code.value != 259 and not getattr(self, 'exit_logged', False):
            # 143 = 셸의 `timeout` 이 시간이 다 되어 프로세스 묶음을 끝낸 것(게임이 죽은 것이 아니다 — 11-25 t5c 에서 그랬다). 시험은 그 한도 안에 끝나게 짤 것.
            self.exit_logged = True; self.L('game process ended, exit code', code.value)
        return code.value == 259

    # ---- 메모리
    def rd(self, addr, n=4):
        b = ctypes.create_string_buffer(n); r = ctypes.c_size_t()
        kernel32.ReadProcessMemory(self.hp, ctypes.c_void_p(addr), b, n, ctypes.byref(r))
        return b.raw

    def w32(self, addr, val):
        """시험 가속용: 엔진 깃발 하나를 쓴다(찍히는 글을 한꺼번에 끝내는 [0x4663d4] 등)."""
        b = struct.pack('<I', val); r = ctypes.c_size_t()
        kernel32.WriteProcessMemory(self.hp, ctypes.c_void_p(addr), b, 4, ctypes.byref(r))

    def w16(self, addr, val):
        b = struct.pack('<H', val); r = ctypes.c_size_t()
        kernel32.WriteProcessMemory(self.hp, ctypes.c_void_p(addr), b, 2, ctypes.byref(r))

    def u32(self, a): return struct.unpack('<I', self.rd(a))[0]
    def u16(self, a): return struct.unpack('<H', self.rd(a, 2))[0]

    def state(self):
        sc = self.u32(0x46639c)
        sid = pc = 0
        if sc:
            base = self.u32(sc); cur = self.u32(sc + 0x44); sid = self.u16(sc + 0x3c); pc = (cur - base) & 0xffffffff
        return dict(sid=sid, pc=pc, click=self.u32(0x4663e8), typing=self.u32(0x4663e0), choice=self.u32(0x4663cc), select=self.u32(0x466418),
                    settings=self.u32(0x46640c), auto=self.u32(0x466408), depth=self.u16(0x4664bc), nested=self.u16(0x466432),
                    bgm=self.u16(0x46646c), se=self.u16(0x466470), seloop=self.u16(0x466472))

    def bgm_engine(self):
        eng = self.u32(0x466398)
        mgr = self.u32(eng + 0x1a8) if eng else 0
        return (self.u32(mgr + 0x10), self.u32(mgr + 0xc)) if mgr else (0, 0)

    # ---- 입력
    def poke(self):
        if self.h:
            user32.PostMessageW(self.h, 0x1C, 1, 0); user32.PostMessageW(self.h, 0x06, 1, 0)

    def post(self, m, w=0, l=0):
        user32.PostMessageW(self.h, m, w, l)

    def key(self, vk, hold=0.05):
        self.poke(); self.post(0x100, vk, 1); time.sleep(hold); self.post(0x101, vk, 0xC0000001)

    def client(self):
        r = wintypes.RECT(); user32.GetClientRect(self.h, ctypes.byref(r)); return r.right, r.bottom

    def to_phys(self, x, y):
        w, hh = self.client()
        if w * 600 <= hh * 800: cw, ch = w, (w * 600 + 400) // 800
        else: ch, cw = hh, (hh * 800 + 300) // 600
        ox, oy = (w - cw) // 2, (hh - ch) // 2
        return ox + math.floor((x + 0.5) * cw / 800), oy + math.floor((y + 0.5) * ch / 600)

    def click(self, x, y, hold=0.08, button='l'):
        X, Y = self.to_phys(x, y)
        lp = (Y << 16) | (X & 0xffff)
        down, up, mk = (0x201, 0x202, 1) if button == 'l' else (0x204, 0x205, 2)
        self.poke(); self.post(0x200, 0, lp); time.sleep(0.15)
        self.post(down, mk, lp); time.sleep(hold); self.post(up, 0, lp)

    def dialog(self):
        for h in self.wins():
            if self.cls(h) == '#32770' and user32.IsWindowVisible(h): return h
        return None

    def answer_yes(self, timeout=6):
        t0 = time.time()
        while time.time() - t0 < timeout:
            self.poke(); d = self.dialog()
            if d:
                t = self.title(d); time.sleep(0.2); user32.PostMessageW(d, 0x111, 6, 0); return t
            time.sleep(0.1)
        return None

    def rewind(self, steps=1):
        self.poke(); self.post(PROBE, 0, steps)

    def mute(self):
        subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', MUTE, '-ProcessId', str(self.pid)], capture_output=True)

    # ---- 그림(클라이언트)
    def _grab_once(self):
        h = self.h
        w, hh = self.client()
        hdc = user32.GetDC(h); mdc = gdi32.CreateCompatibleDC(hdc); bmp = gdi32.CreateCompatibleBitmap(hdc, w, hh); gdi32.SelectObject(mdc, bmp)
        ok = False
        for attempt in range(4):
            if user32.PrintWindow(h, mdc, 3): ok = True; break   # PW_CLIENTONLY | PW_RENDERFULLCONTENT; 실패하면 그림이 새까맣게 남는다 → 다시
            self.shot_retries = getattr(self, 'shot_retries', 0) + 1
            time.sleep(0.05)
        bmi = FastCap.BMI(ctypes.sizeof(FastCap.BMI), w, -hh, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * hh * 4)
        gdi32.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bmi), 0)
        gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(h, hdc)
        return ok, Image.frombuffer('RGBA', (w, hh), buf, 'raw', 'BGRA', 0, 1).convert('RGB')

    @staticmethod
    def black_tail(img):
        """아래에서부터 통째로 (0,0,0) 인 줄 수."""
        import numpy as np
        a = np.asarray(img); n = a.shape[0]
        if a[n - 16:].any(): return 0 if a[n - 1].any() else next(k for k in range(1, 17) if a[n - 1 - k].any())
        full = ~a.reshape(n, -1).any(axis=1)
        k = 0
        while k < n and full[n - 1 - k]: k += 1
        return k

    def shot(self, name=None):
        """창 안쪽 그림. 찍는 도구가 가끔 그림을 덜 가져온다 — 통째로 검게(t5a, 11-25 아침), 또는 위에서부터 일부만 채우고 나머지는 검게
        (h5, 11-25 낮: 위 318줄 + 8줄의 왼쪽 512칸만 채워진 그림. 같은 길을 34번 다시 지나며 3,600장을 찍어도 화면은 온전했다).
        그래서 아래쪽이 통째로 검은 그림이 나오면 한 번 더 찍어 본다: 검은 줄이 줄면 처음 것은 덜 가져온 그림이다(세어 두고 그림도 남긴다)."""
        ok, img = self._grab_once()
        k = self.black_tail(img)
        if k >= 16 or not ok:
            for i in range(2):
                time.sleep(0.06)
                ok2, img2 = self._grab_once(); k2 = self.black_tail(img2)
                if ok2 and k2 < k:
                    self.partial_shots = getattr(self, 'partial_shots', 0) + 1
                    self.L('  capture came back partly empty: %d black rows at the bottom (PrintWindow said %s), taken again: %d black rows' % (k, ok, k2))
                    if self.partial_shots <= 6: img.save(os.path.join(self.out, 'partial_capture_%02d.png' % self.partial_shots))
                    ok, img, k = ok2, img2, k2
                else:
                    break
        if name: img.save(os.path.join(self.out, name + '.png'))
        return img

    # ---- 기록
    def events_path(self):
        return os.path.join(GAME, 'forest-chart-progress', 'events.log')

    def new_events(self):
        try:
            with open(self.events_path(), 'rb') as f:
                f.seek(self.ev_pos); data = f.read(); self.ev_pos += len(data)
        except OSError:
            return []
        return data.decode('utf-8', 'replace').splitlines()

    def skip_events(self):
        try: self.ev_pos = os.path.getsize(self.events_path())
        except OSError: self.ev_pos = 0

    # ---- 기다리기
    def wait(self, pred, timeout=30, step=0.05, poke=True):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if poke: self.poke()
            s = self.state()
            if pred(s): return s
            if not self.alive(): raise RuntimeError('game exited')
            time.sleep(step)
        return None

    def wait_title(self, timeout=150):
        t0 = time.time(); muted = 0
        while time.time() - t0 < timeout:
            if not self.h: self.main()
            if self.h:
                self.poke()
                if time.time() - muted > 3: self.mute(); muted = time.time()
                s = self.state()
                if s['sid'] == 1 and s['select'] == 1: return s
            if not self.alive(): raise RuntimeError('game exited at start')
            time.sleep(0.3)
        return None

    # ---- 끝내기
    def quit(self, timeout=20):
        self.poke(); self.post(0x112, 0xF060, 0)
        dlg = None; t0 = time.time()
        while time.time() - t0 < 8 and not dlg:
            self.poke(); time.sleep(0.2)
            for h in self.wins():
                if self.cls(h) == '#32770' and user32.IsWindowVisible(h): dlg = h
        if not dlg:
            self.L('no quit confirmation dialog'); return False
        self.L('quit dialog:', self.title(dlg))
        user32.PostMessageW(dlg, 0x111, 6, 0)   # IDYES
        t0 = time.time()
        while time.time() - t0 < timeout:
            if not self.alive(): self.L('quit normally'); return True
            time.sleep(0.2)
        return False

    def close(self):
        if self.alive():
            kernel32.TerminateProcess(self.hp, 0); time.sleep(0.5); self.L('terminated (forced)')
        user32.CloseDesktop(self.hdesk)


def diff(a, b, mask=None, tol=8):
    """두 그림에서 tol 넘게 다른 화소 수와 그 테두리 상자. mask = [(x0,y0,x1,y1)] 는 뺀다(그림 좌표)."""
    import numpy as np
    if a.size != b.size: return dict(n=-1, box=None, size=(a.size, b.size))
    x = np.asarray(a, dtype=np.int16); y = np.asarray(b, dtype=np.int16)
    d = (abs(x - y).max(axis=2) > tol)
    for m in (mask or []):
        d[m[1]:m[3], m[0]:m[2]] = False
    n = int(d.sum())
    if not n: return dict(n=0, box=None)
    ys, xs = d.nonzero()
    return dict(n=n, box=(int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1), frac=n / d.size)


class FastCap:
    """Game.shot 과 같은 방법(PrintWindow 3)으로, 그릇을 다시 쓰며 빨리 찍는다(한 장 약 10 ms). grab() → (성공, RGB numpy 배열)."""
    class BMI(ctypes.Structure):
        _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG), ('biPlanes', wintypes.WORD),
                    ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD), ('biSizeImage', wintypes.DWORD),
                    ('biXPelsPerMeter', wintypes.LONG), ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]

    def __init__(self, game):
        self.h = game.h; self.w, self.hh = game.client()
        hdc = user32.GetDC(self.h); self.mdc = gdi32.CreateCompatibleDC(hdc); self.bmp = gdi32.CreateCompatibleBitmap(hdc, self.w, self.hh)
        user32.ReleaseDC(self.h, hdc)
        self.bmi = FastCap.BMI(ctypes.sizeof(FastCap.BMI), self.w, -self.hh, 1, 32, 0, 0, 0, 0, 0, 0)
        self.buf = ctypes.create_string_buffer(self.w * self.hh * 4)

    def grab(self):
        import numpy as np
        old = gdi32.SelectObject(self.mdc, self.bmp)
        ok = user32.PrintWindow(self.h, self.mdc, 3)
        gdi32.SelectObject(self.mdc, old)
        gdi32.GetDIBits(self.mdc, self.bmp, 0, self.hh, self.buf, ctypes.byref(self.bmi), 0)
        return bool(ok), np.frombuffer(self.buf, dtype=np.uint8).reshape(self.hh, self.w, 4)[:, :, 2::-1].copy()   # BGRA → RGB


def ndiff(a, b, mask=(), tol=8):
    """numpy 그림 둘에서 tol 넘게 다른 화소 수와 테두리 상자."""
    import numpy as np
    d = (np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2) > tol)
    for m in mask: d[m[1]:m[3], m[0]:m[2]] = False
    n = int(d.sum())
    if not n: return 0, None
    ys, xs = d.nonzero()
    return n, (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)

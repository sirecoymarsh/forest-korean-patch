"""Forest 「진행」 갈래 숨긴 시험 도구 (2026-11-21).

- 게임은 WMI 로 앱 밖에서 띄운다(ShowWindow=4: 초점을 안 뺏음). 그 프로세스의 모든 보이는 창(확인 창 포함)을
  20ms 마다 모든 모니터 오른쪽 바깥으로 옮기고, 오디오 세션은 생기자마자 음소거한다.
- 입력은 PostMessage 로만 보낸다(실제 커서·키보드는 안 씀). 엔진이 비활성이면 멈추므로 활성 메시지를 보낸다.
- 그림은 PrintWindow(클라이언트만).
- 시험 도우미 메시지 "ForestQolPlayTest"(시험용 임시 qol_present.cpp 에만 있음): 상태 덤프·불러오기·건너뛰기 범위.
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from PIL import Image

ctypes.windll.shcore.SetProcessDpiAwareness(2)
U = ctypes.WinDLL("user32", use_last_error=True)
G = ctypes.WinDLL("gdi32")
K = ctypes.WinDLL("kernel32")
U.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
U.SendMessageTimeoutW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM, wt.UINT, wt.UINT, ctypes.POINTER(ctypes.c_size_t)]
U.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
U.RegisterWindowMessageW.restype = wt.UINT
EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

GAME = Path(os.environ.get("FOREST_GAME", r"Y:\AI\forest-qol-test-play\game"))
OUT = Path(os.environ.get("FOREST_OUT", r"Y:\AI\forest-qol-test-play\out"))
OUT.mkdir(parents=True, exist_ok=True)
TEST_MSG = U.RegisterWindowMessageW("ForestQolPlayTest")


def log(*a):
    s = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(s + "\n")


# ---------------------------------------------------------------- 모니터
def monitors():
    mons = []
    CB = ctypes.WINFUNCTYPE(wt.BOOL, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)

    def cb(h, dc, r, l):
        mons.append((r.contents.left, r.contents.top, r.contents.right, r.contents.bottom))
        return True
    U.EnumDisplayMonitors(None, None, CB(cb), 0)
    return mons


OFF_X = max(m[2] for m in monitors()) + 60
OFF_Y = 80


# ---------------------------------------------------------------- 프로세스·창
def pids():
    psapi = ctypes.windll.psapi
    arr = (wt.DWORD * 8192)()
    got = wt.DWORD()
    psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(got))
    want = (GAME / "Forest.exe").resolve()
    res = []
    buf = ctypes.create_unicode_buffer(1024)
    for pid in arr[: got.value // 4]:
        if not pid:
            continue
        h = K.OpenProcess(0x1000, False, pid)
        if not h:
            continue
        try:
            n = wt.DWORD(1024)
            if K.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
                p = Path(buf.value)
                if p.name.lower() == "forest.exe":
                    try:
                        if p.resolve() == want:
                            res.append(int(pid))
                    except OSError:
                        pass
        finally:
            K.CloseHandle(h)
    return res


def any_forest():
    """다른 사본의 Forest 도 포함해 실행 중인 Forest.exe 경로들"""
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-Process Forest -ErrorAction SilentlyContinue | ForEach-Object { $_.Path }"],
                         capture_output=True, text=True).stdout.split("\n")
    return [x.strip() for x in out if x.strip()]


def windows_of(pid):
    hits = []

    def cb(h, _):
        p = wt.DWORD()
        U.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and U.IsWindowVisible(h):
            hits.append(h)
        return True
    U.EnumWindows(EnumProc(cb), 0)
    return hits


def cls(h):
    b = ctypes.create_unicode_buffer(256)
    U.GetClassNameW(h, b, 256)
    return b.value


def title(h):
    b = ctypes.create_unicode_buffer(256)
    U.GetWindowTextW(h, b, 256)
    return b.value


def main_window(pid):
    for h in windows_of(pid):
        if cls(h) == "LiosGameClass":
            return h
    return None


# ---------------------------------------------------------------- 소리(Core Audio 세션 음소거)
ole = ctypes.OleDLL("ole32")


class GUID(ctypes.Structure):
    _fields_ = [("d1", ctypes.c_uint32), ("d2", ctypes.c_uint16), ("d3", ctypes.c_uint16), ("d4", ctypes.c_ubyte * 8)]

    @classmethod
    def of(cls, s):
        g = cls()
        ctypes.memmove(ctypes.byref(g), uuid.UUID(s).bytes_le, 16)
        return g


CLSID_MMDeviceEnumerator = GUID.of("BCDE0395-E52F-467C-8E3D-C4579291692E")
IID_IMMDeviceEnumerator = GUID.of("A95664D2-9614-4F35-A746-DE8DB63617E6")
IID_IAudioSessionManager2 = GUID.of("77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F")
IID_IAudioSessionControl2 = GUID.of("BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D")
IID_ISimpleAudioVolume = GUID.of("87CE5498-68D6-44E5-9215-6DA47EF883D8")
IID_IAudioMeterInformation = GUID.of("C02216F6-8C67-4B5B-9D00-D008E73E0064")


def _call(obj, idx, argtypes, *a):
    vt = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    hr = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(vt[idx])(obj, *a)
    if hr < 0:
        raise OSError("HRESULT 0x%08x" % (hr & 0xFFFFFFFF))
    return hr


def _qi(obj, iid):
    out = ctypes.c_void_p()
    _call(obj, 0, [ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(iid), ctypes.byref(out))
    return out


def _rel(obj):
    if obj:
        vt = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt[2])(obj)


def audio_sessions(pid):
    """[(ISimpleAudioVolume, IAudioMeterInformation)] of pid (this thread must have CoInitializeEx)"""
    enum = ctypes.c_void_p()
    ole.CoCreateInstance(ctypes.byref(CLSID_MMDeviceEnumerator), None, 23, ctypes.byref(IID_IMMDeviceEnumerator), ctypes.byref(enum))
    coll = ctypes.c_void_p()
    _call(enum, 3, [ctypes.c_int, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)], 0, 1, ctypes.byref(coll))
    n = ctypes.c_uint32()
    _call(coll, 3, [ctypes.POINTER(ctypes.c_uint32)], ctypes.byref(n))
    found = []
    for i in range(n.value):
        dev = ctypes.c_void_p()
        _call(coll, 4, [ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)], i, ctypes.byref(dev))
        mgr = ctypes.c_void_p()
        _call(dev, 3, [ctypes.POINTER(GUID), ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
              ctypes.byref(IID_IAudioSessionManager2), 23, None, ctypes.byref(mgr))
        se = ctypes.c_void_p()
        _call(mgr, 5, [ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(se))
        cnt = ctypes.c_int()
        _call(se, 3, [ctypes.POINTER(ctypes.c_int)], ctypes.byref(cnt))
        for j in range(cnt.value):
            ctl = ctypes.c_void_p()
            _call(se, 4, [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)], j, ctypes.byref(ctl))
            ctl2 = _qi(ctl, IID_IAudioSessionControl2)
            p = ctypes.c_uint32()
            _call(ctl2, 14, [ctypes.POINTER(ctypes.c_uint32)], ctypes.byref(p))
            if p.value == pid:
                found.append((_qi(ctl, IID_ISimpleAudioVolume), _qi(ctl, IID_IAudioMeterInformation)))
            _rel(ctl2)
            _rel(ctl)
        _rel(se)
        _rel(mgr)
        _rel(dev)
    _rel(coll)
    _rel(enum)
    return found


# ---------------------------------------------------------------- 지킴이(창 밖으로·음소거·소리 크기 기록)
class Keeper(threading.Thread):
    def __init__(self, pid):
        super().__init__(daemon=True)
        self.pid = pid
        self.stop = False
        self.muted = False
        self.peak = 0.0
        self.peaks = []   # (time, peak)
        self.moved = 0

    def run(self):
        ole.CoInitializeEx(None, 0)
        last_audio = 0
        while not self.stop:
            for h in windows_of(self.pid):
                r = wt.RECT()
                U.GetWindowRect(h, ctypes.byref(r))
                main = cls(h) == "LiosGameClass"
                x = OFF_X if main else OFF_X + 900
                if r.left < OFF_X - 5 or (not main and r.left < OFF_X + 895):
                    U.SetWindowPos(h, None, x, OFF_Y, 0, 0, 0x0001 | 0x0004 | 0x0010 | 0x4000)  # NOSIZE|NOZORDER|NOACTIVATE|ASYNC
                    self.moved += 1
                    if not main:
                        log("moved dialog off-screen:", cls(h), title(h))
            now = time.time()
            if now - last_audio > 0.05:
                last_audio = now
                try:
                    for vol, meter in audio_sessions(self.pid):
                        b = ctypes.c_int()
                        _call(vol, 6, [ctypes.POINTER(ctypes.c_int)], ctypes.byref(b))
                        if not b.value:
                            _call(vol, 5, [ctypes.c_int, ctypes.c_void_p], 1, None)
                            if not self.muted:
                                log("audio session muted")
                        self.muted = True
                        v = ctypes.c_float()
                        _call(meter, 3, [ctypes.POINTER(ctypes.c_float)], ctypes.byref(v))
                        self.peak = v.value
                        self.peaks.append((now, v.value))
                        if len(self.peaks) > 20000:
                            self.peaks = self.peaks[-10000:]
                        _rel(vol)
                        _rel(meter)
                except OSError:
                    pass
            time.sleep(0.02)


# ---------------------------------------------------------------- 띄우기·끝내기
class Game:
    def __init__(self):
        self.pid = None
        self.h = None
        self.keeper = None

    def launch(self, timeout=40):
        if pids():
            raise RuntimeError("test copy already running")
        exe = GAME / "Forest.exe"
        ps = ("$si = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ShowWindow=[uint16]4}; "
              "$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='\"%s\"'; "
              "CurrentDirectory='%s'; ProcessStartupInformation=$si}; $r.ProcessId" % (exe, GAME))
        fg = U.GetForegroundWindow()
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.strip()
        self.pid = int(out.split()[-1])
        log("launched pid", self.pid, "offscreen x", OFF_X)
        self.keeper = Keeper(self.pid)
        self.keeper.start()
        t0 = time.time()
        while time.time() - t0 < timeout:
            self.h = main_window(self.pid)
            if self.h:
                break
            if self.pid not in pids():
                raise RuntimeError("game exited at start (another Forest running?)")
            time.sleep(0.05)
        if not self.h:
            raise RuntimeError("no game window")
        log("window", hex(self.h))
        time.sleep(0.6)
        if U.GetForegroundWindow() == self.h and fg and U.IsWindow(fg):
            me, gt = K.GetCurrentThreadId(), U.GetWindowThreadProcessId(self.h, None)
            att = U.AttachThreadInput(me, gt, True)
            U.SetForegroundWindow(fg)
            if att:
                U.AttachThreadInput(me, gt, False)
            log("focus handed back:", U.GetForegroundWindow() == fg)
        return self

    def alive(self):
        return self.pid in pids()

    def user_touched(self):
        return U.GetForegroundWindow() == self.h

    # 입력
    def activate(self):
        U.PostMessageW(self.h, 0x1C, 1, 0)
        U.PostMessageW(self.h, 0x06, 1, 0)

    def post(self, m, w=0, l=0):
        U.PostMessageW(self.h, m, w, l)

    def keydown(self, vk, repeat=False):
        self.post(0x100, vk, (0x40000001 if repeat else 1))

    def keyup(self, vk):
        self.post(0x101, vk, 0xC0000001)

    def key(self, vk, hold=0.08):
        self.activate()
        self.keydown(vk)
        time.sleep(hold)
        self.keyup(vk)
        time.sleep(0.05)

    def click(self, x=400, y=300, hold=0.12, button="l"):
        self.activate()
        lp = (y << 16) | (x & 0xffff)
        down, up = (0x201, 0x202) if button == "l" else (0x204, 0x205)
        self.post(0x200, 0, lp)
        time.sleep(0.05)
        self.post(down, 1 if button == "l" else 2, lp)
        time.sleep(hold)
        self.post(up, 0, lp)
        time.sleep(0.05)

    def wheel(self, delta, x=400, y=300):
        self.activate()
        pt = wt.POINT(x, y)
        U.ClientToScreen(self.h, ctypes.byref(pt))
        self.post(0x20A, (delta & 0xffff) << 16, ((pt.y & 0xffff) << 16) | (pt.x & 0xffff))

    def test(self, w, l=0):
        self.post(TEST_MSG, w, l)

    # 상태
    def state(self, wait=0.4):
        p = GAME / "playtest_state.txt"
        try:
            p.unlink()
        except OSError:
            pass
        self.test(1)
        t0 = time.time()
        while time.time() - t0 < 5:
            if p.exists():
                time.sleep(0.05)
                txt = p.read_text(encoding="ascii", errors="replace")
                d = {}
                for part in txt.split():
                    if "=" in part:
                        k, v = part.split("=", 1)
                        d[k] = v
                return d
            time.sleep(0.05)
        return {}

    def shot(self, name):
        h = self.h
        r = wt.RECT()
        U.GetClientRect(h, ctypes.byref(r))
        w, hh = r.right, r.bottom
        hdc = U.GetDC(h)
        mdc = G.CreateCompatibleDC(hdc)
        bmp = G.CreateCompatibleBitmap(hdc, w, hh)
        G.SelectObject(mdc, bmp)
        U.PrintWindow(h, mdc, 3)  # PW_CLIENTONLY | PW_RENDERFULLCONTENT

        class BMI(ctypes.Structure):
            _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                        ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                        ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]
        bmi = BMI(ctypes.sizeof(BMI), w, -hh, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * hh * 4)
        G.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bmi), 0)
        G.DeleteObject(bmp)
        G.DeleteDC(mdc)
        U.ReleaseDC(h, hdc)
        img = Image.frombuffer("RGBA", (w, hh), buf, "raw", "BGRA", 0, 1).convert("RGB")
        path = OUT / (name + ".png")
        img.save(path)
        return path

    def events(self):
        p = GAME / "forest-chart-progress" / "events.log"
        try:
            return p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []

    def wait_state(self, pred, timeout=30, step=0.3, desc=""):
        t0 = time.time()
        while time.time() - t0 < timeout:
            self.activate()
            s = self.state()
            if s and pred(s):
                return s
            time.sleep(step)
        log("wait_state timeout", desc)
        return self.state()

    def quit(self, timeout=20):
        """창 X → 게임 자신의 종료 확인 「예」"""
        self.activate()
        self.post(0x112, 0xF060, 0)
        dlg = None
        t0 = time.time()
        while time.time() - t0 < 8 and not dlg:
            self.activate()
            time.sleep(0.3)
            for h in windows_of(self.pid):
                if cls(h) == "#32770":
                    dlg = h
        if not dlg:
            log("no quit confirmation dialog")
            return False
        log("quit dialog:", title(dlg))
        U.PostMessageW(dlg, 0x111, 6, 0)  # IDYES
        t0 = time.time()
        while time.time() - t0 < timeout:
            if not self.alive():
                log("quit normally")
                if self.keeper:
                    self.keeper.stop = True
                return True
            time.sleep(0.3)
        log("still running after quit")
        return False

    def kill(self):
        if self.pid and self.alive():
            subprocess.run(["taskkill", "/PID", str(self.pid), "/F"], capture_output=True)
        if self.keeper:
            self.keeper.stop = True

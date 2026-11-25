"""설치 묶음을 깐 사본을 숨겨 띄워: 설치 기록 줄·타이틀 도달·창 크기·그림 한 장·정상 종료."""
import os, sys, time, ctypes, ctypes.wintypes as wt
os.environ.setdefault("FOREST_GAME", r"Y:\AI\forest-qol-pkgtest\game")
os.environ.setdefault("FOREST_OUT", r"Y:\AI\forest-qol-pkgtest\out")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fhost
from fhost import log, U

K = ctypes.WinDLL("kernel32")
K.OpenProcess.restype = ctypes.c_void_p
g = fhost.Game().launch()
hp = K.OpenProcess(0x10 | 0x400, False, g.pid)


def u32(a):
    b = ctypes.create_string_buffer(4); n = ctypes.c_size_t()
    K.ReadProcessMemory(ctypes.c_void_p(hp), ctypes.c_void_p(a), b, 4, ctypes.byref(n))
    return int.from_bytes(b.raw, "little")


def sid():
    sc = u32(0x46639c)
    return (u32(sc + 0x3c) & 0xffff) if sc else -1


try:
    line = None; t0 = time.time()
    while time.time() - t0 < 120 and not (line and sid() == 1 and u32(0x466418) == 1):
        g.activate()
        for l in g.events():
            if "qol: present" in l: line = l
        time.sleep(0.5)
    log("INSTALL LOG:", line)
    log("TITLE:", sid() == 1)
    r = wt.RECT(); U.GetClientRect(g.h, ctypes.byref(r)); log("CLIENT:", r.right, r.bottom)
    time.sleep(1.0); g.shot("pkg_title")
finally:
    q = g.quit() if g.alive() else False
    log("QUIT:", q)
    if g.alive(): g.kill()

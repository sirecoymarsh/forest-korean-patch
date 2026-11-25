# -*- coding: utf-8 -*-
"""되감기 오래 돌리기: 메모리·GDI·USER 객체·핸들 수가 새는지, 끝까지 멀쩡한지 본다.
  A. 처음 N 걸음 읽기
  B. 「한 걸음 뒤로 → 한 걸음 앞으로」 M 번(같은 자리를 오감)
  C. 「여러 걸음 뒤로 → 다시 읽기」 몇 번(그림을 견줌)
  D. 대조: 되감기 없이 새로 K 걸음 읽기(핸들이 읽기만으로 얼마나 느는지)
사용: python -I t4_stress.py <출력 이름> [N] [M] [K]"""
import ctypes, os, random, sys, time
from ctypes import wintypes
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv

NAME = sys.argv[1] if len(sys.argv) > 1 else 't4'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 40
M = int(sys.argv[3]) if len(sys.argv) > 3 else 100
K = int(sys.argv[4]) if len(sys.argv) > 4 else 60
r = drv.Run(NAME, settle=0.1); g = r.g
user32 = ctypes.WinDLL('user32'); psapi = ctypes.WinDLL('psapi'); kernel32 = ctypes.WinDLL('kernel32')
user32.GetGuiResources.argtypes = [wintypes.HANDLE, wintypes.DWORD]; user32.GetGuiResources.restype = wintypes.DWORD
psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
kernel32.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]


class PMC(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD), ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t), ('PrivateUsage', ctypes.c_size_t)]


def res():
    p = PMC(); p.cb = ctypes.sizeof(PMC)
    psapi.GetProcessMemoryInfo(g.hp, ctypes.byref(p), p.cb)
    hc = wintypes.DWORD(); kernel32.GetProcessHandleCount(g.hp, ctypes.byref(hc))
    return dict(private_mb=round(p.PrivateUsage / 1048576, 1), gdi=user32.GetGuiResources(g.hp, 0), user=user32.GetGuiResources(g.hp, 1), handles=hc.value)


samples = []


def sample(tag):
    samples.append((tag, res())); r.L('RES', tag, samples[-1][1])


ok = False
try:
    r.start_new_game()
    r.first_pass(N)
    sample('A after reading %d stops' % N)
    done = 0
    for i in range(M):
        b = r.back(1, 'b%03d' % i, compare=(i % 20 == 0))
        if b: done += 1
        r.fwd(1, 'f%03d' % i, compare=(i % 20 == 10))
        if (i + 1) % 50 == 0: sample('B after %d back+forward cycles' % (i + 1))
    for k in (10, 25, 40):
        r.back(k, 'deep%d' % k)
        r.fwd(k, 'reread%d' % k, compare=False)
    r.back(3, 'deep-check'); r.fwd(3, 'deep-check')
    sample('C after 3 deep rewinds and rereads (%d rewinds in all)' % len(r.backs))
    n0 = len(r.stops)
    for j in range(K):
        s, st = r.at_stop(60, need_new=False)
        r.go(s)
        s, st = r.at_stop(60, n0); n0 = len(r.stops)
    sample('D control: after reading %d NEW stops with no rewind' % K)
    ok = True
finally:
    try:
        r.summary(ok, dict(resources=samples))
    finally:
        r.finish(ok)

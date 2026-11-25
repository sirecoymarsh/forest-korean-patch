# -*- coding: utf-8 -*-
"""한 프로세스의 소리 세션 크기(peak) 읽기 — 음소거한 채로도 소리가 나오는지 보려는 것.
(P:\\AI\\forest-qol\\tools\\fhost.py 의 Core Audio 호출을 옮김)"""
import ctypes, uuid

ole = ctypes.OleDLL('ole32')


class GUID(ctypes.Structure):
    _fields_ = [('d1', ctypes.c_uint32), ('d2', ctypes.c_uint16), ('d3', ctypes.c_uint16), ('d4', ctypes.c_ubyte * 8)]

    @classmethod
    def of(cls, s):
        g = cls(); ctypes.memmove(ctypes.byref(g), uuid.UUID(s).bytes_le, 16); return g


CLSID_MMDeviceEnumerator = GUID.of('BCDE0395-E52F-467C-8E3D-C4579291692E')
IID_IMMDeviceEnumerator = GUID.of('A95664D2-9614-4F35-A746-DE8DB63617E6')
IID_IAudioSessionManager2 = GUID.of('77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F')
IID_IAudioSessionControl2 = GUID.of('BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D')
IID_ISimpleAudioVolume = GUID.of('87CE5498-68D6-44E5-9215-6DA47EF883D8')
IID_IAudioMeterInformation = GUID.of('C02216F6-8C67-4B5B-9D00-D008E73E0064')
_init = False


def _call(obj, idx, argtypes, *a):
    vt = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    hr = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(vt[idx])(obj, *a)
    if hr < 0: raise OSError('HRESULT 0x%08x' % (hr & 0xFFFFFFFF))
    return hr


def _qi(obj, iid):
    out = ctypes.c_void_p()
    _call(obj, 0, [ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(iid), ctypes.byref(out))
    return out


def _rel(obj):
    if obj:
        vt = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt[2])(obj)


def sessions(pid):
    """[(ISimpleAudioVolume, IAudioMeterInformation)] — 다 쓰면 release()"""
    global _init
    if not _init:
        ole.CoInitializeEx(None, 0); _init = True
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
        try:
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
                _rel(ctl2); _rel(ctl)
            _rel(se)
        except OSError:
            pass
        _rel(mgr); _rel(dev)
    _rel(coll); _rel(enum)
    return found


def release(found):
    for vol, meter in found:
        _rel(vol); _rel(meter)


def peak(found):
    """지금 세션들의 가장 큰 소리 크기(0~1). 음소거 여부도 함께."""
    best = 0.0; muted = None
    for vol, meter in found:
        v = ctypes.c_float()
        _call(meter, 3, [ctypes.POINTER(ctypes.c_float)], ctypes.byref(v))
        best = max(best, v.value)
        b = ctypes.c_int()
        _call(vol, 6, [ctypes.POINTER(ctypes.c_int)], ctypes.byref(b))
        muted = bool(b.value) if muted is None else (muted and bool(b.value))
    return best, muted

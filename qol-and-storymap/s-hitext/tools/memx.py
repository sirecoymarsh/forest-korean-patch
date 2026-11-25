import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ftest
m = ftest.Mem()
def u32(a): return m.u32(a)
def u16(a): b = m.read(a, 2); return struct.unpack('<H', b)[0] if b else None
def sub(o):  # 가상 바탕 하위 객체
    vb = u32(o); return o + u32(vb + 4)

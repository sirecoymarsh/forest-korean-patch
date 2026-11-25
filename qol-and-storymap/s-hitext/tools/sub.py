# -*- coding: utf-8 -*-
"""5번 칸(1020 이정표)에서 잎을 눌러 3024 로 들어가 노란 자막을 캡처한다. boot.py 5 뒤에."""
import sys, os, time, struct
OUT = sys.argv[1] if len(sys.argv) > 1 else r'Y:\AI\claude-work\hitext\sub'
os.environ['HCAP_OUT'] = OUT
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ftest, hcap
ftest.SCALE = float(os.environ.get('FTEST_SCALE', '3'))
m = hcap.mem()
def sid():
    sc = m.u32(0x46639c); return struct.unpack('<H', m.read(sc + 0x3c, 2))[0]
def yellow():
    F = hcap.front(); reg = F[30:260, 150:700].astype(int)
    return int(((reg[:, :, 0] > 200) & (reg[:, :, 1] > 170) & (reg[:, :, 2] < 90)).sum())
seen = 0; nsys = 0; t0 = time.time()
for i in range(120):
    st = ftest.state()
    if st['system']:
        ys = [int(v) for v in os.environ.get('SUB_YS', '300,250,210,120,375').split(',')]
        ftest.click(400, ys[nsys % len(ys)]); nsys += 1; time.sleep(1.5); print(i, 'system -> leaf, sid', sid(), flush=True); continue
    ftest.click(400, 300); ok = hcap.wait_text(8)
    y = yellow() if not ftest.state()['system'] else 0
    if y > 40:
        seen += 1; r = hcap.cap('sub_%02d' % i, crop=(150, 40, 700, 230), note='노란 자막'); print(i, 'subtitle', y, r, sid(), flush=True)
        if seen >= int(os.environ.get('SUB_N', '3')): break
    if time.time() - t0 > 400: break
print('done seen', seen, 'sid', sid())

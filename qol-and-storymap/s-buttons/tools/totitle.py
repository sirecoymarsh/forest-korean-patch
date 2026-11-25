# 타이틀이 뜰 때까지 기다렸다가 이어하기 → 1쪽 → 1번 칸(시작의 이야기·I) 불러오기, 대사 대기까지
import sys, time; sys.path.insert(0, '.')
import ftest
from PIL import Image
import numpy as np
t0 = time.time()
while True:
    try:
        h = ftest.main_window(); ftest.act(h)
        m = ftest.Mem()
        if m.u32(0x466418) == 1 and time.time() - t0 > 8:
            im = np.array(ftest.shot(r'Y:\AI\fq_shots\_t.png')).astype(int)
            # 타이틀 단추 줄(「이어하기」 칸)이 밝으면
            if im[315:335, 560:650].mean() > 60: break
    except SystemExit:
        pass
    if time.time() - t0 > 150: sys.exit('no title')
    time.sleep(2)
print('title after %.0fs' % (time.time() - t0))
ftest.click(605, 324); time.sleep(1.5)
m = ftest.Mem()
for _ in range(10):
    page = struct_page = m.read(0x466468, 2)
    p = int.from_bytes(page, 'little')
    if p == 0: break
    ftest.click(577, 552); time.sleep(0.8)
ftest.click(233, 230)
for _ in range(40):
    time.sleep(0.5); ftest.act()
    if m.u32(0x4663e8) == 1: break
print('loaded; wait2 =', m.u32(0x4663e8))

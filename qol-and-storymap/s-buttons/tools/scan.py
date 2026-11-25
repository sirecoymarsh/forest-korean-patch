import sys, time; sys.path.insert(0, '.')
import ftest
from PIL import Image
import numpy as np
off, x0, name = int(sys.argv[1], 16), int(sys.argv[2]), sys.argv[3]
m = ftest.Mem(); h = ftest.main_window(); ftest.act(h)
alpha = np.array(Image.open(r'..\compane_new\%s.png' % name))[..., 3]
rows = []
for ly in range(14):
    r = ''
    for lx in range(14):
        ftest.post(h, 0x200, 0, ftest.L(x0 + lx, 584 + ly)); time.sleep(0.06)
        b = m.u32(m.u32(0x46630c) + off)
        hv = m.u32(b + 0xb0)
        r += ('#' if hv else '.') + ('a' if alpha[ly, lx] else ' ')
    rows.append(r)
ftest.post(h, 0x200, 0, ftest.L(400, 300))
print('\n'.join(rows))

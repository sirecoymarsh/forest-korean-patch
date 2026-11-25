import sys, time, os; sys.path.insert(0, '.')
import ftest
import numpy as np
O = r'Y:\AI\fq_shots\run1'
m = ftest.Mem()
def lg(): return open(os.path.join(ftest.GAME, 'forest-chart-progress', 'events.log'), 'rb').read().decode('utf-8', 'replace').splitlines()
def newrow(im): return (np.array(im).astype(int)[584:598, 654:685].max(-1) > 120).sum()
n0 = len(lg())
ftest.rclick(400, 300); time.sleep(1.2); ftest.act()
print('settings', m.u32(0x46640c))
ftest.click(661, 591); time.sleep(1.5)
print('after map click under settings: settings', m.u32(0x46640c), 'new log', [l for l in lg()[n0:] if 'buttons' in l or 'ui opened' in l])
ftest.click(340, 447); time.sleep(1.5); ftest.act(); time.sleep(0.5)
im = ftest.shot(os.path.join(O, 's14_save_screen.png'))
print('save screen: system', m.u32(0x4663cc), 'settings', m.u32(0x46640c), 'new-row bright px', newrow(im))
n1 = len(lg())
ftest.click(661, 591); time.sleep(1.2)
print('map click on save screen -> new log', [l for l in lg()[n1:] if 'buttons' in l or 'ui opened' in l], 'system', m.u32(0x4663cc))

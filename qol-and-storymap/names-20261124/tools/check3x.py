import sys, os, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'P:/AI/commentary-mode/forest/trial/colortest')
from ccc import send
import numpy as np
from PIL import Image
NM = 'Y:/AI/claude-work/forest-names'
def must(c):
    r = send(c)
    if not r.get('ok'): raise SystemExit('! %s -> %s' % (c, r))
    return r['res']
plates = {f: (np.array(Image.open(f'{NM}/shifted/{f}').convert('RGBA'))[:, :, 3] > 160) for f in os.listdir(f'{NM}/shifted') if f.endswith('.patch.png')}
def plate_at(small):
    lum = small.mean(2); top = None
    for f, m in plates.items():
        h, w = m.shape
        for y in range(450, 500):
            reg = lum[y:y + h, 0:w]
            if reg.shape != m.shape: continue
            on, off = reg[m], reg[~m]
            sc = on.mean() - off.mean() - 2 * on.std()
            if top is None or sc > top[0]: top = (sc, f, y)
    return top
must({'op': 'key', 'vk': 27, 'after': 1.5})                     # 지도 닫기
must({'op': 'click', 'x': 607, 'y': 287, 'after': 3.0})          # 처음부터
must({'op': 'wait', 'what': 'clickorchoice', 'sec': 30})
must({'op': 'click', 'x': 326, 'y': 224, 'after': 2.0})          # 붉은 날짜
must({'op': 'keydown', 'vk': 17, 'after': 0.2}); must({'op': 'wait', 'what': 'choice', 'sec': 60}); must({'op': 'keyup', 'vk': 17, 'after': 0.5})
must({'op': 'click', 'x': 330, 'y': 91, 'after': 2.5})           # 회상 I
must({'op': 'wait', 'what': 'clickorchoice', 'sec': 30})
got = {}
for i in range(140):
    p = must({'op': 'shot', 'name': 'c3_probe', 'settle': 0.5})['path']
    big = Image.open(p).convert('RGB'); a = np.array(big).astype(int)
    yel = int(((a[:, :, 0] > 200) & (a[:, :, 1] > 170) & (a[:, :, 2] < 90)).sum())
    if 'yellow' not in got and yel > 6000:
        big.save(f'{NM}/c3_yellow.png'); got['yellow'] = i; print('yellow at', i, yel)
    small = np.array(big.resize((800, 600), Image.LANCZOS)).astype(float)
    t = plate_at(small)
    if 'name' not in got and t and t[0] > 60:
        big.save(f'{NM}/c3_named.png'); got['name'] = (i, t[1], t[2], round(float(t[0]), 1)); print('named at', got['name'])
    if len(got) == 2: break
    st = must({'op': 'state', 'cm': False})
    if st.get('choice') or st.get('select'): print('choice at', i); break
    must({'op': 'key', 'vk': 13, 'after': 0.25}); must({'op': 'wait', 'what': 'clickorchoice', 'sec': 20})
print('got', got)

import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'P:/AI/commentary-mode/forest/trial/colortest')
from ccc import send
import numpy as np
from PIL import Image
NM = 'Y:/AI/claude-work/forest-names'
plates = {}
for f in sorted(os.listdir(f'{NM}/ko')):
    a = np.array(Image.open(f'{NM}/ko/{f}').convert('RGBA'))
    plates[f] = a[:, :, 3] > 160


def best(frame):
    lum = frame.mean(2)
    top = None
    for f, m in plates.items():
        h, w = m.shape
        for y in range(440, 520):
            for x in (0,):
                reg = lum[y:y + h, x:x + w]
                if reg.shape != m.shape: continue
                on, off = reg[m], reg[~m]
                sc = on.mean() - off.mean() - 2 * on.std()
                if top is None or sc > top[0]: top = (sc, f, x, y)
    return top


for i in range(90):
    if i == 0:
        send({"op": "key", "vk": 13, "after": 0.25}); send({"op": "wait", "what": "clickorchoice", "sec": 20})
    p = send({'op': 'shot', 'name': 'nm_probe', 'settle': 0.5})['res']['path']
    a = np.array(Image.open(p).convert('RGB')).astype(float)
    t = best(a)
    st = send({'op': 'state', 'cm': False})['res']
    if t and t[0] > 60:
        Image.open(p).save(f'{NM}/named_1x_after.png'); print(i, 'found', t, 'pc', st.get('pc')); break
    if st.get('choice') or st.get('select'):
        print(i, 'stopped at choice/select', st.get('sid'), st.get('pc')); break
    send({'op': 'key', 'vk': 13, 'after': 0.25})
    send({'op': 'wait', 'what': 'clickorchoice', 'sec': 20})
else:
    print('not found', t)

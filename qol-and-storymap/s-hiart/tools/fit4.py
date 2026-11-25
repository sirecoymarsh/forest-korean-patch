"""추적 기록의 층 목록으로 1배 화면을 다시 합성해 그림자 판과 비교."""
import sys, numpy as np, cv2
sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import trace_read as t
from fit1 import frame, src, REC0

ART = ('grpe', 'grpo_bg', 'grpo_bu', 'grpo_f', 'grpo_ci')


def layer_info(r):
    L, I = r['L'], r['I']
    S = L[0x2a4:]
    SI = I[0x4c:]
    return {'idx': r['idx'], 'path': r['path'], 'vis': t.i32(S, 0xc), 'mode': t.i32(S, 0x30),
            'rect': [t.i32(S, 0x4c + 4 * k) for k in range(4)], 'ivis': t.i32(SI, 0xc),
            'ipos': (t.i32(SI, 0x1c), t.i32(SI, 0x20)), 'isz': (t.i32(SI, 0x14), t.i32(SI, 0x18)),
            'irect': [t.i32(SI, 0x4c + 4 * k) for k in range(4)], 'bpp': t.i32(SI, 0x24)}


def compose(infos):
    M = np.zeros((600, 800, 3), np.int64)
    for li in sorted(infos, key=lambda x: x['idx']):
        f = li['path'].replace('.\\', '').split('\\')[0]
        if f not in ART or not li['vis'] or not li['ivis']: continue
        im = src(li['path']).astype(np.int64)
        x0, y0 = li['irect'][0], li['irect'][1]
        h, w = im.shape[:2]
        xa, ya, xb, yb = max(0, x0), max(0, y0), min(800, x0 + w), min(600, y0 + h)
        s = im[ya - y0:yb - y0, xa - x0:xb - x0]
        rgb = s[:, :, :3]
        if li['mode'] == 6: rgb = rgb >> 1
        if s.shape[2] == 4:
            a = s[:, :, 3:4]
            M[ya:yb, xa:xb] = (rgb * a + M[ya:yb, xa:xb] * (255 - a)) // 255
        else:
            M[ya:yb, xa:xb] = rgb
    return M


if __name__ == '__main__':
    ev = t.read(rec=REC0)
    for e in ev:
        if e[0] != 'D' or e[2] < int(sys.argv[1]): continue
        infos = [layer_info(r) for r in e[3]]
        F = frame(e[2]).astype(np.int64)[:, :, :3]
        M = compose(infos)
        d = np.abs(F - M).max(axis=2)
        bad = d > 4
        print('dump', e[2], 'match(<=4) %.4f' % (1 - bad.mean()), 'bad bbox', cv2.boundingRect(bad.astype(np.uint8)),
              [(i['idx'], i['path'][2:], i['vis'], i['ivis'], i['mode'], i['irect']) for i in infos if i['idx'] in (0, 10, 30, 35, 40)])
        cv2.imwrite(r'Y:\AI\claude-work\forest-hiart\out\fit_bad_%04d.png' % e[2], (bad * 255).astype(np.uint8))

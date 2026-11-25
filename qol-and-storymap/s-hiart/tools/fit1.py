import sys, numpy as np, cv2, struct
sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import trace_read as t
TR = t.TR
REC0 = 4 + 64 + 0x364 + 0x10c


def frame(n):
    return np.fromfile(TR + '\\frame_%04d.bgra' % n, np.uint8).reshape(600, 800, 4)


def src(path):
    f, n = path.replace('.\\', '').split('\\')
    return cv2.imread('Y:\\AI\\forest-4k\\src\\%s\\%s.png' % (f, n), cv2.IMREAD_UNCHANGED)


if __name__ == '__main__':
    ev = t.read(rec=REC0)
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    for e in ev:
        if e[0] != 'D' or e[2] < lo: continue
        print('== dump', e[2])
        for r in e[3]:
            if r['idx'] not in (0, 10, 35): continue
            L = r['L']; I = r['I']
            S = L[0x2a4:]
            sv = [t.i32(S, o) for o in range(0, 0xc0, 4)]
            print(' layer', r['idx'], r['path'], 'S:', ' '.join('%x:%d' % (o * 4, v) for o, v in enumerate(sv) if v != 0 and abs(v) < 100000))
            lv = [t.i32(L, o) for o in range(0, 0x2a4, 4)]
            print('   L:', ' '.join('%x:%d' % (o * 4, v) for o, v in enumerate(lv) if v != 0 and abs(v) < 100000))
            iv = [t.i32(I, o) for o in range(0, 0x10c, 4)]
            print('   img:', ' '.join('%x:%d' % (o * 4, v) for o, v in enumerate(iv) if v != 0 and abs(v) < 100000))

import sys, numpy as np, cv2


def fnv(a):
    h = 2166136261
    for v in a.tolist():
        h = ((h ^ v) * 16777619) & 0xffffffff
    return h


def bgra(key):
    im = cv2.imread('Y:\\AI\\forest-4k\\src\\' + key.replace('/', '\\') + '.png', cv2.IMREAD_UNCHANGED)
    if im.shape[2] == 3:
        im = cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
    return np.ascontiguousarray(im)


if __name__ == '__main__':
    pairs = [x.split('=') for x in sys.argv[1:]]
    for k, want in pairs:
        im = bgra(k)
        a = im.view(np.uint32).ravel()
        z = im.copy(); z[:, :, 3] = 0
        p = im.astype(np.uint32); al = p[:, :, 3:4]
        pm = np.dstack([(p[:, :, :3] * al // 255), p[:, :, 3:]]).astype(np.uint8)
        inv = im.copy(); inv[:, :, 3] = 255 - inv[:, :, 3]
        print(k, want, 'plain %08x' % fnv(a), 'alpha0 %08x' % fnv(np.ascontiguousarray(z).view(np.uint32).ravel()),
              'premul %08x' % fnv(np.ascontiguousarray(pm).view(np.uint32).ravel()), 'inv %08x' % fnv(np.ascontiguousarray(inv).view(np.uint32).ravel()))

import sys, os, numpy as np, cv2
TR = r'Y:\AI\forest-qol-test-hiart\game\forest-chart-progress\hiart-trace'
lo, hi = int(sys.argv[1]), int(sys.argv[2])
out = sys.argv[3]
ims = []
for n in range(lo, hi + 1):
    p = os.path.join(TR, 'frame_%04d.bgra' % n)
    if not os.path.exists(p): continue
    a = np.fromfile(p, np.uint8).reshape(600, 800, 4)[:, :, :3].copy()
    a = cv2.resize(a, (266, 200), interpolation=cv2.INTER_AREA)
    cv2.putText(a, str(n), (5, 20), 0, 0.6, (0, 255, 255), 2)
    ims.append(a)
while len(ims) % 4: ims.append(np.zeros_like(ims[0]))
rows = [np.hstack(ims[i:i + 4]) for i in range(0, len(ims), 4)]
cv2.imwrite(out, np.vstack(rows))

import sys, time; sys.path.insert(0, '.')
import ftest
def dump(off):
    m = ftest.Mem(); w = m.u32(0x46630c); b = m.u32(w + off)
    return m.read(b, 0x128)
off = int(sys.argv[1], 16)
ftest.move(400, 300); time.sleep(0.5); a = dump(off)
ftest.move(int(sys.argv[2]), int(sys.argv[3])); time.sleep(0.5); b = dump(off)
ftest.move(400, 300); time.sleep(0.5); c = dump(off)
for i in range(0, 0x128, 4):
    x, y, z = a[i:i+4], b[i:i+4], c[i:i+4]
    if x != y or y != z:
        print(hex(i), x.hex(), y.hex(), z.hex())

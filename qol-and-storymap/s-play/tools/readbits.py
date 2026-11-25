"""시험 사본 save\rssave.dat 의 읽음 표시 고치기: python -I readbits.py <rssave.dat> <대본> <슬롯 첫> <슬롯 끝> [set]
처음 고칠 때 rssave.dat.orig 를 떠 둔다."""
import shutil, struct, sys
from pathlib import Path
p = Path(sys.argv[1]); sc = int(sys.argv[2]); a = int(sys.argv[3]); z = int(sys.argv[4]); setbit = len(sys.argv) > 5
orig = p.with_name(p.name + '.orig')
if not orig.exists():
    shutil.copy2(p, orig)
b = bytearray(p.read_bytes())
cnt = struct.unpack_from('<I', b, 6030)[0]; q = 6034
for i in range(cnt):
    s, ln = struct.unpack_from('<HI', b, q)
    if s == sc:
        for slot in range(a, z + 1):
            byte, bit = q + 6 + slot // 8, slot % 8
            if slot // 8 < ln:
                if setbit: b[byte] |= (1 << bit)
                else: b[byte] &= ~(1 << bit) & 0xff
        print('script', s, 'bits now', sum(bin(x).count('1') for x in b[q + 6:q + 6 + ln]))
    q += 6 + ln
p.write_bytes(bytes(b))

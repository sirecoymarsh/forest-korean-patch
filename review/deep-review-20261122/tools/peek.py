import sys; sys.stdout.reconfigure(encoding="utf-8")
import sys, os
sys.path.insert(0, r'P:\AI\forest-gemini-review\tools')
from gscwalk import walk
CUR = r'P:\AI\forest-flowchart-claude\runtime\scr'
JA = r'P:\AI\forest-kr-build\ja_scr'
f = sys.argv[1]; a0 = int(sys.argv[2]); n = int(sys.argv[3])
c, s = walk(os.path.join(CUR, f)); jc, js = walk(os.path.join(JA, f))
km = [(a[5], a[1], a) for _, op, a in c if op == 0x51]
jm = [(a[5], a[1], a) for _, op, a in jc if op == 0x51]
for i in range(a0, a0+n):
    print(i, km[i][2], jm[i][2])
    print('  JA', js[jm[i][0]].decode('cp932','replace'))
    print('  KO', s[km[i][0]].decode('cp949','replace'))

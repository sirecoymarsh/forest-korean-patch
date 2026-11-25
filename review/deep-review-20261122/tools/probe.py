import sys, os, collections
sys.path.insert(0, r'P:\AI\forest-gemini-review\tools')
from gscwalk import walk
CUR = r'P:\AI\forest-flowchart-claude\runtime\scr'
JA = r'P:\AI\forest-kr-build\ja_scr'
tot = collections.Counter()
for f in sorted(os.listdir(CUR)):
    if not f.endswith('.gsc'): continue
    c, s = walk(os.path.join(CUR, f))
    cc = collections.Counter(op for _, op, _ in c)
    jp = os.path.join(JA, f)
    if os.path.exists(jp):
        jc, js = walk(jp); jcc = collections.Counter(op for _, op, _ in jc)
    else: jcc = collections.Counter()
    row = (f, cc[0x51], jcc[0x51], cc[0x52], jcc[0x52], cc[0x20], jcc[0x20], cc[0x0E], jcc[0x0E])
    tot['msg'] += cc[0x51]; tot['jmsg'] += jcc[0x51]; tot['app'] += cc[0x52]; tot['japp'] += jcc[0x52]
    if cc[0x51] != jcc[0x51] or cc[0x52] != jcc[0x52] or cc[0x0E] != jcc[0x0E]: print('MISMATCH', row)
print(tot)

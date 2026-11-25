import sys; sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import gscwalk, collections
want={0x14,0x0d,0x1c,0x24,0x27,0x1f,0x21,0x22,0x23,0x25,0x26,0x28,0x3c,0x3d,0x3e,0x3f,0x40,0x42}
ex=collections.defaultdict(list)
for sid,p in gscwalk.all_scripts():
    if sid not in (2100,2200): continue
    rows,_=gscwalk.read_gsc(p)
    for pc,op,a in rows[:4000]:
        if op in want and len(ex[op])<14: ex[op].append(a)
for k,v in sorted(ex.items()): print(hex(k), v)

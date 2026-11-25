import sys; sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import gscwalk
for sid in (0, 100):
    rows,strs=gscwalk.read_gsc(r'P:\AI\forest-kr-build\ja_scr\%04d.gsc'%sid)
    print('==', sid, len(rows), strs[:60])
    for pc,op,a in rows[:300]:
        if op&0xf000: continue
        print(hex(pc), hex(op), a)

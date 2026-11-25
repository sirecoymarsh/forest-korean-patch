import sys; sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import gscwalk, collections
c0=collections.Counter(); ex=collections.defaultdict(list)
for sid,p in gscwalk.all_scripts():
    rows,_=gscwalk.read_gsc(p)
    for pc,op,a in rows:
        if op==0x1e:
            c0[a[0]]+=1
            if len(ex[a[0]])<8: ex[a[0]].append((sid,a))
print(c0.most_common(40))
for k,v in sorted(ex.items()): print(k, v)

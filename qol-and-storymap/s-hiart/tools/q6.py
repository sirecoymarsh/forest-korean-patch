import sys, json, collections; sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import gscwalk
probe={1101,1201,1301,1401,1501,1601,2101,2501,3001,3401,3601,1102,2002,3701,3802}
hits=collections.Counter(); ex=[]
for sid,p in gscwalk.all_scripts():
    rows,strs=gscwalk.read_gsc(p)
    for k,(pc,op,a) in enumerate(rows):
        if op&0xf000:
            for v in a[1:]:
                if v in probe:
                    hits[op&0xf000]+=1
                    if len(ex)<25: ex.append((sid,hex(op),a,[ (hex(o),aa) for _,o,aa in rows[k+1:k+4]]))
print(hits)
for e in ex: print(e)

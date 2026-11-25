import sys, json, collections; sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import gscwalk
probe={1101,1201,1301,1401,1501,1601,2101,2501,3001,3401,3601,1102,2002}
hits=collections.Counter(); ex=[]
for sid,p in gscwalk.all_scripts():
    rows,strs=gscwalk.read_gsc(p)
    for pc,op,a in rows:
        if op&0xf000: continue
        for i,v in enumerate(a):
            if v in probe:
                hits[(op,i)]+=1
                if len(ex)<30: ex.append((sid,hex(op),i,a))
    for s in strs:
        if any(('%04d'%x) in s for x in probe):
            hits[('str',)]+=1
            if len(ex)<40: ex.append((sid,'str',s[:60]))
print(hits.most_common(20)); 
for e in ex: print(e)

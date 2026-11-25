import sys, json, collections; sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import gscwalk
inv=json.load(open(r'Y:\AI\forest-4k\inventory_raw.json',encoding='utf-8'))
where=collections.defaultdict(list)
for e in inv:
    if e['name'][:4].isdigit(): where[int(e['name'][:4])].append(e['arc'].replace('.xfl',''))
dup=[(k,v) for k,v in where.items() if len([a for a in v if a.startswith('grpo')])>1]
print('grpo dup names', len(dup), dup[:10])
both=[(k,v) for k,v in where.items() if 'grpe' in v and any(a.startswith('grpo') for a in v)]
print('grpe&grpo same number', len(both), both[:10])
lay=collections.defaultdict(collections.Counter)
for sid,p in gscwalk.all_scripts():
    rows,_=gscwalk.read_gsc(p)
    for pc,op,a in rows:
        if op==0x1e and a[1]<65536:
            lay[a[0]][tuple(where.get(a[1],['?']))]+=1
for k in sorted(lay): print(k, dict(lay[k]))

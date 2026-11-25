import sys, json, collections; sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import gscwalk
inv=json.load(open(r'Y:\AI\forest-4k\inventory_raw.json',encoding='utf-8'))
grpe={int(e['name'][:4]) for e in inv if e['arc']=='grpe.xfl'}
sc=json.load(open(r'Y:\AI\forest-4k\scenes.json',encoding='utf-8'))
first={}; uses=collections.defaultdict(list); other=collections.Counter()
for sid,p in gscwalk.all_scripts():
    rows,_=gscwalk.read_gsc(p)
    for pc,op,a in rows:
        if op==0x14:
            v=a[0]
            if v in grpe: uses[v].append((sid,pc))
            else: other[v]+=1
print('0x14 non-grpe values', other.most_common(20))
print('grpe used by 0x14:', len(uses), 'of', len(grpe))
unused=sorted(grpe-set(uses)); print('unused', unused)
ch=collections.Counter()
for v,u in uses.items():
    chs=sorted({sc.get(str(s),[ -1])[0] for s,_ in u}); ch[min(chs)]+=1
print('first chapter of grpe CG', sorted(ch.items()))
json.dump({v:u for v,u in uses.items()}, open(r'Y:\AI\forest-4k\grpe_uses.json','w'))

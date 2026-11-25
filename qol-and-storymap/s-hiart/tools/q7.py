import sys, json, collections; sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import gscwalk
inv=json.load(open(r'Y:\AI\forest-4k\inventory_raw.json',encoding='utf-8'))
grpe={int(e['name'][:4]) for e in inv if e['arc']=='grpe.xfl'}
sc={int(k):v for k,v in json.load(open(r'Y:\AI\forest-4k\scenes.json',encoding='utf-8')).items()}
uses=collections.defaultdict(list); varc=collections.Counter()
for sid,p in gscwalk.all_scripts():
    rows,_=gscwalk.read_gsc(p)
    for pc,op,a in rows:
        if op==0x1800 and len(a)==3 and a[2] in grpe: varc[a[1]]+=1
        if (op==0x1800 and len(a)==3 and a[1] in (501,502,503,504,3501,3502,3503,3504,1) and a[2] in grpe) or (op==0x14 and a[0] in grpe):
            v=a[2] if op==0x1800 else a[0]; uses[v].append((sid,pc))
print('vars assigned grpe numbers', varc.most_common(8))
print('grpe covered', len(uses), '/', len(grpe), 'missing', sorted(grpe-set(uses)))
ch=collections.Counter(); first={}
for v,u in uses.items():
    chs=[sc[s][0] if s in sc else -1 for s,_ in u]
    good=[c for c in chs if c>=0]
    first[v]=min(good) if good else -1
    ch[first[v]]+=1
print(sorted(ch.items()))
json.dump({'uses':{v:u for v,u in uses.items()},'first':first}, open(r'Y:\AI\forest-4k\grpe_uses.json','w'))
print('ch0-1:', sorted(v for v,c in first.items() if c in (0,1)))
print('ch2 :', sorted((v,[s for s,_ in uses[v]][:3]) for v,c in first.items() if c==2))

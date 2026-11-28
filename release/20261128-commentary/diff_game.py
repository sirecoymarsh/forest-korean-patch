import os,sys,hashlib
sys.stdout.reconfigure(encoding='utf-8')
O=r'P:\GAME\Forest'; N=r'Y:\AI\forest-cm-v2\game'
def h(p):
    s=os.path.getsize(p); 
    if s>200<<20: return 'size%d'%s
    return hashlib.sha256(open(p,'rb').read()).hexdigest()[:12]
skip=('hiart','save','forest-chart-progress')
new=[];chg=[];
for dp,dn,fn in os.walk(N):
    rel0=os.path.relpath(dp,N)
    if rel0.split(os.sep)[0] in skip: continue
    for f in fn:
        r=os.path.normpath(os.path.join(rel0,f)); o=os.path.join(O,r); n=os.path.join(N,r)
        if not os.path.exists(o): new.append(r)
        elif os.path.getsize(o)!=os.path.getsize(n) or h(o)!=h(n): chg.append(r)
from collections import Counter
print('CHANGED',len(chg)); [print(' ',c, os.path.getsize(os.path.join(N,c))) for c in chg if c.count(os.sep)<1 or not c.startswith(('scr','grp'))]
print(Counter(c.split(os.sep)[0] for c in chg))
print('NEW',len(new)); print(Counter(c.split(os.sep)[0] if os.sep in c else c for c in new))
missing=[]
for dp,dn,fn in os.walk(O):
    for f in fn:
        r=os.path.relpath(os.path.join(dp,f),O)
        if r.split(os.sep)[0] in skip: continue
        if not os.path.exists(os.path.join(N,r)): missing.append(r)
print('ONLY_IN_ORIG',missing[:20],len(missing))

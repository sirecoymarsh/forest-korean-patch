import sys, struct, collections; sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
from fdis import *
text=[s for s in pe.sections if s.Name.startswith(b'.text')][0]
lo=B+text.VirtualAddress; hi=lo+text.Misc_VirtualSize; code=D[lo-B:hi-B]
# function starts = call targets
starts=set()
for j in range(len(code)-5):
    if code[j]==0xe8:
        t=lo+j+5+struct.unpack_from('<i',code,j+1)[0]
        if lo<=t<hi: starts.add(t)
starts=sorted(starts)
md.skipdata=True
stats=[]
for k,s in enumerate(starts):
    e=starts[k+1] if k+1<len(starts) else hi
    if e-s>6000: e=s+6000
    c=collections.Counter()
    for i in md.disasm(D[s-B:e-B], s):
        m=i.mnemonic
        if m in ('imul','mul'): c['mul']+=1
        if m=='movzx' and 'byte' in i.op_str: c['movzxb']+=1
        if m in ('shr','sar') : c['shr']+=1
        if m=='div': c['div']+=1
        if m=='mov' and i.op_str.startswith('byte ptr ['): c['stb']+=1
    score=c['mul']*2+c['movzxb']+c['stb']
    stats.append((score,s,e-s,dict(c)))
stats.sort(reverse=True)
for x in stats[:40]: print(hex(x[1]), x[2], x[3])

import sys, struct, collections; sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
from fdis import *
text=[s for s in pe.sections if s.Name.startswith(b'.text')][0]
lo=B+text.VirtualAddress; hi=lo+text.Misc_VirtualSize
md.detail=False; md.skipdata=True
cnt=collections.Counter(); funcs=collections.defaultdict(collections.Counter)
# linear sweep (approx)
a=lo
code=D[lo-B:hi-B]
for i in md.disasm(code, lo):
    m=i.mnemonic
    if m.startswith('pmul') or m in ('punpcklbw','packuswb','pmaddwd','psrlw','movq','emms'):
        cnt[m]+=1; funcs[i.address & ~0xfff][m]+=1
print(cnt)
for k,v in sorted(funcs.items()): print(hex(k), dict(v))

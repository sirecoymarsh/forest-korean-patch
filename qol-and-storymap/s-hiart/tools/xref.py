import sys, struct; sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
from fdis import *
import capstone
pe2=pe
text=[s for s in pe.sections if s.Name.startswith(b'.text')][0]
lo=B+text.VirtualAddress; hi=lo+text.Misc_VirtualSize
targets=[int(x,16) for x in sys.argv[1:]]
code=D[lo-B:hi-B]
for t in targets:
    pat=struct.pack('<I',t)
    i=0; hits=[]
    while True:
        i=code.find(pat,i)
        if i<0: break
        hits.append(lo+i); i+=1
    # also call rel32
    for j in range(len(code)-5):
        if code[j]==0xe8 or code[j]==0xe9:
            rel=struct.unpack_from('<i',code,j+1)[0]
            if lo+j+5+rel==t: hits.append(-(lo+j))
    print(hex(t), ' '.join(('call@%x'%-h) if h<0 else ('imm@%x'%h) for h in hits[:60]))

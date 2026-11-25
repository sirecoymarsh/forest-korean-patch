import sys, struct; sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
from fdis import *
text=[s for s in pe.sections if s.Name.startswith(b'.text')][0]
lo=B+text.VirtualAddress; hi=lo+text.Misc_VirtualSize; code=D[lo-B:hi-B]
for iat in [int(x,16) for x in sys.argv[1:]]:
    pat=b'\xff\x15'+struct.pack('<I',iat); i=0; hs=[]
    while True:
        i=code.find(pat,i)
        if i<0: break
        hs.append(lo+i); i+=1
    pat2=b'\x8b\x35'+struct.pack('<I',iat); pat3=b'\x8b\x3d'+struct.pack('<I',iat); pat4=b'\x8b\x1d'+struct.pack('<I',iat); pat5=b'\x8b\x2d'+struct.pack('<I',iat)
    for p in (pat2,pat3,pat4,pat5):
        i=0
        while True:
            i=code.find(p,i)
            if i<0: break
            hs.append(-(lo+i)); i+=1
    print(hex(iat), ' '.join(('mov@%x'%-h) if h<0 else ('call@%x'%h) for h in hs))

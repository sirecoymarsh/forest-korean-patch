import sys; sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
from fdis import *
a=int(sys.argv[1],16); n=int(sys.argv[2])
md.skipdata=True
for i in md.disasm(D[a-B:a-B+n], a):
    if i.mnemonic in ('call','ret') or (i.mnemonic=='jmp' and 'ptr' in i.op_str): print('%x: %s %s'%(i.address,i.mnemonic,i.op_str))

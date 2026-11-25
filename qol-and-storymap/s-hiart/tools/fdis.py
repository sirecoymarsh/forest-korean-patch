import pefile, capstone, sys
pe=pefile.PE(r'Y:\AI\forest-qol-test-hiart\game\Forest.exe'); D=pe.get_memory_mapped_image(); B=0x400000
md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
def dis(a, n=60, stop_ret=True):
    out=[]
    for i in md.disasm(D[a-B:a-B+n*8], a):
        out.append('%x: %s %s'%(i.address,i.mnemonic,i.op_str))
        if len(out)>=n or (stop_ret and i.mnemonic=='ret'): break
    return '\n'.join(out)
def u32(a): import struct; return struct.unpack_from('<I',D,a-B)[0]
if __name__=='__main__':
    a=int(sys.argv[1],16); n=int(sys.argv[2]) if len(sys.argv)>2 else 60
    print(dis(a,n, len(sys.argv)<=3))

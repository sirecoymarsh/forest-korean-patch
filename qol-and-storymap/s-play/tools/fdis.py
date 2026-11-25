import sys, pefile, capstone
pe = pefile.PE(r"Y:\AI\forest-qol-test-play\game\Forest.exe")
base = pe.OPTIONAL_HEADER.ImageBase
img = pe.get_memory_mapped_image()
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
def dis(start, count=40, stop_ret=False):
    off = start - base
    code = img[off:off+count*16]
    n=0
    for i in md.disasm(code, start):
        print("%08x: %-24s %s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))
        n+=1
        if n>=count: break
        if stop_ret and i.mnemonic=='ret': break
if __name__=='__main__':
    for a in sys.argv[1:]:
        if ':' in a: s,c=a.split(':'); dis(int(s,16), int(c))
        else: dis(int(a,16), 40)
        print('----')

def xrefs(target, kinds=('call','jmp')):
    text = [s for s in pe.sections if s.Name.startswith(b'.text')][0]
    start = base + text.VirtualAddress; size = text.Misc_VirtualSize
    code = img[text.VirtualAddress:text.VirtualAddress+size]
    out=[]
    # scan e8/e9 rel32
    import struct
    for i in range(len(code)-5):
        op = code[i]
        if op in (0xe8,0xe9):
            rel = struct.unpack_from('<i', code, i+1)[0]
            if start+i+5+rel == target: out.append(start+i)
    return out
def immrefs(value):
    import struct
    text = [s for s in pe.sections if s.Name.startswith(b'.text')][0]
    start = base + text.VirtualAddress; size = text.Misc_VirtualSize
    code = img[text.VirtualAddress:text.VirtualAddress+size]
    pat = struct.pack('<I', value)
    out=[]; i=code.find(pat)
    while i>=0: out.append(start+i); i=code.find(pat,i+1)
    return out

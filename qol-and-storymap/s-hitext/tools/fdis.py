# Forest.exe 정적 분석 도우미: imports, xref, 함수 역어셈블
import sys, pefile, capstone, re, struct
EXE = r"Y:\AI\forest-qol-test-hitext\game\Forest.exe"
pe = pefile.PE(EXE)
base = pe.OPTIONAL_HEADER.ImageBase
img = pe.get_memory_mapped_image()
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
def imports():
    d = {}
    for e in pe.DIRECTORY_ENTRY_IMPORT:
        for i in e.imports:
            if i.name: d[i.name.decode()] = i.address
    return d
def read(va, n): return img[va-base: va-base+n]
def dis(va, n=200, stop_ret=True, maxins=400):
    out=[]
    code = read(va, n*1)
    for ins in md.disasm(code, va):
        out.append(ins)
        if len(out)>=maxins: break
        if stop_ret and ins.mnemonic=='ret': break
    return out
text = [s for s in pe.sections if s.Name.startswith(b'.text')][0]
tva = base + text.VirtualAddress; tsz = text.Misc_VirtualSize
tcode = read(tva, tsz)
def xref_iat(iat):
    # call dword ptr [iat] = FF 15 iat ; mov reg,[iat] = 8B 05/1D/0D/15/35/3D iat; jmp [iat] FF 25
    pat = struct.pack('<I', iat)
    res=[]
    for m in re.finditer(re.escape(pat), tcode):
        res.append(tva + m.start() - 2)
    return res
def xref_call(target):
    res=[]
    for i in range(len(tcode)-5):
        if tcode[i]==0xE8:
            rel = struct.unpack_from('<i', tcode, i+1)[0]
            if tva+i+5+rel == target: res.append(tva+i)
    return res
def xref_imm(val):
    pat = struct.pack('<I', val); res=[]
    for m in re.finditer(re.escape(pat), tcode): res.append(tva+m.start())
    return res
def p(va, n=400, maxins=200, stop=True):
    for ins in dis(va, n, stop, maxins):
        print(f"{ins.address:08x}  {ins.bytes.hex():20s} {ins.mnemonic} {ins.op_str}")
if __name__=='__main__':
    cmd=sys.argv[1]
    if cmd=='imp':
        for k,v in sorted(imports().items(), key=lambda x:x[1]):
            if len(sys.argv)<3 or re.search(sys.argv[2], k): print(hex(v), k)
    elif cmd=='xiat':
        im=imports()
        for name in sys.argv[2:]:
            print(name, hex(im[name]), [hex(x) for x in xref_iat(im[name])])
    elif cmd=='xcall':
        for t in sys.argv[2:]: print(t, [hex(x) for x in xref_call(int(t,16))])
    elif cmd=='ximm':
        for t in sys.argv[2:]: print(t, [hex(x) for x in xref_imm(int(t,16))])
    elif cmd=='dis':
        va=int(sys.argv[2],16); n=int(sys.argv[3]) if len(sys.argv)>3 else 60
        stop = (sys.argv[4]!='0') if len(sys.argv)>4 else True
        p(va, n*8, n, stop)
    elif cmd=='str':
        s=sys.argv[2].encode()
        data=img
        for m in re.finditer(re.escape(s), data): print(hex(base+m.start()), data[m.start()-8:m.start()+40])

def func_start(va):
    # 거꾸로 훑어 CC/C3 패딩 뒤 첫 바이트(대개 함수 시작)
    i = va - tva
    while i>0:
        if tcode[i-1] in (0xCC,) and tcode[i] not in (0xCC,): return tva+i
        if tcode[i-1]==0xC3 and tcode[i] in (0x55,0x83,0x81,0x6A,0x53,0x56,0x57,0x8B,0x51,0x64,0xA1,0xB8): 
            return tva+i
        i-=1
    return None
if __name__=='__main__' and sys.argv[1]=='fs':
    for t in sys.argv[2:]: print(t, hex(func_start(int(t,16))))

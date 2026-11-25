# 사용: python dis.py <exe> <시작 hex> <끝 hex>  — capstone 역어셈블
import sys, pefile, capstone
pe = pefile.PE(sys.argv[1]); base = pe.OPTIONAL_HEADER.ImageBase
img = pe.get_memory_mapped_image()
a, b = int(sys.argv[2], 16), int(sys.argv[3], 16)
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32); md.skipdata = True
for i in md.disasm(img[a - base:b - base], a):
    print('%08x  %-24s %s %s' % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))

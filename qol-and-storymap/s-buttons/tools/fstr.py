import sys, pefile
pe = pefile.PE(sys.argv[1]); base = pe.OPTIONAL_HEADER.ImageBase
img = pe.get_memory_mapped_image()
for s in sys.argv[2:]:
    a = int(s, 16); e = img.index(b'\0', a - base)
    print(hex(a), img[a - base:e].decode('cp932', 'replace'))

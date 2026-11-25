import pefile, re, sys
pe=pefile.PE(r'Y:\AI\forest-qol-test-hiart\game\Forest.exe')
data=pe.get_memory_mapped_image(); base=pe.OPTIONAL_HEADER.ImageBase
for m in re.finditer(rb'[\x20-\x7e]{3,}\x00', data):
    s=m.group()[:-1]
    if re.search(rb'(?i)grp|wcg|lwg|msk|xfl|%0|\.bmp|bg|bu|ci', s) and len(s)<60:
        print(hex(base+m.start()), s.decode())

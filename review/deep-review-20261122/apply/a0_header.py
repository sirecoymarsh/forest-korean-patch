# -*- coding: utf-8 -*-
"""GSC 머리(u32 7개)와 구역 크기의 관계를 104개 전부에서 잰다. 숫자만 출력."""
import os, sys, glob, struct, collections
DST = r'Y:\AI\forest-deep-review\applied_20261122\scr'
rel = collections.Counter(); odd = []
for p in sorted(glob.glob(os.path.join(DST, '*.gsc'))):
    d = open(p, 'rb').read(); n = len(d)
    h = struct.unpack_from('<7I', d, 0)
    tp = h[1] + h[2]; cnt = h[3] // 4; base = tp + h[3]
    offs = struct.unpack_from('<%dI' % cnt, d, tp) if cnt else ()
    # 문자열 구역 끝: 마지막 문자열의 NUL 다음
    if cnt:
        end = d.index(b'\0', base + offs[-1]) + 1
        mono = all(offs[k] < offs[k + 1] for k in range(cnt - 1))
        # 연속 배치인가: 각 오프셋 = 앞 문자열 끝 + 1
        contig = True; q = base + offs[0]
        for k in range(cnt):
            if base + offs[k] != q: contig = False; break
            q = d.index(b'\0', q) + 1
    else:
        end = base; mono = contig = True
    blob = end - base; tail = n - end
    facts = (h[1] == 28, h[0] == n, h[0] == n - h[6], h[4] == blob, h[4] == blob + (offs[0] if cnt else 0), tail == h[5] + h[6], tail == h[6], mono, contig, (offs[0] if cnt else -1))
    rel[facts] += 1
    if os.path.basename(p) in ('0000.gsc', '2100.gsc', '2600.gsc') or not (mono and contig):
        odd.append((os.path.basename(p), n, h, 'tp', tp, 'cnt', cnt, 'base', base, 'blob', blob, 'tail', tail, 'first_off', offs[0] if cnt else None))
print('(h1=28, h0=크기, h0=크기-h6, h4=문자열구역, h4=구역+첫오프셋, 꼬리=h5+h6, 꼬리=h6, 단조, 연속, 첫 오프셋) → 파일 수')
for k, v in rel.most_common(): print('  ', k, v)
for o in odd: print(o)

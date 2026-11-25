# -*- coding: utf-8 -*-
"""hiart-trace/trace.bin 읽기. 기록 = 'tick D 번호 개수\r\n' + Rec*개수 / 'tick T 글\r\n'."""
import struct, sys, os
REC = 4 + 64 + 0x364 + 0x10c + 4 * 5 + 32
TR = r'Y:\AI\forest-qol-test-hiart\game\forest-chart-progress\hiart-trace'


def read(path=os.path.join(TR, "trace.bin"), rec=None):
    rec = rec or REC
    d = open(path, 'rb').read()
    i = 0; out = []
    while i < len(d):
        j = d.index(b'\r\n', i)
        line = d[i:j].decode('latin1'); i = j + 2
        parts = line.split(' ', 3)
        tick, kind = int(parts[0]), parts[1]
        if kind == 'T':
            out.append(('T', tick, parts[2] + (' ' + parts[3] if len(parts) > 3 else '')))
        else:
            num, cnt = int(parts[2]), int(parts[3].split()[0])
            clip = parts[3].split()[1] if len(parts[3].split()) > 1 else ''
            recs = []
            for k in range(cnt):
                r = d[i:i + rec]; i += rec
                idx = struct.unpack_from('<i', r, 0)[0]
                path = r[4:68].split(b'\0')[0].decode('latin1')
                x = {'idx': idx, 'path': path, 'L': r[68:68 + 0x364], 'I': r[68 + 0x364:68 + 0x364 + 0x10c]}
                if rec > 68 + 0x364 + 0x10c:
                    o = 68 + 0x364 + 0x10c
                    x['sioff'], x['w'], x['h'], x['bits'], x['hash'] = struct.unpack_from('<iiiII', r, o)
                    x['px'] = struct.unpack_from('<8I', r, o + 20)
                recs.append(x)
            out.append(('D', tick, num, recs, clip))
    return out


def u32(b, o): return struct.unpack_from('<I', b, o)[0]
def i32(b, o): return struct.unpack_from('<i', b, o)[0]


if __name__ == '__main__':
    ev = read()
    for e in ev[:int(sys.argv[1]) if len(sys.argv) > 1 else 50]:
        if e[0] == 'T': print(e[1], e[2])
        else: print(e[1], 'D', e[2], [(r['idx'], r['path']) for r in e[3]])

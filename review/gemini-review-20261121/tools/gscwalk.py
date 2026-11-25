# -*- coding: utf-8 -*-
"""Forest GSC 명령부를 명령 길이표(코덱스 opcode_layouts.json)로 정확히 걷는다.

walk(path) -> (cmds, strings)
  cmds: [(pc, op, args)]  args 는 정수 목록(V 는 u32 그대로, H 는 u16)
  strings: 슬롯 → bytes
"""
import json, struct

LAYOUT = json.load(open(r'P:\AI\Codex\projects\forest-flowchart\data\opcode_layouts.json', encoding='utf-8-sig'))
LAYOUT['155'] = ['V', 'V']          # 코덱스 extract_flow.py 와 같음
SIZE = {'H': 2, 'h': 2, 'I': 4, 'V': 4}


def strings_of(d):
    h = struct.unpack_from('<7I', d, 0)
    tp = h[1] + h[2]
    n = h[3] // 4
    base = tp + h[3]
    offs = struct.unpack_from('<%dI' % n, d, tp)
    out = []
    for o in offs:
        p = base + o
        e = d.index(b'\0', p)
        out.append(d[p:e])
    return out


def walk(path):
    d = open(path, 'rb').read()
    h = struct.unpack_from('<7I', d, 0)
    A, size = h[1], h[2]
    code = d[A:A + size]
    cmds = []
    i = 0
    while i < len(code):
        op = struct.unpack_from('<H', code, i)[0]
        if op & 0xF000:                 # 식 명령(코덱스 extract_flow.py 규칙)
            lay = ['H', 'h'] if op & 0xF000 == 0xF000 else ['H', 'h', 'h']
        else:
            lay = LAYOUT.get(str(op))
        if lay is None:
            raise ValueError('unknown op 0x%x at pc 0x%x in %s' % (op, i, path))
        j = i + 2
        args = []
        for t in lay:
            if t == 'H':
                args.append(struct.unpack_from('<H', code, j)[0])
            elif t == 'h':
                args.append(struct.unpack_from('<h', code, j)[0])
            else:
                args.append(struct.unpack_from('<I', code, j)[0])
            j += SIZE[t]
        cmds.append((i, op, args))
        i = j
    return cmds, strings_of(d)

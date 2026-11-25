# -*- coding: utf-8 -*-
"""GSC 명령 걷기(코덱스 forest-flowchart extract_flow.read_gsc 를 옮김) + 그림 명령 찾기."""
import struct, json, os, sys, collections
LAYOUTS = {int(k): v for k, v in json.load(open(r'P:\AI\Codex\projects\forest-flowchart\data\opcode_layouts.json', encoding='utf-8-sig')).items()}
LAYOUTS[155] = ['V', 'V']
JA = r'P:\AI\forest-kr-build\ja_scr'


def read_gsc(path, encoding='cp932'):
    raw = open(path, 'rb').read()
    h = struct.unpack_from('<7I', raw)
    code = raw[28:28 + h[2]]
    table = 28 + h[2]
    base = table + h[3]
    offsets = struct.unpack_from('<%dI' % (h[3] // 4), raw, table)
    strings = []
    for o in offsets:
        end = raw.find(b'\0', base + o)
        strings.append(raw[base + o:end].decode(encoding, errors='replace'))
    rows = []
    pc = 0
    while pc < len(code):
        start = pc
        op = struct.unpack_from('<H', code, pc)[0]
        pc += 2
        if op & 0xf000:
            layout = ['H', 'h'] if op & 0xf000 == 0xf000 else ['H', 'h', 'h']
        else:
            layout = LAYOUTS[op]
        args = []
        for kind in layout:
            fmt = 'I' if kind == 'V' else kind
            args.append(struct.unpack_from('<' + fmt, code, pc)[0])
            pc += struct.calcsize(fmt)
        rows.append((start, op, args))
    return rows, strings


def all_scripts():
    for n in sorted(os.listdir(JA)):
        if n.endswith('.gsc'):
            yield int(n[:4]), os.path.join(JA, n)


if __name__ == '__main__':
    inv = json.load(open(r'Y:\AI\forest-4k\inventory_raw.json', encoding='utf-8'))
    names = collections.defaultdict(set)
    for e in inv:
        names[e['arc']].add(int(e['name'][:4]) if e['name'][:4].isdigit() else -1)
    stat = collections.defaultdict(lambda: collections.Counter())
    cnt = collections.Counter()
    for sid, p in all_scripts():
        rows, _ = read_gsc(p)
        for pc, op, args in rows:
            if op & 0xf000:
                continue
            cnt[op] += 1
            for ai, v in enumerate(args):
                for arc, s in names.items():
                    if v in s and v > 0:
                        stat[(op, ai)][arc] += 1
    for (op, ai), c in sorted(stat.items()):
        if sum(c.values()) >= 20:
            print('op 0x%02x arg%d  n=%d  %s' % (op, ai, cnt[op], dict(c)))

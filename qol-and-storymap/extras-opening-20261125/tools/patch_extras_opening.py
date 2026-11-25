# -*- coding: utf-8 -*-
"""scr/0001.gsc 특전 메뉴에 「오프닝」 항목을 넣는다.
- 슬롯 15 = 오프닝(그림 1010/1110, y 384, 값 5), 「뒤로」(슬롯 14)는 y 423 으로 내림.
- 원래 862 의 OP_0024 [15,0](슬롯 15 지우기)을 그 자리에서 오프닝 단추 정의로 바꾼다.
- 고른 값이 5 면: OP_003D [1](다른 특전 화면 첫 명령과 같음) → OP_0041 [1](엔진 영상 명령, mov\\0001.mpg) → LOAD_SCRIPT [1](특전 화면을 닫을 때와 같은 길).
python patch_extras_opening.py <원래 0001.gsc> <출력 0001.gsc>
"""
import struct, sys, json, hashlib
sys.path.insert(0, r'P:\AI\Codex\projects\forest-flowchart\scripts')
import extract_flow as E
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
raw = src.read_bytes()
h = list(struct.unpack_from('<7I', raw))
code = raw[28:28 + h[2]]
rest = raw[28 + h[2]:]
info = E.read_gsc(src, 'cp949')
cmds = info['commands']
by_off = {c['offset']: c for c in cmds}

def chunk(c):
    return bytearray(code[c['offset']:c['offset'] + c['size']])

def w16(b, pos, v):
    struct.pack_into('<H', b, pos, v & 0xffff)

def wv(b, i, v):
    struct.pack_into('<I', b, 2 + 4 * i, v)

# 확인: 예상한 자리
assert by_off[862]['op'] == 0x24 and by_off[862]['args'] == [15, 0]
assert by_off[800]['op'] == 0x1E and by_off[800]['args'][:4] == [14, 1009, 515, 384]
assert by_off[826]['op'] == 0x4B and by_off[826]['args'] == [14, 1109, 515, 384]
assert by_off[1000]['name'] == 'EXPR' and by_off[1014]['op'] == 3 and by_off[1014]['args'] == [1026]
assert by_off[1026]['op'] == 8 and cmds[-1]['offset'] == 1026

out = []        # (원래 offset 또는 None, bytes, 뛰는 곳을 고칠지)
for c in cmds:
    b = chunk(c)
    off = c['offset']
    if off == 800:   # 뒤로 = y 423
        wv(b, 3, 423)
    elif off == 826:
        wv(b, 3, 423)
    if off == 862:
        # 슬롯 15 오프닝 단추: 슬롯 14 정의 3줄(800·826·844)을 본떠 값만 바꿈
        b1 = chunk(by_off[800]); wv(b1, 0, 15); wv(b1, 1, 1010); wv(b1, 3, 384)
        b2 = chunk(by_off[826]); wv(b2, 0, 15); wv(b2, 1, 1110); wv(b2, 3, 384)
        b3 = chunk(by_off[844]); wv(b3, 0, 15); wv(b3, 1, 5)
        out.append((None, bytes(b1), False)); out.append((None, bytes(b2), False)); out.append((None, bytes(b3), False))
        continue
    if off == 1026:
        # 값 5 비교 + 오프닝 + 타이틀로
        e1 = chunk(by_off[1000])              # EXPR [1,0,4]
        assert by_off[1000]['args'] == [1, 0, 4]
        e1 = bytes(e1).replace(struct.pack('<h', 4), struct.pack('<h', 5), 1) if False else e1
        # EXPR 인자 셋째(상수)를 5 로: 같은 비교 블록 1000 의 바이트에서 상수 자리를 찾는다
        layout_pos = None
        for p in range(2, len(e1) - 1, 2):
            if struct.unpack_from('<h', e1, p)[0] == 4: layout_pos = p
        assert layout_pos is not None
        w16(e1, layout_pos, 5)
        out.append(('L5', bytes(e1), False))
        out.append((None, bytes(chunk(by_off[1008])), False))      # EXPR [0,1]
        jz = chunk(by_off[1014]); out.append(('JZ', bytes(jz), True))   # JUMP_IF_ZERO -> STOP (고침)
        out.append((None, struct.pack('<HI', 0x3D, 1), False))     # OP_003D [1]
        out.append((None, struct.pack('<HI', 0x41, 1), False))     # OP_0041 [1]
        ls = chunk([c2 for c2 in cmds if c2['op'] == 12][0]); struct.pack_into('<I', ls, 2, 1)
        out.append((None, bytes(ls), False))                        # LOAD_SCRIPT [1]
        out.append(('STOP', bytes(b), False))
        continue
    out.append((off, bytes(b), True))

# 새 위치 계산
newpos = {}; pos = 0; marks = {}
for key, b, _ in out:
    if isinstance(key, int): newpos[key] = pos
    elif key: marks[key] = pos
    pos += len(b)
newpos[1026] = marks['L5']          # 옛 「값 4 아님 → STOP」 이 이제 값 5 비교로
code_end = pos

# 뛰는 곳 고치기
fixed = bytearray()
for key, b, fix in out:
    b = bytearray(b)
    op = struct.unpack_from('<H', b, 0)[0]
    if fix and op in (3, 4, 5):
        t = struct.unpack_from('<I', b, 2)[0]
        if key == 'JZ':
            nt = marks['STOP']
        else:
            assert t in newpos, t
            nt = newpos[t]
        struct.pack_into('<I', b, 2, nt)
    if fix and op == 14:
        raise SystemExit('CHOICE 는 이 대본에 없어야 함')
    fixed += b
assert len(fixed) == code_end
delta = len(fixed) - h[2]
h[2] = len(fixed); h[0] += delta
newraw = struct.pack('<7I', *h) + bytes(fixed) + rest
assert len(newraw) == sum(h[1:]) + h[6]
dst.write_bytes(newraw)
chk = E.read_gsc(dst, 'cp949')
for c in chk['commands'][-40:]:
    print(c['offset'], c['name'], c['args'])
print('size', len(raw), '->', len(newraw), 'code sha', hashlib.sha256(bytes(fixed)).hexdigest()[:12])

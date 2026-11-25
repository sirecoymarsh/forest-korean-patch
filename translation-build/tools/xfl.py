# -*- coding: utf-8 -*-
"""XFL 아카이브 판독기 (Forest / GsWin 계열).

2026-08-14 재해독. 원래 파이프라인의 adapter\\extract_xfl_entries.py 가 소실되어
scr.xfl(103개 GSC 파일명을 이미 알고 있어 검증이 확실한 쪽)로 포맷을 다시 뜯었다.

  0x00  char  magic[4]      "LB\\x01\\x00"
  0x04  u32   index_size    = count * 40
  0x08  u32   count
  0x0C  entry[count]        char name[32]; u32 offset; u32 size
        data                offset 는 (0x0C + index_size) 기준 상대값

  python xfl.py list  <archive> [패턴]        목록
  python xfl.py get   <archive> <이름> <출력>  하나 꺼내기
  python xfl.py index <archive> <번호> <출력>  번호로 꺼내기(voice 처럼 이름이 번호일 때)
"""
import sys, io, os, struct

HDR = 12
ENT = 40


def read_index(path):
    """[(name, abs_offset, size)] 반환. 데이터는 읽지 않는다(대용량 대비)."""
    with open(path, 'rb') as f:
        head = f.read(HDR)
        if head[:2] != b'LB':
            raise ValueError(f'XFL 매직 불일치: {head[:4]!r}')
        index_size, count = struct.unpack_from('<II', head, 4)
        if index_size != count * ENT:
            raise ValueError(f'인덱스 크기 불일치: {index_size} != {count}*{ENT}')
        raw = f.read(index_size)
    base = HDR + index_size
    out = []
    for i in range(count):
        rec = raw[i * ENT:(i + 1) * ENT]
        name = rec[:32].split(b'\x00', 1)[0].decode('cp932', 'replace')
        off, size = struct.unpack_from('<II', rec, 32)
        out.append((name, base + off, size))
    return out


def extract(path, entry):
    _, off, size = entry
    with open(path, 'rb') as f:
        f.seek(off)
        return f.read(size)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    cmd, arc = sys.argv[1], sys.argv[2]
    idx = read_index(arc)

    if cmd == 'list':
        pat = sys.argv[3] if len(sys.argv) > 3 else ''
        hit = [e for e in idx if pat in e[0]]
        print(f'{os.path.basename(arc)}: 전체 {len(idx)}개 / 일치 {len(hit)}개')
        for n, o, s in hit[:60]:
            print(f'  {n:34s} off {o:10d}  size {s:9d}')
        if len(hit) > 60:
            print(f'  … 외 {len(hit)-60}개')

    elif cmd == 'get':
        name, out = sys.argv[3], sys.argv[4]
        e = next((x for x in idx if x[0] == name), None)
        if not e:
            print(f'없음: {name}')
            return
        os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
        open(out, 'wb').write(extract(arc, e))
        print(f'{name} -> {out}  ({e[2]} bytes)')

    elif cmd == 'index':
        i, out = int(sys.argv[3]), sys.argv[4]
        if not 0 <= i < len(idx):
            print(f'범위 밖: {i} (0~{len(idx)-1})')
            return
        os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
        open(out, 'wb').write(extract(arc, idx[i]))
        print(f'[{i}] {idx[i][0]} -> {out}  ({idx[i][2]} bytes)')

    else:
        print(__doc__)


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main()

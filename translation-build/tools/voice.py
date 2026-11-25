# -*- coding: utf-8 -*-
"""voice.xfl 에서 음성을 꺼내 바로 들을 수 있는 .ogg 로 저장한다.

voice.xfl 항목은 `NNNN.wav` 6,134개이고 내용은 **Vorbis-in-WAV**(코덱 0x6771)다.
**RIFF 헤더만 벗겨서는 안 된다** — data 청크 안에 빈 더미 스트림이 섞여 있어
브라우저에서 조금 재생되다 멈춘다. `oggfix.convert()` 로 진짜 스트림만 골라낸다.

  python voice.py 3732                 -> voice_out\\3732.ogg
  python voice.py 3730 3735            범위
  python voice.py 3732 --name 아기돼지  파일명에 메모 붙이기

주의: 아카이브의 **인덱스 위치와 파일명 번호가 다르다.** 반드시 이름(`%04d.wav`)으로 찾는다.
"""
import sys, io, os, struct

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xfl import read_index, extract  # noqa: E402
from oggfix import convert as ogg_convert  # noqa: E402

ARC = r"P:\GAME\Forest\voice.xfl"
OUT = r"P:\AI\forest-kr-build\voice_out"


def save(idx, n, note=''):
    name = f'{n:04d}.wav'
    e = next((x for x in idx if x[0] == name), None)
    if not e:
        print(f'  {n:5d} 없음')
        return None
    try:
        data = ogg_convert(extract(ARC, e))
    except Exception as exc:
        print(f'  {n:5d} 변환 실패: {exc}')
        return None
    os.makedirs(OUT, exist_ok=True)
    tag = f'_{note}' if note else ''
    path = os.path.join(OUT, f'{n:04d}{tag}.ogg')
    open(path, 'wb').write(data)
    print(f'  {n:5d} -> {os.path.basename(path)}  ({len(data)} bytes)')
    return path


def main():
    argv = sys.argv[1:]
    note = ''
    if '--name' in argv:
        k = argv.index('--name')
        note = argv[k + 1] if k + 1 < len(argv) else ''
        argv = argv[:k] + argv[k + 2:]
    args = [a for a in argv if not a.startswith('--')]
    if not args:
        print(__doc__)
        return
    lo = int(args[0])
    hi = int(args[1]) if len(args) > 1 else lo
    idx = read_index(ARC)
    print(f'voice.xfl 항목 {len(idx)}개 / 추출 {lo}~{hi}')
    for n in range(lo, hi + 1):
        save(idx, n, note)


main()

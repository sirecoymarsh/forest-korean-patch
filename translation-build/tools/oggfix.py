# -*- coding: utf-8 -*-
"""게임이 WAV 안에 넣어 둔 Vorbis 스트림을 **브라우저에서 재생되는 Ogg** 로 꺼낸다.

증상: RIFF 헤더만 벗겨 .ogg 로 저장하면 브라우저에서 조금 재생되다 멈춘다.

원인: WAV(Vorbis 코덱 0x6771)의 data 청크 안에 **논리 Ogg 스트림이 둘** 들어 있다.

    serial 0x00000000   36페이지  본문 116,379  granule 355,671  EOS 있음   <- 진짜
    serial 0xFFFFFFFF  533페이지  본문 0        granule 0        EOS 없음   <- 더미

더미는 본문이 0바이트인 빈 페이지가 실제 오디오 페이지 사이사이에 끼워져 있다.
그대로 저장하면 디코더가 두 스트림을 만나 멈춘다.

해결: **진짜 스트림의 페이지만 남긴다.** 재조립·granule 재계산은 필요 없다 —
진짜 스트림은 granule 도 EOS 도 처음부터 정상이다.

검증: WAV 의 `fact` 청크가 총 표본 수이고, 진짜 스트림의 마지막 granule 과 같아야 한다.

  python oggfix.py <입력.wav> <출력.ogg>
"""
import sys, io, os, struct, collections


def split_streams(data):
    """Ogg 페이지를 훑어 serial 별로 (시작, 끝, flags, granule, 본문크기) 를 모은다."""
    by = collections.defaultdict(list)
    pos = 0
    while pos + 27 <= len(data) and data[pos:pos + 4] == b'OggS':
        ns = data[pos + 26]
        if pos + 27 + ns > len(data):
            break
        body = sum(data[pos + 27:pos + 27 + ns])
        end = pos + 27 + ns + body
        if end > len(data):
            break
        serial = struct.unpack_from('<I', data, pos + 14)[0]
        granule = int.from_bytes(data[pos + 6:pos + 14], 'little', signed=True)
        by[serial].append((pos, end, data[pos + 5], granule, body))
        pos = end
    return by


def riff_chunks(wav):
    out, p = {}, 12
    while p + 8 <= len(wav):
        cid = wav[p:p + 4]
        sz = struct.unpack_from('<I', wav, p + 4)[0]
        out[cid] = wav[p + 8:p + 8 + sz]
        p += 8 + sz + (sz & 1)
    return out


def convert(wav):
    """Vorbis-in-WAV -> 재생 가능한 Ogg."""
    ch = riff_chunks(wav)
    if b'data' not in ch:
        raise ValueError('data 청크가 없다')
    data = ch[b'data']
    fact = struct.unpack_from('<I', ch[b'fact'], 0) [0] if b'fact' in ch else None

    by = split_streams(data)
    if not by:
        raise ValueError('Ogg 페이지를 찾지 못했다')
    # 진짜 스트림 = 본문이 있는 쪽
    real = max(by.items(), key=lambda kv: sum(x[4] for x in kv[1]))
    serial, pages = real
    if sum(x[4] for x in pages) == 0:
        raise ValueError('본문 있는 스트림이 없다')

    out = b''.join(data[a:b] for a, b, *_ in pages)
    last = pages[-1]
    if fact is not None and last[3] != fact:
        raise ValueError(f'granule 검증 실패: 마지막 {last[3]} != fact {fact}')
    if not (last[2] & 0x04):
        raise ValueError('마지막 페이지에 EOS 플래그가 없다')
    return out


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if len(sys.argv) < 3:
        print(__doc__)
        return
    wav = open(sys.argv[1], 'rb').read()
    ogg = convert(wav)
    open(sys.argv[2], 'wb').write(ogg)
    print(f'{os.path.basename(sys.argv[1])} -> {os.path.basename(sys.argv[2])}'
          f'  ({len(wav)} -> {len(ogg)} bytes)')


if __name__ == '__main__':
    main()

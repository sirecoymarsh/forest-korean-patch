# -*- coding: utf-8 -*-
"""Forest GSC 읽고 다시 쓰기 — 머리 값으로 구역을 정한다(추측으로 표를 찾지 않는다).

파일 = 머리 28바이트(u32 7개) | 명령부 h2 | 문자열 오프셋 표 h3(u32 × N) | 문자열 구역 h4(NUL 종단, 연속) | 꼬리(h5 + 2*h6)
104개 전부에서 확인한 것(a0_header.py·a0b_convention.py):
  h1 = 28, 표 위치 = h1 + h2, N = h3 / 4, 문자열 구역 크기 = h4, 첫 오프셋 0, 오프셋은 연속
  파일 크기 = 28 + h2 + h3 + h4 + h5 + 2*h6
  h0 은 파일마다 「파일 크기」(60개 — 영문 패치·플레이해 온 한국어판도 같은 꼴)이거나 「파일 크기 - h6」(44개, 일본어 원본 꼴)
→ 문자열을 바꾸면 늘어난 만큼 h0 과 h4 에 더한다(파일마다의 h0 꼴이 그대로 지켜진다). 나머지 바이트는 그대로 옮긴다."""
import struct


def parse(raw):
    h = list(struct.unpack_from('<7I', raw, 0))
    assert h[1] == 28, h
    tp = h[1] + h[2]; cnt = h[3] // 4; base = tp + h[3]
    offs = struct.unpack_from('<%dI' % cnt, raw, tp) if cnt else ()
    strings = []; q = base
    for o in offs:
        p = base + o
        assert p == q, '문자열이 연속 배치가 아님'
        e = raw.index(b'\0', p); strings.append(raw[p:e]); q = e + 1
    blob_end = base + h[4]
    assert q == blob_end, ('문자열 구역 끝이 h4 와 다름', q, blob_end)
    assert len(raw) == 28 + h[2] + h[3] + h[4] + h[5] + 2 * h[6], '파일 크기 식이 안 맞음'
    return {'head': h, 'table_pos': tp, 'count': cnt, 'base': base, 'strings': strings, 'blob_end': blob_end}


def rebuild(raw, strings):
    g = parse(raw)
    if len(strings) != g['count']:
        raise ValueError('문자열 개수가 다름: %d != %d' % (len(strings), g['count']))
    blob = bytearray(); offs = []
    for s in strings:
        if b'\0' in s: raise ValueError('문자열 안에 NUL')
        offs.append(len(blob)); blob += s + b'\0'
    out = bytearray(raw[:g['table_pos']])
    out += struct.pack('<%dI' % g['count'], *offs)
    out += blob
    out += raw[g['blob_end']:]
    h = list(g['head']); delta = len(blob) - h[4]
    h[0] += delta; h[4] += delta
    struct.pack_into('<7I', out, 0, *h)
    return bytes(out)

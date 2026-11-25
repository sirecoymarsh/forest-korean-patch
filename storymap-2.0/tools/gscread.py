# -*- coding: utf-8 -*-
"""Forest GSC 읽기 (머리글 기준).

머리글 u32 7개: [0]=파일크기-[6], [1]=28(명령부 시작), [2]=명령부 크기,
[3]=오프셋 표 크기(=4*문자열 수), [4]=문자열 덩어리 크기, [5][6]=꼬리 표.
표 위치 = 28+[2], 문자열 수 = [3]/4, 덩어리 시작 = 28+[2]+[3].
P:\\AI\\forest-kr-build\\tools\\gsc.py 는 표를 훑어서 찾는데, 문자열이 하나뿐인
0001.gsc 에서는 엉뚱한 자리를 잡는다. 머리글로 읽으면 103개 모두 맞는다.
"""
import struct, hashlib


class Gsc:
    def __init__(self, raw, encoding='cp949'):
        self.raw = raw
        h = struct.unpack_from('<7I', raw, 0)
        self.head = h
        self.code_start = h[1]
        self.code = raw[h[1]:h[1] + h[2]]
        tp = h[1] + h[2]
        n = h[3] // 4
        base = tp + h[3]
        offs = struct.unpack_from('<%dI' % n, raw, tp)
        out = []
        for o in offs:
            p = base + o
            e = raw.index(b'\0', p)
            out.append(raw[p:e])
        self.raw_strings = out
        self.strings = [s.decode(encoding, 'replace') for s in out]

    def code_sha256(self):
        return hashlib.sha256(self.code).hexdigest()


def load(path, encoding='cp949'):
    with open(path, 'rb') as f:
        return Gsc(f.read(), encoding)

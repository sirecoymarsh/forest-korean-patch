# -*- coding: utf-8 -*-
"""GSC 스크립트 판독·재조립 (Forest / GsWin 계열).

2026-08-14 재해독. 원래 파이프라인의 gsc_codec 이 소실되어 다시 썼다.

파일 끝에 **문자열 구역**이 있고 그 앞에 **오프셋 표**가 붙는다:

    … 명령부 … | u32 offset[N] | 문자열 블롭(NUL 종단, cp949/cp932)
                 ^table_pos      ^base = table_pos + 4*N
    슬롯 k 의 문자열 = base + offset[k] 부터 NUL 까지

헤더는 u32 7개인데 전부 해독하지는 못했다. 확실한 것만 쓴다:
    h[0] = 파일 크기 - h[6]      (h[6] 은 꼬리 구역 크기, 103개 전건 성립)
    h[1] = 28  (명령부 시작)
    h[4] = 문자열 구역 안쪽을 가리키며 파일 크기와 같은 폭으로 움직인다
           -> 문자열이 늘어난 만큼 더해 준다

**표 위치는 실측으로 찾는다.** 헤더 필드로 유도하려 했으나 파일마다 관계가 달라
포기했고, 대신 후보 위치를 훑어 ①오프셋이 단조증가 ②각 오프셋 앞이 NUL(또는 base)
③마지막 문자열이 파일 끝에서 끝남 을 모두 만족하는 자리를 고른다.
103개 전건에서 유일해로 잡히는지 self-test 로 확인한다.

    python gsc.py test <dir>     디렉터리 전체 왕복 무변경 검증
    python gsc.py dump <file> [슬롯]
"""
import sys, io, os, struct, glob

HDR_N = 7


class Gsc:
    __slots__ = ('raw', 'head', 'table_pos', 'count', 'base', 'offsets', 'strings', '_nul_cache')

    def __init__(self, raw):
        self.raw = raw
        self.head = list(struct.unpack_from('<%dI' % HDR_N, raw, 0))
        self._locate()

    def _locate(self):
        """오프셋 표와 문자열 구역을 실측으로 찾는다.

        문자열은 연속 배치이므로 **base 하나만 정하면 오프셋이 전부 결정된다.**
        그래서 base 후보(= NUL 바로 뒤)마다 오프셋을 계산해 실제 표 바이트와
        통째로 대조한다. 표 위치는 base - 4*개수 이고, 4바이트 정렬이 아니다.
        """
        raw = self.raw
        n = len(raw)
        lo = self.head[1]
        # 표는 선두가 0 또는 1이고 이후 단조증가한다. 그런 자리를 앞에서부터 훑되,
        # 각 후보마다 **항목 수 N을 풀어서** 검증한다: base = tp + 4N 이므로
        # base 부터 문자열을 NUL 단위로 걸어 만든 오프셋 열이 표 바이트와
        # 통째로 같아야 하고, 걸음이 구역 끝에서 정확히 멈춰야 한다.
        # 작은 우연 일치(항목 1~2개)가 앞쪽에서 먼저 걸리므로 **항목이 가장 많은 해**를
        # 고른다. 진짜 표는 수백~수천 항목이라 잡음과 자릿수가 다르다.
        best = None
        for tp in range(lo, n - 12):
            a, b, c = struct.unpack_from('<3I', raw, tp)
            if a not in (0, 1) or not (a < b < c) or c - a > 4096:
                continue
            r = self._solve(tp, n)
            if r and (best is None or r[1] > best[1]):
                best = r
        if not best:
            raise ValueError('문자열 오프셋 표를 찾지 못했다')
        self.table_pos, self.count, self.base, self.offsets, self.strings = best

    def _solve(self, tp, n):
        """표가 tp 에서 시작한다고 보고 항목 수 N 을 푼다.

        문자열 구역 **뒤에 또 다른 표가 붙는 파일이 있으므로**(2100.gsc 는 86바이트)
        "걸음이 파일 끝에서 멈춘다"는 조건은 쓸 수 없다. 대신 N 을 위에서부터 낮춰
        가며 표 바이트와 통째로 대조한다. 매 후보를 다 걸으면 O(N²)이 되므로,
        표의 두 번째 항목이 첫 문자열 길이+1 과 같은지로 O(1) 선별한 뒤 걸음을 건다.
        """
        raw = self.raw
        # 단조증가가 끊기는 지점 = 항목 수 상한
        hi, prev = 1, struct.unpack_from('<I', raw, tp)[0]
        while tp + 4 * (hi + 1) <= n - 4:
            v = struct.unpack_from('<I', raw, tp + 4 * hi)[0]
            if v <= prev:
                break
            prev = v
            hi += 1
        t0 = struct.unpack_from('<I', raw, tp)[0]
        t1 = struct.unpack_from('<I', raw, tp + 4)[0] if hi >= 2 else None
        for count in range(hi, 0, -1):
            base = tp + 4 * count
            if base + t0 >= n:
                continue
            e = raw.find(b'\x00', base + t0)
            if e < 0:
                continue
            if t1 is not None and count >= 2 and t1 != e - base + 1:
                continue
            offs, p, good = [], base + t0, True
            for _ in range(count):
                q = raw.find(b'\x00', p)
                if q < 0:
                    good = False
                    break
                offs.append(p - base)
                p = q + 1
            if not good:
                continue
            if struct.pack('<%dI' % count, *offs) != raw[tp:base]:
                continue
            strings = [raw[base + o:raw.find(b'\x00', base + o)] for o in offs]
            return tp, count, base, offs, strings
        return None

    def rebuild(self, strings=None):
        """문자열을 갈아끼워 바이트열을 새로 만든다. strings=None 이면 무변경."""
        ss = self.strings if strings is None else strings
        if len(ss) != self.count:
            raise ValueError(f'문자열 개수 불일치: {len(ss)} != {self.count}')
        pad = self.offsets[0]                     # 선두 빈 문자열(있으면 1바이트)
        blob = bytearray(self.raw[self.base:self.base + pad])
        offs = []
        for s in ss:
            offs.append(len(blob))
            blob += s + b'\x00'
        # 문자열 구역 뒤에 또 다른 표가 붙는 파일이 있어 잔여를 그대로 옮긴다
        blob_end = self.base + self.offsets[-1] + len(self.strings[-1]) + 1
        out = bytearray(self.raw[:self.table_pos])
        out += struct.pack('<%dI' % self.count, *offs)
        out += blob
        out += self.raw[blob_end:]
        delta = len(out) - len(self.raw)
        if delta:
            h = list(self.head)
            h[0] += delta
            h[4] += delta
            struct.pack_into('<%dI' % HDR_N, out, 0, *h)
        return bytes(out)


def test_dir(d):
    files = sorted(glob.glob(os.path.join(d, '*.gsc')))
    ok = fail = 0
    for p in files:
        raw = open(p, 'rb').read()
        try:
            g = Gsc(raw)
            if g.rebuild() == raw:
                ok += 1
            else:
                fail += 1
                print(f'  왕복 불일치 {os.path.basename(p)}')
        except Exception as e:
            fail += 1
            print(f'  실패 {os.path.basename(p)}: {e}')
    print(f'{d}: 무변경 왕복 일치 {ok} / 실패 {fail} / 전체 {len(files)}')
    return fail == 0


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if len(sys.argv) < 3:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == 'test':
        test_dir(sys.argv[2])
    elif cmd == 'dump':
        g = Gsc(open(sys.argv[2], 'rb').read())
        enc = 'cp932' if 'ja_scr' in sys.argv[2] else 'cp949'
        print(f'헤더 {g.head}  표@{g.table_pos}  개수 {g.count}  base {g.base}')
        rng = [int(sys.argv[3])] if len(sys.argv) > 3 else range(min(12, g.count))
        for i in rng:
            print(f'  [{i}] {g.strings[i].decode(enc, "replace")[:70]!r}')
    else:
        print(__doc__)


if __name__ == '__main__':
    main()

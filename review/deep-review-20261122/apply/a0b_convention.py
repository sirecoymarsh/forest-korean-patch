# -*- coding: utf-8 -*-
"""머리 첫 칸(h0)이 「파일 크기」인지 「파일 크기 - h6」인지를 판별로 센다: 일본어 원본 / 플레이해 온 한국어판(백업) / 지금 최신판 / 영문 패치.
그리고 크기 식  n = 28 + h2 + h3 + h4 + h5 + 2*h6  이 모두에서 서는지 본다. 숫자만 출력."""
import os, sys, glob, struct, collections
sys.path.insert(0, r'Y:\AI\forest-deep-review\tools')
from common import *  # noqa
SETS = {'일본어 원본': JA, '플레이해 온 판(scr_backup_20261121)': OLD, '지금 최신판(runtime\\scr)': CUR, '영문 패치': EN,
        '놀이 사본(game\\scr)': r'P:\AI\forest-kr-build\game\scr'}
conv = {}
for name, d in SETS.items():
    fs = sorted(glob.glob(os.path.join(d, '*.gsc')))
    c = collections.Counter(); sizeok = 0; per = {}
    for p in fs:
        raw = open(p, 'rb').read(); n = len(raw)
        h = struct.unpack_from('<7I', raw, 0)
        k = 'h0=크기' if h[0] == n else ('h0=크기-h6' if h[0] == n - h[6] else 'h0=기타')
        c[k] += 1; per[os.path.basename(p)] = k
        sizeok += (n == 28 + h[2] + h[3] + h[4] + h[5] + 2 * h[6])
    conv[name] = per
    print('%-36s 파일 %3d | %s | 크기 식 성립 %d' % (name, len(fs), dict(c), sizeok))
# 지금 최신판에서 h0=크기 인 파일이 플레이해 온 판에서는 어땠나
cur, old = conv['지금 최신판(runtime\\scr)'], conv['플레이해 온 판(scr_backup_20261121)']
tab = collections.Counter((old.get(f, '없음'), k) for f, k in cur.items())
print('플레이해 온 판 → 지금 최신판:', dict(tab))
play = conv.get('놀이 사본(game\\scr)') or {}
print('놀이 사본에서 h0=크기 인 파일 수', sum(1 for v in play.values() if v == 'h0=크기'), '/', len(play))
# I~III장 파일(사용자가 실제로 플레이한 범위)의 판별
early = [f for f in sorted(old) if f[:4] in ('2100', '2101', '2200', '2300') or f[:2] == '30']
print('플레이한 범위(I~III) 파일의 판별(플레이해 온 판):', collections.Counter(old[f] for f in early))

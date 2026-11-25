# -*- coding: utf-8 -*-
"""1) 최신판 대본(runtime\\scr) 104개를 사본 폴더로 통째로 복사(진짜 복사, 하드링크 아님)
2) 다시 쓰기 도구(forest-kr-build\\tools\\gsc.py)가 믿을 만한지 확인:
   - 사본 104개를 고치지 않고 다시 썼을 때 바이트까지 같은가
   - 슬롯 번호가 gscwalk(헤더로 읽는 다른 판독기)와 같은가
   - 제미나이 6차(코덱스 gsc_codec 으로 쓴 것) 앞뒤 파일로 재현: 5차 스냅숏에 같은 문자열을 넣어 다시 쓰면 지금 파일과 바이트까지 같은가
원본 runtime\\scr 는 읽기만 한다."""
import os, sys, json, glob, shutil, hashlib, struct
sys.path.insert(0, r'Y:\AI\forest-deep-review\tools')
from common import *  # noqa  (gscwalk.walk 포함)
sys.path.insert(0, r'P:\AI\forest-kr-build\tools')
from gsc import Gsc
sys.path.insert(0, r'P:\AI\forest-gemini-review\tools')
from gscwalk import strings_of

AP = r'Y:\AI\forest-deep-review\apply'
DST = r'Y:\AI\forest-deep-review\applied_20261122\scr'
os.makedirs(DST, exist_ok=True)


def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()


src = sorted(glob.glob(os.path.join(CUR, '*.gsc')))
base = {}
for p in src:
    f = os.path.basename(p)
    shutil.copyfile(p, os.path.join(DST, f))
    base[f] = {'sha256': sha(p), 'size': os.path.getsize(p)}
    assert sha(os.path.join(DST, f)) == base[f]['sha256']
json.dump(base, open(os.path.join(AP, 'base_hashes.json'), 'w', encoding='utf-8'), indent=1)
print('복사', len(src), '개 →', DST)

# 왕복·슬롯 대조
rt_ok = slot_ok = 0; bad = []
for p in sorted(glob.glob(os.path.join(DST, '*.gsc'))):
    raw = open(p, 'rb').read()
    g = Gsc(raw)
    if g.rebuild() == raw: rt_ok += 1
    else: bad.append(('왕복', os.path.basename(p)))
    h = struct.unpack_from('<7I', raw, 0)
    if g.strings == strings_of(raw) and g.table_pos == h[1] + h[2] and g.count == h[3] // 4: slot_ok += 1
    else: bad.append(('슬롯', os.path.basename(p)))
print('고치지 않고 다시 쓰기 = 원본과 같음', rt_ok, '/ 슬롯·표 위치가 다른 판독기와 같음', slot_ok, '/ 전체', len(src), '어긋남', bad)

# 제미나이 6차 재현
S5 = os.path.join(GEM, 'scr_pass5_snapshot')
rep = []
for f in sorted(os.listdir(S5)):
    if not f.endswith('.gsc'): continue
    a = open(os.path.join(S5, f), 'rb').read(); b = open(os.path.join(CUR, f), 'rb').read()
    if a == b: continue
    ga, gb = Gsc(a), Gsc(b)
    same = ga.rebuild(list(gb.strings)) == b
    nchg = sum(1 for x, y in zip(ga.strings, gb.strings) if x != y)
    ha = struct.unpack_from('<7I', a, 0); hb = struct.unpack_from('<7I', b, 0)
    rep.append((f, nchg, same, [k for k in range(7) if ha[k] != hb[k]], len(b) - len(a)))
print('6차에서 바뀐 파일 재현(파일, 바뀐 슬롯 수, 바이트 일치, 바뀐 헤더 칸, 크기 차):', rep)
json.dump({'roundtrip_ok': rt_ok, 'slot_ok': slot_ok, 'bad': bad, 'pass6_repro': rep}, open(os.path.join(AP, 'a1_check.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

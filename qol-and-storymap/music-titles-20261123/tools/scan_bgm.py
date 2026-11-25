# 모든 대본(성인 장면 8개 제외)의 명령부에서 BGM 재생 후보(opcode 60, 상수 인자)를 센다. 글은 읽지 않는다.
import sys, struct, collections
sys.path.insert(0, 'P:/AI/forest-kr-build/tools'); sys.path.insert(0, 'P:/AI/forest-flowchart-claude/tools')
import xfl, gscread
SKIP = {'2101', '2301', '2302', '2501', '2601', '2701', '2801', '3039'}
ARC = 'P:/GAME/Forest/scr.xfl'
idx = xfl.read_index(ARC)
names = [e[0] for e in idx]
print('scripts', len(names)); print(' '.join(n[:4] for n in names))
use = collections.defaultdict(list)
for e in idx:
    stem = e[0][:4]
    if stem in SKIP: continue
    g = gscread.Gsc(xfl.extract(ARC, e), 'cp932')
    c = g.code
    v = struct.unpack_from('<%dH' % (len(c) // 2), c)
    for i in range(len(v) - 4):
        if v[i] == 60 and v[i + 2] in (0, 2) and v[i + 4] == 0 and 0 < v[i + 1] < 64:
            use[stem].append((v[i + 1], v[i + 2], v[i + 3], i * 2))
for s in sorted(use):
    print(s, [(a if t == 0 else 'var%d' % a, b) for a, t, b, _ in use[s]])

# -*- coding: utf-8 -*-
"""사본의 바뀐 33개 파일을 다른 도구들도 그대로 읽는지 본다(뒤에 제미나이·코덱스 도구가 이 파일을 읽게 되므로).
 - 코덱스 gsc_codec(제미나이가 3~6차에 쓴 것): parse → 문자열이 같은가, 고치지 않고 rebuild 하면 바이트까지 같은가
 - forest-kr-build\\tools\\gsc.py(표를 실측으로 찾는 옛 도구): 읽히는 파일에서는 문자열이 같은가 / 못 읽는 파일은 원본에서도 못 읽는가
그리고 사본 전체를 놓고 정한 낱말이 남았는지 다시 센다. 숫자·파일 이름만 출력."""
import os, sys, json, glob, struct, collections, re
sys.path.insert(0, r'Y:\AI\forest-deep-review\tools')
from common import *  # noqa
sys.path.insert(0, r'P:\AI\forest-gemini-review\tools')
from gscwalk import strings_of
AP = r'Y:\AI\forest-deep-review\apply'
DST = r'Y:\AI\forest-deep-review\applied_20261122\scr'
log = json.load(open(os.path.join(AP, 'a2_log.json'), encoding='utf-8'))
changed = sorted(log['files'])

# 코덱스 gsc_codec
sys.path.insert(0, r'P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest\work\forest-en-korean-pilot\translation_work\tools')
try:
    from gsc_codec import parse_gsc, rebuild_gsc
    ok = rt = 0; bad = []
    for f in changed:
        b = open(os.path.join(DST, f), 'rb').read()
        pts = parse_gsc(b)
        # parse 결과에서 문자열 목록을 찾는다(구조를 모르므로 다시 쓰기만으로 본다)
        strs = None
        for cand in (getattr(pts, 'strings', None), pts.get('strings') if isinstance(pts, dict) else None):
            if cand is not None: strs = list(cand); break
        if strs is None and isinstance(pts, (tuple, list)):
            for x in pts:
                if isinstance(x, (tuple, list)) and x and isinstance(x[0], (bytes, bytearray)) and len(x) == len(strings_of(b)): strs = list(x); break
        if strs is not None and [bytes(s) for s in strs] == strings_of(b): ok += 1
        elif strs is None: bad.append((f, '문자열 목록 못 찾음(구조 모름)'))
        else: bad.append((f, '문자열 다름'))
        if strs is not None:
            try:
                if rebuild_gsc(pts, tuple(strs)) == b: rt += 1
                else: bad.append((f, '다시 쓰기 불일치'))
            except Exception as e:
                bad.append((f, 'rebuild 예외 %s' % type(e).__name__))
    print('코덱스 gsc_codec: 문자열 같음 %d / 고치지 않고 다시 쓰기 같음 %d / 바뀐 파일 %d | 어긋남 %s' % (ok, rt, len(changed), bad[:5]))
except Exception as e:
    print('코덱스 gsc_codec 을 쓸 수 없음:', type(e).__name__, str(e)[:120])

# 옛 gsc.py
sys.path.insert(0, r'P:\AI\forest-kr-build\tools')
from gsc import Gsc
def old_read(raw):
    try:
        g = Gsc(raw)
        return 'ok' if g.strings == strings_of(raw) else 'diff'
    except Exception:
        return 'fail'
st_new = {}; st_org = {}
for p in sorted(glob.glob(os.path.join(DST, '*.gsc'))):
    f = os.path.basename(p)
    st_new[f] = old_read(open(p, 'rb').read()); st_org[f] = old_read(open(os.path.join(CUR, f), 'rb').read())
notok = [f for f, v in st_new.items() if v != 'ok']
print('옛 gsc.py: 사본 104개 중 제대로 읽음 %d · 못 읽거나 달리 읽음 %d' % (sum(1 for v in st_new.values() if v == 'ok'), len(notok)))
print('   그 %d개는 원본에서도 똑같이 그런가: %s | 그중 내가 바꾼 파일: %s | 번호대: %s' % (
    len(notok), all(st_org[f] == st_new[f] for f in notok), [f for f in notok if f in changed], sorted({f[:2] for f in notok})))
print('   내가 바꾼 33개는 옛 gsc.py 로도 제대로 읽힘:', all(st_new[f] == 'ok' for f in changed))

# 정한 낱말이 남았는가(보류 구간 밖)
corpus = [c for c in load_corpus() if c['kind'] in ('MSG', 'SUB', 'CHQ', 'CHO')]
ADULT = set(json.load(open(os.path.join(DATA, 'adult.json'), encoding='utf-8'))['ids'])
cache = {}
left = collections.Counter(); total = same = diff = 0
for c in corpus:
    if c['id'] in ADULT or c.get('hold') or c['file'] in HOLD_FILES: continue
    f = c['file'] + '.gsc'
    if f not in cache: cache[f] = strings_of(open(os.path.join(DST, f), 'rb').read())
    t = cache[f][c['slot']].decode('cp949', 'replace')      # 말뭉치도 같은 방식으로 읽었다
    total += 1
    if t == c['ko']: same += 1
    else: diff += 1
    for w in ('갤러리', '카부키쵸', '개적'):
        if w in t: left[w] += 1
print('사본의 칸(보류 구간 밖) %d 중 지금 판과 같은 칸 %d · 달라진 칸 %d | 남은 낱말 %s' % (total, same, diff, dict(left) or '없음'))

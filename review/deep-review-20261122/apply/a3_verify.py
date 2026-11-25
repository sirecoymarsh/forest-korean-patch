# -*- coding: utf-8 -*-
"""사본에 넣은 결과를 쓰기 도구와 다른 길로 대조한다(판독은 gscwalk — 명령 길이표로 명령부를 걷고 머리 값으로 문자열을 읽음).
 a. 명령부: 104개 모두 원본과 바이트·명령 목록이 같은가
 b. 문자열: 개수 같음 / 바뀐 슬롯 = 목록 541칸 + 자막 외곽선 / 바뀐 슬롯의 글 = 목록의 fix / 나머지 슬롯은 바이트까지 같음
 c. 머리: h1·h2·h3·h5·h6 그대로, h4 = 새 문자열 구역 크기, h0 꼴(크기 / 크기-h6) 그대로, 크기 식 성립, 꼬리 바이트 그대로
 d. 목록에 없는 파일은 원본과 해시가 같음
 e. 넣은 글: cp949, 한 줄 57칸, 줄 수, ^g 뒤 숫자, 토큰·따옴표
 f. 원본 runtime\\scr·일본어 원본 해시는 처음 그대로, 놀이 사본 마지막 쓰기 시각
화면에는 번호·숫자만 낸다."""
import os, sys, json, glob, hashlib, struct, collections, re, time
sys.path.insert(0, r'Y:\AI\forest-deep-review\tools')
from common import *  # noqa
sys.path.insert(0, r'P:\AI\forest-gemini-review\tools')
from gscwalk import strings_of

AP = r'Y:\AI\forest-deep-review\apply'
DST = r'Y:\AI\forest-deep-review\applied_20261122\scr'
PK = r'P:\AI\forest-gemini-review\제미나이_전달_20261122'
cells = {}
for l in open(os.path.join(PK, '01_확정_반영목록.jsonl'), encoding='utf-8'):
    if l.strip():
        c = json.loads(l); cells[('%04d.gsc' % c['file_id'], c['slot_idx'])] = c
log = json.load(open(os.path.join(AP, 'a2_log.json'), encoding='utf-8'))
outline = {(o['file'], o['slot']): o['id'] for o in log['outline']}
want_files = sorted({k[0] for k in cells})
res = collections.Counter(); bad = collections.defaultdict(list)


def sha(b): return hashlib.sha256(b).hexdigest()


def linecells(s):
    out = []
    for line in re.split(r'\^n', s):
        out.append(len(re.sub(r'\^(g[0-9]{3}|m|c[a-z])', '', line).encode('cp949')))
    return out


files = sorted(glob.glob(os.path.join(CUR, '*.gsc')))
changed_slots = 0
for p in files:
    f = os.path.basename(p)
    a = open(p, 'rb').read(); b = open(os.path.join(DST, f), 'rb').read()
    ha = struct.unpack_from('<7I', a, 0); hb = struct.unpack_from('<7I', b, 0)
    if f not in want_files:
        if a == b: res['목록 밖 파일 = 원본과 같음'] += 1
        else: bad['목록 밖 파일이 바뀜'].append(f)
        continue
    # a. 명령부
    ca, _ = walk(p); cb, _ = walk(os.path.join(DST, f))
    if a[28:28 + ha[2]] == b[28:28 + hb[2]] and ca == cb: res['명령부 같음'] += 1
    else: bad['명령부 다름'].append(f)
    # c. 머리·꼬리
    if not (ha[1] == hb[1] and ha[2] == hb[2] and ha[3] == hb[3] and ha[5] == hb[5] and ha[6] == hb[6]): bad['머리 h1·h2·h3·h5·h6 바뀜'].append(f)
    tpb = hb[1] + hb[2]; baseb = tpb + hb[3]
    sa = strings_of(a); sb = strings_of(b)
    blob_b = sum(len(x) + 1 for x in sb)
    if hb[4] != blob_b: bad['h4 가 새 문자열 구역 크기와 다름'].append(f)
    if len(b) != 28 + hb[2] + hb[3] + hb[4] + hb[5] + 2 * hb[6]: bad['크기 식 안 맞음'].append(f)
    conv_a = 'n' if ha[0] == len(a) else ('n-h6' if ha[0] == len(a) - ha[6] else '?')
    conv_b = 'n' if hb[0] == len(b) else ('n-h6' if hb[0] == len(b) - hb[6] else '?')
    if conv_a != conv_b or conv_b == '?': bad['h0 꼴 바뀜'].append((f, conv_a, conv_b))
    else: res['h0 꼴 그대로(%s)' % conv_b] += 1
    tail_a = a[28 + ha[2] + ha[3] + ha[4]:]; tail_b = b[28 + hb[2] + hb[3] + hb[4]:]
    if tail_a == tail_b: res['꼬리 같음'] += 1
    else: bad['꼬리 다름'].append(f)
    # 오프셋 표가 문자열과 맞는가(연속 배치)
    offs = struct.unpack_from('<%dI' % (hb[3] // 4), b, tpb); q = 0; okoff = True
    for k, s in enumerate(sb):
        if offs[k] != q: okoff = False; break
        q += len(s) + 1
    if not okoff: bad['오프셋 표 어긋남'].append(f)
    # b. 문자열
    if len(sa) != len(sb): bad['문자열 개수 다름'].append(f); continue
    for k, (x, y) in enumerate(zip(sa, sb)):
        key = (f, k)
        if key in cells:
            c = cells[key]
            if x.decode('cp949') != c['cur']: bad['원본 글이 목록 cur 와 다름'].append(c['id'])
            if y.decode('cp949') == c['fix']: res['목록 칸 = fix 와 같음'] += 1
            else: bad['넣은 글이 fix 와 다름'].append(c['id'])
            changed_slots += 1
        elif key in outline:
            body = cells[(f, next(s for (ff, s), cc in cells.items() if ff == f and cc['id'] == outline[key]))]
            if y == b'^ck' + body['fix'].encode('cp949')[3:] and x == b'^ck' + body['cur'].encode('cp949')[3:]: res['외곽선 = 몸체와 같은 글'] += 1
            else: bad['외곽선 글 어긋남'].append(outline[key])
            changed_slots += 1
        else:
            if x == y: res['나머지 슬롯 그대로'] += 1
            else: bad['목록에 없는 슬롯이 바뀜'].append('%s:%d' % (f[:4], k))
# e. 넣은 글의 꼴
for (f, k), c in cells.items():
    fx, cu = c['fix'], c['cur']
    lc = linecells(fx)
    if max(lc) > 57: bad['넘침'].append(c['id'])
    if len(lc) > (4 if cu.startswith('^c') else 3): bad['줄 초과'].append(c['id'])
    if len(lc) > len(linecells(cu)): res['줄 수 늘어남(허용 범위 안)'] += 1; bad_note = c['id']
    if re.search(r'\^g[0-9]{3}[0-9]', fx): bad['^g 뒤 숫자'].append(c['id'])
    if re.findall(r'\^(?:g[0-9]{3}|m|c[a-z])', fx) != re.findall(r'\^(?:g[0-9]{3}|m|c[a-z])', cu): bad['토큰 다름'].append(c['id'])
    if fx.count('"') != cu.count('"'): bad['ASCII 따옴표 수 다름'].append(c['id'])
# f. 원본들
p0 = json.load(open(r'P:\AI\Codex\projects\forest-translation-review-20261121\deep-review-20261122\census-20261122\outputs\preservation_check.json', encoding='utf-8'))
same0 = sum(1 for c in p0['checks'] if sha(open(c['path'], 'rb').read()) == c['after'])
newest = 0
for root, ds, fs in os.walk(r'P:\AI\forest-kr-build\game'):
    for x in fs:
        try: newest = max(newest, os.path.getmtime(os.path.join(root, x)))
        except OSError: pass
print('바뀐 파일', len(want_files), '/ 전체', len(files), '| 바뀐 슬롯', changed_slots, '(목록', len(cells), '+ 외곽선', len(outline), ')')
for k, v in res.items(): print('  ', k, v)
print('어긋남:', {k: v[:20] for k, v in bad.items()} or '없음')
print('원본 대본·일본어 원본 해시 처음 그대로:', same0, '/', len(p0['checks']), '| 놀이 사본 마지막 쓰기', time.strftime('%Y-%m-%d %H:%M', time.localtime(newest)))
json.dump({'changed_files': want_files, 'changed_slots': changed_slots, 'res': dict(res), 'bad': {k: v for k, v in bad.items()}, 'orig_hash_same': same0},
          open(os.path.join(AP, 'a3_verify.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

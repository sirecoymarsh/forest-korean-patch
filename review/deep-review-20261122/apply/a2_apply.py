# -*- coding: utf-8 -*-
"""확정 반영 목록(01, 541칸)을 사본 Y:\\AI\\forest-deep-review\\applied_20261122\\scr 에 넣는다.
먼저 다시 쓰기 도구를 검증한다: ① 104개를 고치지 않고 다시 쓰면 바이트까지 같은가 ② 제미나이 6차 앞뒤 파일로 재현되는가.
원본 runtime\\scr 와 놀이 사본은 읽기만 한다. 화면에는 번호·숫자만 낸다."""
import os, sys, json, glob, hashlib, struct, collections, re
sys.path.insert(0, r'Y:\AI\forest-deep-review\tools')
from common import *  # noqa  (walk 포함)
sys.path.insert(0, r'Y:\AI\forest-deep-review\apply')
import gscrw

AP = r'Y:\AI\forest-deep-review\apply'
DST = r'Y:\AI\forest-deep-review\applied_20261122\scr'
PK = r'P:\AI\forest-gemini-review\제미나이_전달_20261122'
DRY = '--dry' in sys.argv


def sha(b): return hashlib.sha256(b).hexdigest()


# ---------- 0. 사본이 지금도 최신판과 같은 상태에서 시작하는가(다시 돌려도 같게: 원본에서 새로 복사)
base = json.load(open(os.path.join(AP, 'base_hashes.json'), encoding='utf-8'))
src_files = sorted(glob.glob(os.path.join(CUR, '*.gsc')))
assert len(src_files) == len(base) == 104
raws = {}
for p in src_files:
    f = os.path.basename(p); b = open(p, 'rb').read()
    assert sha(b) == base[f]['sha256'], '원본이 복사 뒤에 바뀜: ' + f
    raws[f] = b

# ---------- 1. 도구 검증
rt = sum(1 for f, b in raws.items() if gscrw.rebuild(b, gscrw.parse(b)['strings']) == b)
print('① 고치지 않고 다시 쓰기 = 원본과 바이트까지 같음:', rt, '/', len(raws))
assert rt == len(raws)
S5 = os.path.join(GEM, 'scr_pass5_snapshot'); rep = []
for f in sorted(os.listdir(S5)):
    if not f.endswith('.gsc'): continue
    a = open(os.path.join(S5, f), 'rb').read(); b = raws[f]
    if a == b: continue
    sb = gscrw.parse(b)['strings']; sa = gscrw.parse(a)['strings']
    rep.append((f, sum(1 for x, y in zip(sa, sb) if x != y), gscrw.rebuild(a, sb) == b, len(b) - len(a)))
print('② 제미나이 6차 재현(파일, 바뀐 슬롯 수, 바이트 일치, 크기 차):', rep)
assert rep and all(r[2] for r in rep)

# ---------- 2. 목록 읽기
cells = [json.loads(l) for l in open(os.path.join(PK, '01_확정_반영목록.jsonl'), encoding='utf-8') if l.strip()]
assert len(cells) == len({c['id'] for c in cells})
byf = collections.defaultdict(list)
for c in cells: byf['%04d.gsc' % c['file_id']].append(c)
print('목록', len(cells), '칸,', len(byf), '개 파일')

# ---------- 3. 넣기
log = {'cells': [], 'outline': [], 'files': {}}
problems = []
for f in sorted(byf):
    raw = raws[f]; g = gscrw.parse(raw); ss = list(g['strings'])
    cmds, _ = walk(os.path.join(CUR, f))
    # 자막 몸체 슬롯 → 외곽선 슬롯들: op 0x20 이 a0=45,46,47,48(외곽선) 다음 49(몸체)로 이어지는 묶음
    outl = collections.defaultdict(set)
    for k, (pc, op, a) in enumerate(cmds):
        if op == 0x20 and a and a[0] == 49:
            j = k - 1; grp = []
            while j >= 0 and cmds[j][1] == 0x20 and cmds[j][2] and cmds[j][2][0] in (45, 46, 47, 48) and len(grp) < 4:
                grp.append(cmds[j][2][5]); j -= 1
            for s in grp: outl[a[5]].add(s)
    touched = {}
    for c in byf[f]:
        sl = c['slot_idx']
        try:
            cur_b = c['cur'].encode('cp949'); fix_b = c['fix'].encode('cp949')
        except UnicodeEncodeError as e:
            problems.append((c['id'], 'cp949 불가')); continue
        if sl >= len(ss): problems.append((c['id'], '슬롯 범위 밖')); continue
        if g['strings'][sl] != cur_b: problems.append((c['id'], '지금 글이 목록의 cur 와 다름')); continue
        if sl in touched: problems.append((c['id'], '같은 슬롯 두 번')); continue
        ss[sl] = fix_b; touched[sl] = c['id']
        log['cells'].append({'id': c['id'], 'file': f, 'slot': sl, 'kind': c['kind'], 'bytes': [len(cur_b), len(fix_b)]})
        if c['kind'] == 'SUB':
            if not c['cur'].startswith('^cy') or not c['fix'].startswith('^cy'): problems.append((c['id'], '자막인데 ^cy 로 시작하지 않음')); continue
            if not outl.get(sl): problems.append((c['id'], '외곽선 슬롯을 못 찾음')); continue
            for o in sorted(outl[sl]):
                want_old = b'^ck' + cur_b[3:]
                if g['strings'][o] != want_old: problems.append((c['id'], '외곽선 슬롯 %d 의 글이 몸체와 다름' % o)); continue
                if o in touched: problems.append((c['id'], '외곽선 슬롯이 다른 칸과 겹침')); continue
                ss[o] = b'^ck' + fix_b[3:]; touched[o] = c['id'] + '(외곽선)'
                log['outline'].append({'id': c['id'], 'file': f, 'slot': o})
    new = gscrw.rebuild(raw, ss)
    log['files'][f] = {'cells': len(byf[f]), 'slots_changed': len(touched), 'size': [len(raw), len(new)], 'sha256': [sha(raw), sha(new)]}
    raws[f + '.new'] = new
print('넣을 칸', len(log['cells']), '외곽선 슬롯', len(log['outline']), '바뀌는 파일', len(log['files']), '| 문제', problems)
if problems:
    json.dump(problems, open(os.path.join(AP, 'a2_problems.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    sys.exit('문제가 있어 쓰지 않았다')
if DRY:
    print('--dry: 쓰지 않음'); sys.exit()
for f in sorted(byf):
    open(os.path.join(DST, f), 'wb').write(raws[f + '.new'])
json.dump(log, open(os.path.join(AP, 'a2_log.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('사본에 씀:', DST)
print('크기 변화 합', sum(v['size'][1] - v['size'][0] for v in log['files'].values()), '바이트')

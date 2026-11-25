# -*- coding: utf-8 -*-
"""Forest 한국어 빌드 — 교정안을 하나씩 적용한다.

  python apply_patch.py init                  기준본(AIS fusion_round03)으로 작업장 초기화
  python apply_patch.py list                  적용 대기/완료 목록
  python apply_patch.py apply <patch.json>    한 건 적용 (검증 후 커밋)
  python apply_patch.py status                현재 상태 요약
  python apply_patch.py diff <uid>            특정 uid의 기준본 대비 변화
  python apply_patch.py rollback              마지막 적용 취소

패치 형식: [{"uid":..., "before":..., "after":..., "reason":...}, ...]  (json 또는 jsonl)
게이트: 제어토큰 시퀀스 불변 · CP949 · main_dialogue ≤3줄 · 전 레인 ≤57 EAW ·
        물리개행/NUL 금지
"""
import json, sys, io, os, glob, re, shutil, hashlib, unicodedata, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = r"P:\AI\forest-kr-build"
SRC  = r"P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest\outputs\forest_full_ja_compact_packets_20260802"
BASE_MAP = os.path.join(SRC, "fusion_round03_aistudio_objective_error_hotfix", "translation_map.gemini_full_fused.json")

D_BASE  = os.path.join(ROOT, 'base')
D_CUR   = os.path.join(ROOT, 'current')
D_PATCH = os.path.join(ROOT, 'patches')
D_LOG   = os.path.join(ROOT, 'log')
F_CUR   = os.path.join(D_CUR, 'translation_map.current.json')
F_BASE  = os.path.join(D_BASE, 'translation_map.base.json')
F_LOG   = os.path.join(D_LOG, 'applied.jsonl')

CODE = re.compile(r'\^g\d{3}|\^n|\^c[a-z]')

# 화면 표시 한계. 2026-08-08 실측으로 확정했다.
#   3021.gsc 0x000370 두 줄이 각각 63 EAW인데 화면에서 접혔고, 접힌 지점의 누적폭이
#   각각 56/57, 다음 글자를 포함하면 58 — 즉 57까지 들어가고 58부터 접힌다.
#   영문 팬패치는 시나리오 30,270줄 전건이 54 이하다(본문·자막 모두). 3만큼 여유를 뒀다.
# 종전 값 64는 근거 없는 과대치였고, 그 탓에 253개 레코드가 넘친 채 통과했다.
# 폭은 EAW의 W/F/A를 2로 센다(A=애매폭 포함 — 하네스 runtime_line_eaw_width와 동일).
MAX_EAW = 57

DIGIT_AFTER_G = re.compile(r'\^g\d{3}\d')

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest().upper()

def eaw(s):
    s = CODE.sub('', s)
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F', 'A') else 1 for c in s)

def body_lines(t):
    return re.sub(r'\^g\d{3}|\^c[a-z]', '', t).split('^n')

def load_lane():
    lane = {}
    for p in sorted(glob.glob(os.path.join(SRC, 'maps', '*.map.jsonl'))):
        for line in open(p, encoding='utf-8'):
            if line.strip():
                r = json.loads(line)
                lane[r['uid']] = r.get('lane')
    return lane

def load_patch(p):
    txt = open(p, encoding='utf-8').read().strip()
    if txt.startswith('['):
        return json.loads(txt)
    return [json.loads(l) for l in txt.splitlines() if l.strip()]

def fail(m):
    print(f"[오류] {m}")
    print("RESULT: FAIL")
    sys.exit(1)

def cmd_init():
    if os.path.exists(F_CUR):
        fail(f"이미 초기화됨: {F_CUR}\n      다시 만들려면 {ROOT} 를 지우고 실행하라")
    for d in (D_BASE, D_CUR, D_PATCH, D_LOG):
        os.makedirs(d, exist_ok=True)
    shutil.copy2(BASE_MAP, F_BASE)
    shutil.copy2(BASE_MAP, F_CUR)
    d = json.load(open(F_BASE, encoding='utf-8'))
    open(F_LOG, 'w', encoding='utf-8').close()
    print(f"기준본  : {BASE_MAP}")
    print(f"  SHA-256 {sha(F_BASE)}")
    print(f"  레코드  {len(d['records'])}")
    print(f"작업장  : {ROOT}")
    print("RESULT: PASS")

def cmd_apply(pfile):
    if not os.path.exists(F_CUR): fail("init 먼저 실행")
    if not os.path.exists(pfile):
        alt = os.path.join(D_PATCH, os.path.basename(pfile))
        if os.path.exists(alt): pfile = alt
        else: fail(f"패치 없음: {pfile}")
    rows = load_patch(pfile)
    doc = json.load(open(F_CUR, encoding='utf-8'))
    cur = {r['uid']: r for r in doc['records']}
    lane = load_lane()

    mism, miss, already = [], [], []
    for r in rows:
        u = r['uid']
        if u not in cur: miss.append(u); continue
        t = cur[u].get('target') or ''
        if t == r['after']: already.append(u)
        elif t != r['before']: mism.append(u)
    print(f"패치     : {os.path.basename(pfile)}  ({len(rows)}건)")
    print(f"  대조   : 적용가능 {len(rows)-len(mism)-len(miss)-len(already)} / 이미적용 {len(already)} / before불일치 {len(mism)} / uid없음 {len(miss)}")
    if mism or miss:
        for u in (mism + miss)[:8]: print(f"    문제 {u}")
        fail("before 불일치 또는 uid 누락 — 적용하지 않는다")
    if already and len(already) == len(rows):
        print("이미 전건 적용된 상태다.")
        print("RESULT: PASS"); return

    bad = []
    for r in rows:
        u, a = r['uid'], r['after']
        b = cur[u].get('target') or ''
        p = []
        if CODE.findall(a) != CODE.findall(b): p.append('제어토큰')
        try: a.encode('cp949')
        except UnicodeEncodeError as e: p.append('CP949:' + e.object[e.start:e.end])
        if any(c in a for c in '\n\r\0'): p.append('물리개행')
        # ^g### 직후의 반각 숫자 — 엔진이 그룹 코드로 탐욕적으로 먹어 대사가 깨진다.
        # ^g999 + 7 -> ^g9997 로 읽혀 코드가 무효가 되고 위치가 무너지며
        # 이전 화자 이름표가 남는다. 일본어 원문은 이 자리에 전각 숫자를 쓴다.
        # ^n·^c 는 인자를 받지 않으므로 숫자가 뒤따라도 안전하다.
        if DIGIT_AFTER_G.search(a):
            p.append('^g뒤반각숫자')

        L = body_lines(a)
        if lane.get(u) == 'main_dialogue' and len(L) > 3:
            p.append(f'{len(L)}줄')
        # 폭 검사는 모든 레인에 건다. 자막도 넘치면 화면에서 접힌다.
        w = max(eaw(x) for x in L)
        if w > MAX_EAW: p.append(f'{w}EAW')
        if p: bad.append((u, ','.join(p)))
    if bad:
        for u, w in bad[:10]: print(f"    게이트 위반 {u}  {w}")
        fail(f"게이트 위반 {len(bad)}건")
    print("  게이트 : 제어토큰·CP949·줄수·폭 전건 통과")

    shutil.copy2(F_CUR, F_CUR + '.prev')
    n = 0
    for r in rows:
        if cur[r['uid']].get('target') != r['after']:
            cur[r['uid']]['target'] = r['after']; n += 1
    tmp = F_CUR + '.tmp'
    json.dump(doc, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, F_CUR)
    with open(F_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'patch': os.path.basename(pfile), 'entries': len(rows),
                            'changed': n, 'sha256': sha(F_CUR)}, ensure_ascii=False) + '\n')
    print(f"  적용   : {n}건 변경")
    print(f"  현재본 : SHA-256 {sha(F_CUR)}")
    print("RESULT: PASS")

def cmd_status():
    if not os.path.exists(F_CUR): fail("init 먼저 실행")
    base = {r['uid']: (r.get('target') or '') for r in json.load(open(F_BASE, encoding='utf-8'))['records']}
    cur  = {r['uid']: (r.get('target') or '') for r in json.load(open(F_CUR, encoding='utf-8'))['records']}
    diff = [u for u in cur if cur[u] != base.get(u)]
    print(f"작업장   : {ROOT}")
    print(f"레코드   : {len(cur)}")
    print(f"기준본 대비 변경: {len(diff)}건")
    print(f"현재본 SHA-256  : {sha(F_CUR)}")
    print("\n적용 이력:")
    if os.path.exists(F_LOG):
        for l in open(F_LOG, encoding='utf-8'):
            if l.strip():
                r = json.loads(l)
                print(f"  {r['patch']:<34} {r['changed']:>5}건  {r['sha256'][:16]}…")
    print("\n대기 중인 패치:")
    done = {json.loads(l)['patch'] for l in open(F_LOG, encoding='utf-8') if l.strip()} if os.path.exists(F_LOG) else set()
    for p in sorted(glob.glob(os.path.join(D_PATCH, '*.json'))) + sorted(glob.glob(os.path.join(D_PATCH, '*.jsonl'))):
        b = os.path.basename(p)
        if b not in done:
            try: n = len(load_patch(p))
            except Exception: n = '?'
            print(f"  {b:<34} {n}건")
    print("RESULT: PASS")

def cmd_list():
    cmd_status()

def cmd_diff(uid):
    base = {r['uid']: (r.get('target') or '') for r in json.load(open(F_BASE, encoding='utf-8'))['records']}
    cur  = {r['uid']: (r.get('target') or '') for r in json.load(open(F_CUR, encoding='utf-8'))['records']}
    hit = [u for u in cur if uid in u]
    for u in hit[:20]:
        print(f"\n{u}")
        print(f"  기준| {base.get(u,'')}")
        print(f"  현재| {cur[u]}")
    print("RESULT: PASS")

def cmd_rollback():
    p = F_CUR + '.prev'
    if not os.path.exists(p): fail("되돌릴 이전 상태가 없다")
    shutil.copy2(p, F_CUR); os.remove(p)
    lines = [l for l in open(F_LOG, encoding='utf-8') if l.strip()]
    if lines:
        open(F_LOG, 'w', encoding='utf-8').writelines(lines[:-1])
        print(f"취소: {json.loads(lines[-1])['patch']}")
    print(f"현재본 SHA-256 {sha(F_CUR)}")
    print("RESULT: PASS")

if __name__ == '__main__':
    if len(sys.argv) < 2: fail("사용법: init | list | apply <patch> | status | diff <uid> | rollback")
    c = sys.argv[1]
    if   c == 'init': cmd_init()
    elif c == 'apply': cmd_apply(sys.argv[2] if len(sys.argv) > 2 else fail("패치 파일 지정"))
    elif c in ('status', 'list'): cmd_status()
    elif c == 'diff': cmd_diff(sys.argv[2] if len(sys.argv) > 2 else fail("uid 조각 지정"))
    elif c == 'rollback': cmd_rollback()
    else: fail(f"알 수 없는 명령: {c}")

# -*- coding: utf-8 -*-
"""빌드 결과를 새 게임 사본에 설치한다.

  base    : 파이프라인 격리 실행본(영문 팬패치, 무수정)
  payload : Codex 누적 릴리스 (굴림 EXE, 화자명 48, 챕터선택 UI 44)
  ui      : 세이브/로드 화면 UI 89 (시나리오 제목 카드 88 + savescrn)
  gsc     : P:\\AI\\forest-kr-build\\gsc_build\\scr 의 52개

원본 게임과 파이프라인 격리본은 건드리지 않는다.

주의: 누적 릴리스 2BB2F4C7 에는 save/load UI 가 없다. 빠뜨리면 세이브 화면
챕터명이 영문 래스터("Story of the Beginning I", "Signpost")로 남는다.
한국어 자산은 UI_REL 스테이징에 있고, 다른 계보 스테이징과 바이트 동일하므로
계보와 무관하게 얹어도 된다. 상세는 install_saveload_ui.py 참조.
"""
import json, sys, io, os, glob, shutil, hashlib, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SRC_GAME = r"P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest\work\forest-en-korean-pilot\game"
REL = r"P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest\work\forest-en-korean-pilot\translation_work\correction_work\staging_release_2BB2F4C7_gulim_chapter_titles"
UI_REL = r"P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest\work\forest-en-korean-pilot\translation_work\correction_work\staging_release_D27972DF_aistudio_objective_hotfix_save_load_ui"
UI_ROLES = ('save_load_scenario_title_ui', 'save_load_screen_ui')
GSC = r"P:\AI\forest-kr-build\gsc_build\scr"
DST = r"P:\AI\forest-kr-build\game"

FORBIDDEN = [os.path.normcase(r"P:\GAME\Forest"), os.path.normcase(SRC_GAME)]

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest().upper()

def fail(m):
    print(f"[오류] {m}"); print("RESULT: FAIL"); sys.exit(1)

if os.path.normcase(DST) in FORBIDDEN:
    fail("보호 경로에는 설치하지 않는다")

mode = sys.argv[1] if len(sys.argv) > 1 else 'install'

if mode == 'install':
    if os.path.exists(DST):
        fail(f"이미 존재: {DST}\n      다시 만들려면 지우고 실행하라")
    print(f"1) 기반 복사: {SRC_GAME}")
    shutil.copytree(SRC_GAME, DST)
    n = sum(len(f) for _, _, f in os.walk(DST))
    print(f"   {n}개 파일")

    print(f"2) Codex 누적 릴리스 적용")
    man = json.load(open(os.path.join(REL, 'release_manifest.json'), encoding='utf-8'))
    cnt = collections.Counter()
    for row in man['payload_files']:
        rel = row['relative_path']
        src = os.path.join(REL, rel.replace('/', os.sep))
        if not os.path.exists(src):
            fail(f"페이로드 없음: {rel}")
        if sha(src).upper() != row['sha256'].upper():
            fail(f"페이로드 해시 불일치: {rel}")
        dst = os.path.join(DST, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        cnt[row['role']] += 1
    for k, v in cnt.items(): print(f"   {k}: {v}")

    print(f"2b) 세이브/로드 화면 UI 적용")
    uman = json.load(open(os.path.join(UI_REL, 'release_manifest.json'), encoding='utf-8'))
    urows = [r for r in uman['payload_files'] if r['role'] in UI_ROLES]
    if len(urows) != 89:
        fail(f"save/load UI 페이로드 개수가 89가 아니다: {len(urows)}")
    ucnt = collections.Counter()
    for row in urows:
        rel = row['relative_path']
        src = os.path.join(UI_REL, rel.replace('/', os.sep))
        if not os.path.exists(src):
            fail(f"UI 페이로드 없음: {rel}")
        if sha(src).upper() != row['sha256'].upper():
            fail(f"UI 페이로드 해시 불일치: {rel}")
        dst = os.path.join(DST, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        ucnt[row['role']] += 1
    for k, v in ucnt.items(): print(f"   {k}: {v}")

    print(f"3) 신규 GSC 설치")
    gm = json.load(open(r"P:\AI\forest-kr-build\gsc_build\manifests\gsc_build_manifest.json", encoding='utf-8'))
    ok = 0
    for row in gm['files']:
        f = row['file']
        src = os.path.join(GSC, f)
        if sha(src) != row['output']['sha256'].upper():
            fail(f"GSC 해시 불일치: {f}")
        shutil.copy2(src, os.path.join(DST, 'scr', f))
        ok += 1
    print(f"   {ok}개 GSC")

    print(f"4) 검증")
    bad = 0
    for row in gm['files']:
        p = os.path.join(DST, 'scr', row['file'])
        if sha(p) != row['output']['sha256'].upper(): bad += 1
    for row in man['payload_files']:
        # scenario_gsc 52개는 신규 빌드로 덮었으므로 릴리스 해시와 다른 게 정상
        if row['role'] == 'scenario_gsc': continue
        p = os.path.join(DST, row['relative_path'].replace('/', os.sep))
        if sha(p).upper() != row['sha256'].upper(): bad += 1
    for row in urows:
        p = os.path.join(DST, row['relative_path'].replace('/', os.sep))
        if sha(p).upper() != row['sha256'].upper(): bad += 1
    print(f"   해시 불일치: {bad}  (릴리스 GSC 52개는 신규 빌드로 대체됨 — 검증 제외)")
    if bad: fail("설치 검증 실패")
    m = sum(os.path.getsize(os.path.join(r, x)) for r, _, fs in os.walk(DST) for x in fs)
    print(f"\n설치 완료: {DST}  ({m/1024**3:.2f} GB)")
    print(f"실행: {os.path.join(DST, 'Forest.exe')}")
    print("RESULT: PASS")

elif mode == 'status':
    if not os.path.exists(DST): fail("미설치")
    gm = json.load(open(r"P:\AI\forest-kr-build\gsc_build\manifests\gsc_build_manifest.json", encoding='utf-8'))
    match = sum(1 for row in gm['files']
                if os.path.exists(os.path.join(DST, 'scr', row['file']))
                and sha(os.path.join(DST, 'scr', row['file'])) == row['output']['sha256'].upper())
    print(f"게임    : {DST}")
    print(f"GSC     : {match}/52 일치")
    exe = os.path.join(DST, 'Forest.exe')
    print(f"EXE     : {sha(exe)[:24]}…")
    print("RESULT: PASS")

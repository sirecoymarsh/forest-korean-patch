# -*- coding: utf-8 -*-
"""세이브/로드 화면 UI 자산(한국어)을 설치한다.

배경
  install_build.py 가 참조하는 누적 릴리스 staging_release_2BB2F4C7_gulim_chapter_titles 에는
  save/load UI 가 들어 있지 않다. 그래서 게임 폴더의 세이브 화면 챕터명이 영문 팬패치
  래스터("Story of the Beginning I", "Signpost")로 남아 있었다.

  한국어 자산은 별도 스테이징에 이미 빌드·검증되어 있다.
    - grps/dt1_*.wcg      88개  시나리오 제목 카드 (시작의 이야기·I, 이정표 …)
    - grps/savescrn.lwg    1개  화면 라벨 (저장 / 불러오기)

  이 89개는 staging_release_D27972DF_* 와 staging_release_BBC800B7_* 에서 바이트 단위로
  동일하다. 즉 번역 계보와 무관한 순수 UI 래스터이므로 현재 계보에 그대로 얹을 수 있다.

사용
  python install_saveload_ui.py check    설치 상태만 확인
  python install_saveload_ui.py install  설치 (기존 파일은 backup_en_saveload_ui/ 로 보존)
"""
import json, sys, io, os, shutil, hashlib

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

UI_REL = (r"P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest\work"
          r"\forest-en-korean-pilot\translation_work\correction_work"
          r"\staging_release_D27972DF_aistudio_objective_hotfix_save_load_ui")
DST = r"P:\AI\forest-kr-build\game"
BACKUP = r"P:\AI\forest-kr-build\backup_en_saveload_ui"
ROLES = ('save_load_scenario_title_ui', 'save_load_screen_ui')


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest().upper()


def fail(m):
    print(f"[오류] {m}")
    print("RESULT: FAIL")
    sys.exit(1)


def payload():
    man = json.load(open(os.path.join(UI_REL, 'release_manifest.json'), encoding='utf-8'))
    return [r for r in man['payload_files'] if r['role'] in ROLES]


mode = sys.argv[1] if len(sys.argv) > 1 else 'check'
rows = payload()
if len(rows) != 89:
    fail(f"페이로드 개수가 89가 아니다: {len(rows)}")

if mode == 'check':
    ok = miss = old = 0
    for r in rows:
        p = os.path.join(DST, r['relative_path'].replace('/', os.sep))
        if not os.path.exists(p):
            miss += 1
        elif sha(p) == r['sha256'].upper():
            ok += 1
        else:
            old += 1
    print(f"한국어 자산 설치됨 {ok} / 미설치(영문 등) {old} / 파일없음 {miss}  (총 {len(rows)})")
    print("RESULT: PASS" if old == 0 and miss == 0 else "RESULT: 설치 필요")

elif mode == 'install':
    # 1) 페이로드 무결성 선검증 — 하나라도 어긋나면 아무것도 건드리지 않는다
    for r in rows:
        src = os.path.join(UI_REL, r['relative_path'].replace('/', os.sep))
        if not os.path.exists(src):
            fail(f"페이로드 없음: {r['relative_path']}")
        if sha(src) != r['sha256'].upper():
            fail(f"페이로드 해시 불일치: {r['relative_path']}")
    print(f"1) 페이로드 검증: {len(rows)}개 해시 일치")

    # 2) 기존(영문) 자산 백업 — 되돌릴 수 있게
    saved = 0
    for r in rows:
        p = os.path.join(DST, r['relative_path'].replace('/', os.sep))
        if not os.path.exists(p):
            continue
        b = os.path.join(BACKUP, r['relative_path'].replace('/', os.sep))
        if os.path.exists(b):
            continue
        os.makedirs(os.path.dirname(b), exist_ok=True)
        shutil.copy2(p, b)
        saved += 1
    print(f"2) 기존 자산 백업: {saved}개 -> {BACKUP}")

    # 3) 설치
    n = 0
    for r in rows:
        src = os.path.join(UI_REL, r['relative_path'].replace('/', os.sep))
        dst = os.path.join(DST, r['relative_path'].replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    print(f"3) 설치: {n}개")

    # 4) 검증
    bad = [r['relative_path'] for r in rows
           if sha(os.path.join(DST, r['relative_path'].replace('/', os.sep))) != r['sha256'].upper()]
    if bad:
        fail(f"설치 검증 실패: {bad[:5]}")
    print(f"4) 검증: {len(rows)}/{len(rows)} 일치")
    print("RESULT: PASS")

else:
    fail(f"알 수 없는 명령: {mode}")

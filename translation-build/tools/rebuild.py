# -*- coding: utf-8 -*-
"""번역 맵 -> GSC 빌드 -> 게임 설치. (자립 체인)

  python rebuild.py build      맵으로 gsc_build\\scr 재생성
  python rebuild.py install    game\\scr 에 설치 (해시 검증)
  python rebuild.py all        둘 다
  python rebuild.py verify     빌더가 원래 파이프라인과 같은 산출물을 내는지 확인

2026-08-14 전면 재작성. 원래는 Codex 트리의 하네스와 빌더를 호출했는데 그 트리가
사라져 죽었다. 지금은 이 폴더 안에서만 돈다:

  base_scr\\                          기반 GSC 52 (gsc_build\\scr 스냅숏)
  gsc_build\\manifests\\gsc_build_manifest.json   uid -> (파일, 슬롯) 매핑
  tools\\gsc.py                       GSC 코덱 (직접 재해독)
  tools\\build_gsc.py                 빌더

`build_gsc.py verify` 가 근거다 — 패치 75 직후 맵으로 빌드하면 그때 산출물과
52개 전건 바이트 일치한다. 즉 새 빌더는 원래 파이프라인과 동일하게 동작한다.
"""
import json, sys, io, os, shutil, hashlib, subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = r"P:\AI\forest-kr-build"
TOOLS = os.path.join(ROOT, 'tools')
OUT = os.path.join(ROOT, 'gsc_build', 'scr')
GAME = os.path.join(ROOT, 'game', 'scr')
CUR = os.path.join(ROOT, 'current', 'translation_map.current.json')
STATE = os.path.join(ROOT, 'gsc_build', 'manifests', 'build_state.json')

sys.path.insert(0, TOOLS)


def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest().upper()


def fail(m):
    print(f'[오류] {m}')
    print('RESULT: FAIL')
    sys.exit(1)


def do_build():
    import build_gsc
    n = build_gsc.build(CUR, OUT)
    state = {
        'translation_map_sha256': sha_file(CUR),
        'file_count': n,
        'files': {f: sha_file(os.path.join(OUT, f)) for f in sorted(os.listdir(OUT))},
    }
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(state, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'빌드 : {n}개  맵 SHA {state["translation_map_sha256"][:16]}…')
    print('RESULT: PASS')


def do_install():
    if not os.path.exists(STATE):
        fail('빌드 상태 없음 — build 를 먼저 실행하라')
    st = json.load(open(STATE, encoding='utf-8'))
    if st['translation_map_sha256'] != sha_file(CUR):
        fail('빌드가 현재 맵과 다르다 — build 를 먼저 실행하라')
    bad = [f for f, h in st['files'].items() if sha_file(os.path.join(OUT, f)) != h]
    if bad:
        fail(f'빌드 산출물 변조: {bad[:5]}')
    print(f'검증 : 빌드 산출물 {len(st["files"])}개 해시 일치')

    n = 0
    for f, h in st['files'].items():
        dst = os.path.join(GAME, f)
        if not os.path.exists(dst) or sha_file(dst) != h:
            shutil.copy2(os.path.join(OUT, f), dst)
            n += 1
    print(f'설치 : {len(st["files"])}개 중 {n}개 갱신')
    bad = [f for f, h in st['files'].items() if sha_file(os.path.join(GAME, f)) != h]
    if bad:
        fail(f'설치 검증 실패: {bad[:5]}')
    print(f'검증 : 설치본 {len(st["files"])}/{len(st["files"])} 일치')
    print('RESULT: PASS')


cmd = sys.argv[1] if len(sys.argv) > 1 else 'all'
if cmd == 'build':
    do_build()
elif cmd == 'install':
    do_install()
elif cmd == 'all':
    do_build()
    do_install()
elif cmd == 'verify':
    subprocess.run([sys.executable, os.path.join(TOOLS, 'build_gsc.py'), 'verify'])
else:
    print(__doc__)
